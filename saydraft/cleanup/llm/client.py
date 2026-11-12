"""Text-only cleanup over the owned streaming sidecar; failures preserve rules."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .loopback import LocalHTTPError
from .calibration import DecoderCalibration
from .gate import MIN_REQUEST_SECONDS, decision, predict
from .prompts import PromptHints, bridge_protected, build_messages, output_token_limit
from .sidecar import SidecarReply
from .streaming import read_completion
from .structure import rule_structure_reason


@dataclass(frozen=True)
class CleanupReply:
    text: str | None
    reason: str
    input_tokens: int = 0
    output_limit: int = 0
    gate: dict | None = None


class CleanupClient:
    def __init__(self, manager, *, max_tokens=256, clock=time.monotonic):
        if type(max_tokens) is not int or max_tokens < 1:
            raise ValueError("Cleanup output cap must be a positive integer")
        self.manager, self.max_tokens, self.clock = manager, max_tokens, clock
        self.decoder = DecoderCalibration(manager)
        self._prefix = None

    def calibrate_decoder(self, *, timeout=60):
        return CleanupReply(None, self.decoder.measure(timeout=timeout))

    def _request(self, text, *, hints=None, glossary=(), timeout=0.8, max_tokens=None, gate=None,
                 cache_tokens=False, stop_at=None):
        try:
            messages = build_messages(text, hints=hints, glossary=glossary)
        except (OSError, ValueError):
            return SidecarReply(None, "prompt_unavailable")
        if stop_at is not None:
            timeout = min(timeout, max(0, stop_at - self.clock()))
            if timeout <= 0:
                info = decision(gate, "skip_budget", remaining=0) if gate is not None else None
                return SidecarReply({"skipped": "skip_budget", "gate": info}, "ok")

        gate_plan = None

        def operation(client, deadline):
            nonlocal gate_plan
            def budget_skip(source_tokens=0):
                remaining = max(0, deadline - self.clock())
                if gate is not None and remaining <= MIN_REQUEST_SECONDS:
                    return {"skipped": "skip_budget", "gate": decision(gate, "skip_budget",
                        remaining=remaining, source_tokens=source_tokens)}
                return None

            def check():
                if self.clock() >= deadline:
                    raise TimeoutError("Cleanup deadline expired")

            def tokenize(content):
                tokens = client.request_json("/tokenize", payload={"content": content, "add_special": False},
                                             deadline=deadline).get("tokens")
                if not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens):
                    raise LocalHTTPError("Local tokenizer returned unsupported tokens")
                return tokens
            if skipped := budget_skip():
                return skipped
            tokens = tokenize(text)
            if skipped := budget_skip(len(tokens)):
                return skipped
            limit = min(self.max_tokens if max_tokens is None else max_tokens, output_token_limit(len(tokens)))
            generation = getattr(self.manager, "generation", None)
            base = tuple((m["role"], m["content"]) for m in messages[:-1])
            user_tokens = tokenize(messages[-1]["content"]) if cache_tokens or gate is not None else None
            plan = None
            if gate is not None:
                remaining = max(0, deadline - self.clock())
                if remaining <= MIN_REQUEST_SECONDS:
                    plan = decision(gate, "skip_budget", remaining=remaining, source_tokens=len(tokens))
                elif self._prefix is None or generation is None or self._prefix[:2] != (generation, base):
                    plan = decision(gate, "skip_unprepared_prefix", remaining=remaining)
                else:
                    common = 0
                    for before, after in zip(self._prefix[2], user_tokens):
                        if before != after:
                            break
                        common += 1
                    measurement = self.decoder.current
                    rate = min(measurement.rates) if measurement is not None else None
                    plan = predict(gate, source_tokens=len(tokens), pending_tokens=len(user_tokens) - common + 12,
                                   output_limit=limit, rate=rate, remaining=remaining)
                gate_plan = plan
                if plan["reason"] != "call":
                    return {"skipped": plan["reason"], "gate": plan}  # Tokenization earns no generation credit.
            payload = {"model": "saydraft-cleanup", "messages": messages, "stream": True, "n": 1,
                "temperature": 0, "max_tokens": limit, "stop": ["</out>"], "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none"}
            with client.response_bytes("/v1/chat/completions", payload=payload, deadline=deadline,
                                       content_type="text/event-stream") as chunks:
                result = read_completion(chunks, check)
            self._prefix = ((generation, base, tuple(user_tokens))
                            if user_tokens is not None and result["done"] else None)
            return {**result, "input_tokens": len(tokens), "output_limit": limit, "gate": plan}

        reply = self.manager.run(operation, timeout=timeout)
        if reply.value is None and gate_plan is not None:
            return SidecarReply({"failed": reply.reason, "gate": gate_plan}, "ok")
        return reply

    def prepare_prompt(self, *, style="neutral", post_rules=True, app="", group="general", timeout=60):
        # A fixed one-token probe warms the real chat prefix, never user content.
        reply = self._request("Ready", hints=PromptHints(style=style, post_rules=post_rules, app=app, group=group),
                              timeout=timeout, max_tokens=1, cache_tokens=True)
        value = reply.value or {}
        complete = (value.get("done") and value.get("finish_reason") in ("stop", "length")
                    and not value.get("tool_calls") and value.get("input_tokens", 0) > 0)
        reason = "prepared" if complete else reply.reason if reply.reason != "ok" else "prompt_incomplete"
        return CleanupReply(None, reason)

    def clean(self, text, *, hints=None, glossary=(), timeout=0.8, gate=None, stop_at=None):
        if not text.strip():
            return CleanupReply(None, "empty")
        protected = bridge_protected(text)
        reply = self._request(protected.text, hints=hints, glossary=glossary, timeout=timeout, gate=gate, stop_at=stop_at)
        if reply.value is None:
            return CleanupReply(None, reply.reason)
        value = reply.value
        counts = {"input_tokens": value.get("input_tokens", 0), "output_limit": value.get("output_limit", 0),
                  "gate": value.get("gate")}
        if value.get("skipped"):
            return CleanupReply(None, value["skipped"], **counts)
        if value.get("failed"):
            return CleanupReply(None, value["failed"], **counts)
        if not value.get("done") or value.get("finish_reason") != "stop":
            return CleanupReply(None, "incomplete", **counts)
        if value.get("tool_calls"):
            return CleanupReply(None, "tool_output", **counts)
        candidate = value.get("text")
        if not isinstance(candidate, str) or not candidate.strip():
            return CleanupReply(None, "empty", **counts)
        restored = protected.restore(candidate.strip())
        if restored is None:
            return CleanupReply(None, "protected_changed", **counts)
        if hints is not None and hints.post_rules:
            reason = rule_structure_reason(text, restored)
            if reason:
                return CleanupReply(None, reason, **counts)
        return CleanupReply(restored, "ok", **counts)
