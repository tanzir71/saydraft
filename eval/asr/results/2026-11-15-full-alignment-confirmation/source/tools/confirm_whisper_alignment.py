"""Freeze one confirmation of the admitted full-model/alignment candidate.

Only the previously reserved 20 bn/ta/te clips per language are eligible. No
downloads, app defaults, arbitrary candidates, reference edits or owner I/O.
"""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import time

from tools import probe_whisper_alignment as probe
from tools.asr_accuracy import digest

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT = ROOT / "eval/asr/results/2026-11-15-full-alignment"
RESERVATION = ROOT / "eval/asr/results/2026-11-14-external-boundaries/holdout"
COHORT = "reserved-bn-ta-te-60"
CRITERIA = {**probe.CRITERIA, "complete_verified_pairs": 60}


def claim_path():
    state = probe.read(RESERVATION / "state.json")
    return Path(state["languages"][0]["corpus"]).parent.parent / "full-alignment-confirmation-consumption.json"


def register_consumption(plan, registration):
    """An exclusive external claim survives partial runs and new output folders."""
    path = claim_path()
    if plan.get("consumption_claim_path") != str(path):
        raise ValueError("Confirmation consumption path changed")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(registration, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return {"path": str(path), "sha256": digest(path)}


def evidence_binding():
    return {name: digest(DEVELOPMENT / name) for name in (
        "manifest.json", "comparison/plan.json", "comparison/native/report.json"
    )}


def reserved_selection(state, corpora):
    """Derive the entire pre-existing suffix, never choose from model outputs."""
    if (not state.get("complete") or state.get("errors")
            or Counter(row["language"] for row in state["languages"])
            != {"bn": 1, "ta": 1, "te": 1}):
        raise ValueError("Incomplete reserved acquisition")
    result, audio_seen = [], set()
    for receipt in state["languages"]:
        language = receipt["language"]
        corpus = corpora[language]
        rows = corpus["clips"]
        if (len(rows) != 40 or len({r["id"] for r in rows}) != 40
                or any(r["language"] != language for r in rows)
                or receipt.get("inference_run") is not False
                or receipt.get("observed_prefix_matches_baseline") is not True
                or [r["id"] for r in rows[:20]] != receipt["excluded_observed_ids"]
                or [r["id"] for r in rows[20:]] != receipt["heldout_ids"]
                or {str(r["id"]): r["sha256"] for r in rows[20:]}
                != receipt["heldout_audio_sha256"]):
            raise ValueError("Reserved selection changed or overlaps observed IDs")
        for row in rows:
            if row["sha256"] in audio_seen:
                raise ValueError("Reserved/observed audio overlaps")
            audio_seen.add(row["sha256"])
        result.extend({
            "language": language, "id": row["id"],
            "audio_sha256": row["sha256"],
            "corpus": {"path": receipt["corpus"], "sha256": receipt["corpus_sha256"]},
        } for row in rows[20:])
    if len(result) != 60:
        raise ValueError("All sixty reserved clips are required")
    return result


def selected_clips(plan):
    """Bind every child to the previously committed reservation and candidate."""
    dev = probe.read(DEVELOPMENT / "comparison/plan.json")
    state = probe.read(RESERVATION / "state.json")
    corpora = {lang: probe.read(RESERVATION / f"{lang}-corpus.json")
               for lang in ("bn", "ta", "te")}
    expected = reserved_selection(state, corpora)
    if (plan.get("cohort") != COHORT or plan.get("criteria") != CRITERIA
            or plan.get("clips") != expected
            or plan.get("candidate_model") != dev["candidate_model"]
            or plan.get("development_evidence") != evidence_binding()
            or plan.get("reservation_sha256") != digest(RESERVATION / "state.json")
            or plan.get("confirmation_producer_sha256") != digest(__file__)
            or plan.get("seed") != dev["seed"]
            or plan.get("repeat_control_index") != 39
            or plan.get("consumption_claim_path") != str(claim_path())
            or plan.get("case_timeout_seconds") != 600):
        raise ValueError("Frozen confirmation candidate, selection or criteria changed")
    probe.full_candidate(plan)
    return expected


def require_development(plan, report):
    from tools.bench_models import score

    if (plan["criteria"] != probe.CRITERIA or plan["source"]["dirty"]
            or report["source"] != plan["source"]
            or not report.get("measurement_integrity")
            or not report.get("complete") or not report.get("control_reproduced")
            or len(report["cases"]) != 18 or len(report["processes"]) != 19
            or any(not p.get("job_tree_exit_observed") or p.get("returncode") != 0
                   for p in report["processes"])):
        raise ValueError("No complete reproducible admitted development result")
    for row in report["cases"]:
        if row["scores"] != score(row["reference"], row["text"]):
            raise ValueError("Development scores changed")
    comparison = probe.summarize(report["cases"])
    if comparison != report["comparison"] or not comparison["development_gate_met"]:
        raise ValueError("Development gate failed")
    repeat = report["reproducibility_case"]
    original = next(r for r in report["cases"] if r["language"] == repeat["language"]
                    and r["id"] == repeat["id"] and r["arm"] == "control")
    if not probe.same_recognition(original, repeat):
        raise ValueError("Development control did not reproduce")


def freeze(reserved_state, output):
    from tools.asr_accuracy import _source, load_corpora
    from tools.latency_environment import runtime_environment
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model

    source = _source()
    if source["dirty"]:
        raise ValueError("Commit before freezing confirmation")
    dev = probe.read(DEVELOPMENT / "comparison/plan.json")
    report = probe.read(DEVELOPMENT / "comparison/native/report.json")
    for record in probe.read(DEVELOPMENT / "manifest.json")["records"]:
        path = DEVELOPMENT / record["path"]
        if path.stat().st_size != record["size"] or digest(path) != record["sha256"]:
            raise ValueError("Retained development evidence changed")
    require_development(dev, report)
    if (source["fingerprints"] != dev["source"]["fingerprints"]
            or runtime_environment() != dev["runtime_environment"]
            or get_model(dev["model_id"]) != dev["model_descriptor"]):
        raise ValueError("ASR runtime, production engine or control model changed")
    for descriptor, directory in [
        (dev["model_descriptor"], dev["model_directory"]),
        (dev["candidate_model"]["descriptor"], dev["candidate_model"]["directory"]),
    ]:
        if not installation_ready(descriptor, Path(directory), check_hashes=True):
            raise ValueError("Model cache changed")
    if digest(reserved_state) != digest(RESERVATION / "state.json"):
        raise ValueError("Supply the exact previously reserved acquisition state")
    if claim_path().exists():
        raise ValueError("Reserved set already committed to confirmation; preserve its existing run")
    state = probe.read(reserved_state)
    paths = [r["corpus"] for r in state["languages"]]
    _, receipts = load_corpora(paths)
    corpora = {}
    for row in state["languages"]:
        lang, path = row["language"], Path(row["corpus"])
        if digest(path) != row["corpus_sha256"] or digest(path) != digest(RESERVATION / f"{lang}-corpus.json"):
            raise ValueError("Reserved corpus changed")
        corpus = corpora[lang] = probe.read(path)
        old = next(r for r in dev["clips"] if r["language"] == lang)
        if digest(old["baseline_journal"]) != old["baseline_journal_sha256"]:
            raise ValueError("Observed baseline changed")
        journal = [json.loads(line) for line in Path(old["baseline_journal"]).read_text(encoding="utf-8").splitlines()]
        for clip in corpus["clips"][:20]:
            probe.require_observed(clip, clip, journal, dev["model_id"])
    selected = reserved_selection(state, corpora)
    plan = deepcopy(dev)
    plan.update(
        cohort=COHORT, scope="All sixty reserved bn/ta/te confirmation clips; no tuning or default promotion.",
        frozen_epoch=time.time(), source=source, producer_sha256=digest(probe.__file__),
        child_guard_sha256=digest(ROOT / "tools/public_file_guard.py"),
        confirmation_producer_sha256=digest(__file__), development_evidence=evidence_binding(),
        reservation_sha256=digest(reserved_state), clips=selected, corpora=receipts,
        criteria=CRITERIA, repeat_control_index=39, case_timeout_seconds=600,
        consumption_claim_path=str(claim_path()),
    )
    plan.pop("selection_path")
    plan.pop("selection_sha256")
    selected_clips(plan)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep confirmation output outside the checkout")
    output.mkdir(parents=True, exist_ok=False)
    probe.write(output / "plan.json", plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reserved-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    freeze(args.reserved_state, args.output)
    print("Frozen all sixty reserved clips and unchanged candidate/criteria; no inference.")


if __name__ == "__main__":
    main()
