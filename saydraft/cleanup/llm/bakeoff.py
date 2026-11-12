"""Strict measured evaluation; output agreement never substitutes for model use."""

from __future__ import annotations

import hashlib
import math
import time
from collections import Counter
from dataclasses import asdict

from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.eval import EvalCase, execute_case
from .client import CleanupClient
from .validate import validate_llm_output


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ObservedCleaner:
    def __init__(self, factory, *, clock=time.perf_counter):
        self.clock, self.calls, self.reply = clock, [], {}
        self.delegate = factory(self.client_factory)

    def client_factory(self, manager, **kwargs):
        owner = self

        class RecordingClient(CleanupClient):
            def clean(self, *args, **kwargs):
                reply = super().clean(*args, **kwargs)
                owner.reply = {"client_reason": reply.reason, "source_tokens": reply.input_tokens,
                               "output_limit": reply.output_limit}
                return reply

        return RecordingClient(manager, **kwargs)

    def available(self):
        return self.delegate.available()

    def reset(self):
        self.calls, self.reply = [], {}

    def clean_with_context(self, text, *, context, glossary=()):
        started = self.clock()
        candidate, reason = self.delegate.clean_with_context(text, context=context, glossary=glossary)
        validation = validate_llm_output(text, candidate, mode=context.mode,
            intensity=context.intensity, glossary=glossary) if candidate else None
        self.calls.append({"reason": reason, "seconds": self.clock() - started,
            "returned_candidate": bool(candidate and candidate.strip()), "source_sha256": digest(text),
            "candidate_sha256": digest(candidate) if candidate else None,
            "candidate_validation": validation.reason if validation else None, **self.reply})
        return candidate, reason

    def close(self):
        self.delegate.close()


def measure_cases(golden, adversarial, pipeline, observer, *, ready=lambda: True, include_text=False):
    """Yield metadata after each actual processor case; stop on sidecar failure."""
    baseline = DictationPipeline(DictationConfig())
    original = pipeline.glossary
    fixtures = [("golden", case, "golden", ()) for case in golden] + [
        ("adversarial", EvalCase(row["id"], row["input"], "", row.get("mode", "balanced"), "general"),
         row["category"], tuple(row.get("glossary", ()))) for row in adversarial]
    last_style = None
    try:
        for suite, case, category, terms in fixtures:
            if not ready():
                raise RuntimeError("Sidecar unavailable; evaluation stopped before counting fallback-only cases")
            pipeline.glossary = baseline.glossary = Glossary(protected_terms=terms)
            rules = execute_case(case, baseline)
            observer.reset()
            started = time.perf_counter()
            actual = execute_case(case, pipeline)
            wall = time.perf_counter() - started
            exact = actual.cleaned_text == case.expected and actual.insertion.enter_sent == case.expected_enter
            base_exact = rules.cleaned_text == case.expected and rules.insertion.enter_sent == case.expected_enter
            same = actual.cleaned_text == rules.cleaned_text
            action_same = actual.insertion.enter_sent == rules.insertion.enter_sent
            bypass = case.mode == "raw" or case.profile == "code/comments" or case.app_group == "code"
            check = None if same or bypass else validate_llm_output(rules.cleaned_text, actual.cleaned_text,
                mode=case.mode, intensity=case.intensity, glossary=terms)
            preserved = action_same and (same if bypass else same or check.ok)
            style = {"email": "formal", "chat": "casual"}.get(case.profile, "neutral")
            relation = None if not observer.calls else "first" if last_style is None else (
                "style_changed" if style != last_style else "same_style")
            if observer.calls:
                last_style = style
            row = {"suite": suite, "id": case.id, "category": category, "style": style,
                "prefix_relation": relation, "decision": pipeline.last_llm_decision, "calls": observer.calls,
                "seconds": wall, "exact_pass": exact if suite == "golden" else None,
                "rules_exact_pass": base_exact if suite == "golden" else None, "same_as_rules": same,
                "preservation_ok": preserved, "preservation_reason": "exact" if same and action_same else
                    "action_changed" if not action_same else "bypass_changed" if bypass else check.reason,
                "input_sha256": digest(case.input_text), "output_sha256": digest(actual.cleaned_text),
                "baseline_sha256": digest(rules.cleaned_text), "enter_sent": actual.insertion.enter_sent}
            if include_text:
                row.update(input=case.input_text, expected=case.expected if suite == "golden" else None,
                           actual=actual.cleaned_text, rules=rules.cleaned_text)
            yield row
    finally:
        pipeline.glossary = original
        baseline.close()


def latency(values):
    values = sorted(values)
    return {"n": len(values), **({"p50_seconds": values[max(0, math.ceil(len(values) * .5) - 1)],
        "p95_seconds": values[max(0, math.ceil(len(values) * .95) - 1)], "max_seconds": values[-1]} if values else {})}


def summarize(rows, *, requested_golden, requested_adversarial):
    groups = {}
    for suite, requested in (("golden", requested_golden), ("adversarial", requested_adversarial)):
        selected = [row for row in rows if row["suite"] == suite]
        eligible = [row for row in selected if row["calls"]]
        calls = [call for row in selected for call in row["calls"]]
        passes = sum(row["exact_pass"] is True for row in selected)
        accepted_passes = sum(row["exact_pass"] is True and row["decision"] == "accepted" for row in eligible)
        groups[suite] = {"requested": requested, "completed": len(selected), "cleanup_calls": len(calls),
            "returned_candidates": sum(call["returned_candidate"] for call in calls),
            "client_replies": sum("client_reason" in call for call in calls),
            "client_replies_with_token_counts": sum(call.get("source_tokens", 0) > 0 for call in calls),
            "decisions": dict(Counter(row["decision"] for row in selected)),
            "call_reasons": dict(Counter(call["reason"] for call in calls)),
            "preservation_failures": [row["id"] for row in selected if not row["preservation_ok"]],
            "latency_by_prefix_relation": {label: latency([row["seconds"] for row in eligible
                if row["prefix_relation"] == label]) for label in ("first", "style_changed", "same_style")}}
        if suite == "golden":
            groups[suite].update(exact_passes=passes, exact_rate=100 * passes / max(1, len(selected)),
                accepted_exact_passes=accepted_passes, eligible_cases=len(eligible),
                accepted_exact_rate=100 * accepted_passes / max(1, len(eligible)),
                fallback_exact_passes=sum(row["exact_pass"] is True and row["decision"] != "accepted"
                                         and row["calls"] != [] for row in selected),
                regressions=[row["id"] for row in selected if row["rules_exact_pass"] and not row["exact_pass"]])
    return {"suites": groups, "measurement_complete": all(group["requested"] > 0
        and group["requested"] == group["completed"] and group["client_replies_with_token_counts"] > 0
        for group in groups.values()), "selection_performed": False,
        "notes": "Strict exact strings/actions; preservation checks are finite guards, not semantic proof."}


def corpus_digest(cases):
    import json
    return digest(json.dumps([asdict(case) for case in cases], ensure_ascii=False, sort_keys=True))
