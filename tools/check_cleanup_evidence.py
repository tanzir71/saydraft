"""Check retained native quality evidence; never download or run a model in CI."""

import argparse
import hashlib
import json
import math
import re
import statistics
import tarfile
from pathlib import Path

from saydraft.cleanup.llm.bakeoff import corpus_digest
from saydraft.cleanup.llm.candidates import ROOT, get_candidate
from saydraft.cleanup.llm.eval_validation import DEFAULT_CORPUS, load_cases
from saydraft.eval import load_eval_corpus
from saydraft.models.manifest import safe_member
from saydraft.models.runtime_ids import runtime_model_id

POLICY_INDEX = ROOT / "eval/cleanup/results/2026-11-16-qualification/policy-index.json"
FORCED_INDEX = ROOT / "eval/cleanup/results/2026-11-16-qualification/forced-index.json"
REQUIRED = {"saydraft/cleanup/llm/client.py", "saydraft/cleanup/llm/gate.py",
    "saydraft/cleanup/llm/validate.py", "saydraft/dictation/pipeline.py",
    "saydraft/dictation/llm_local.py", "saydraft/core/processing.py", "saydraft/core/preferences.py", "saydraft/eval.py",
    "saydraft/cleanup/styles.py",
    "saydraft/text_boundaries.py", "saydraft/text_entities.py"}
GUARDS = {"saydraft/cleanup/llm/validate.py", "saydraft/cleanup/llm/structure.py", "saydraft/dictation/pipeline.py",
          "saydraft/text_boundaries.py", "saydraft/text_entities.py"}
PAIR = {"qwen08-cpu.json": ("qwen35-08b-q4-k-m", "cpu", 25),
        "qwen2-vulkan1.json": ("qwen35-2b-q4-k-m", "vulkan", 40)}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate evidence field")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Nonfinite evidence value")


def load(path):
    require(Path(path).stat().st_size <= 2 * 1024**2, "Evidence file exceeds bound")
    content = Path(path).read_bytes()
    require(len(content) <= 2 * 1024**2, "Evidence file exceeds bound")
    return json.loads(content, object_pairs_hook=_pairs, parse_constant=_nonfinite)


def source_matches(path, expected):
    require(isinstance(expected, str) and re.fullmatch(r"[a-f0-9]{64}", expected), "Invalid source digest")
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return expected in (digest(content), digest(content.replace(b"\n", b"\r\n")))


def check_source(report, root, *, forced):
    fingerprints = {}
    recorded = report.get("source_fingerprints", {})
    require(isinstance(recorded, dict), "Invalid evidence source fingerprints")
    for name, value in recorded.items():
        normalized = name.replace("\\", "/")
        require(normalized not in fingerprints, "Ambiguous evidence source path")
        fingerprints[normalized] = value
    required = GUARDS if forced else REQUIRED
    require(required <= fingerprints.keys(), "Missing evidence source fingerprints")
    selected = required if forced else {name for name in fingerprints if name.startswith(
        ("saydraft/cleanup/", "saydraft/dictation/"))} | required
    for name in selected:
        require(safe_member(name), "Unsafe evidence source path")
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()), "Evidence source escapes repository")
        require(source_matches(path, fingerprints[name]), "Stale cleanup source: " + name)
    prompts = report.get("prompt_sha256", {})
    require(isinstance(prompts, dict), "Invalid evidence prompts")
    current = {path.name: path for path in (root / "saydraft/cleanup/llm/prompts").iterdir()
               if path.suffix in (".txt", ".json", ".py")}
    require(prompts.keys() == current.keys(), "Prompt evidence file set changed")
    require(all(source_matches(current[name], value) for name, value in prompts.items()), "Stale cleanup prompts")


def _archived_reports(index, *, root):
    name = index.get("archive", "")
    require(isinstance(name, str) and safe_member(name), "Unsafe evidence archive path")
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), "Evidence archive escapes repository")
    require(path.stat().st_size <= 32 * 1024**2, "Evidence archive exceeds bound")
    expected = index.get("archive_sha256", "")
    require(isinstance(expected, str) and re.fullmatch(r"[a-f0-9]{64}", expected), "Invalid archive digest")
    selected, members, total_size = {}, set(), 0
    for entry in index.get("reports", []):
        member = entry.get("member", "")
        require(isinstance(member, str) and safe_member(member) and member not in selected,
                "Invalid or duplicate archive report member")
        selected[member] = None
    # Never extract to disk. Hash and read through the same archive handle.
    with path.open("rb") as source:
        require(hashlib.file_digest(source, "sha256").hexdigest() == expected, "Evidence archive bytes changed")
        source.seek(0)
        with tarfile.open(fileobj=source, mode="r:gz") as archive:
            for member in archive:
                require(member.name not in members and len(members) < 2048, "Duplicate or excessive archive members")
                members.add(member.name)
                total_size += member.size
                require(0 <= member.size and total_size <= 64 * 1024**2, "Unpacked evidence archive exceeds bound")
                if member.name not in selected:
                    continue
                require(member.isfile() and 0 <= member.size <= 2 * 1024**2, "Invalid or oversized archive report")
                selected[member.name] = archive.extractfile(member).read(2 * 1024**2 + 1)
    require(all(content is not None for content in selected.values()), "Archive report member missing")
    return selected


def reports(index_path, *, root=ROOT):
    index = load(index_path)
    require(isinstance(index, dict) and type(index.get("schema_version")) is int
            and index["schema_version"] in (1, 2) and index.get("selection_performed") is False,
            "Invalid evidence index")
    require(isinstance(index.get("source_commit"), str) and re.fullmatch(r"[a-f0-9]{7,40}", index["source_commit"]),
            "Invalid evidence source commit")
    require(isinstance(index.get("reports"), list) and len(index["reports"]) == len(PAIR),
            "Evidence requires both CPU 0.8B and Vulkan 2B reports")
    require(all(isinstance(entry, dict) for entry in index["reports"]), "Invalid report entry")
    archived = _archived_reports(index, root=root) if index["schema_version"] == 2 else None
    result = {}
    for entry in index.get("reports", []):
        name = entry.get("report", "")
        require(isinstance(name, str) and safe_member(name) and Path(name).name == name
                and name not in result, "Invalid report filename")
        if archived is None:
            path = index_path.parent / name
            require(path.stat().st_size <= 2 * 1024**2, "Evidence file exceeds bound")
            content = path.read_bytes()
        else:
            content = archived[entry["member"]]
        require(len(content) <= 2 * 1024**2, "Evidence file exceeds bound")
        require(digest(content) == entry.get("report_sha256"), "Native report bytes changed")
        report = json.loads(content, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        require(isinstance(report, dict), "Invalid native report")
        commit = report.get("git_commit", "")
        require(re.fullmatch(r"[a-f0-9]{40}", commit) and commit.startswith(index.get("source_commit", "!")),
                "Native report source commit differs")
        result[name] = report
    require(result.keys() == PAIR.keys(), "Evidence requires both CPU 0.8B and Vulkan 2B reports")
    return result


def _validate_report(report, *, root, identifier, backend, forced, golden, adversarial):
    require(report.get("candidate") == get_candidate(identifier), "Candidate identity or pinned artifact changed")
    require(report.get("backend") == backend and report.get("full_corpus") is True
            and report.get("source_dirty") is False and report.get("isolation_declared") is True,
            "Native evidence is partial, dirty or not isolated")
    require(report.get("runtime") == runtime_model_id(backend) and report.get("context_size") == 4096
            and report.get("max_output_tokens") == 256 and report.get("decoding_temperature") == 0,
            "Native generation contract changed")
    exits = report.get("native_exit_observed", [])
    require(isinstance(exits, list) and exits and all(value is True for value in exits), "Native exit evidence missing")
    require(not report.get("error_type"), "Native measurement failed")
    require(report.get("golden_sha256") == corpus_digest(golden)
            and report.get("adversarial_sha256") == digest(json.dumps(adversarial, sort_keys=True).encode()),
            "Native evidence uses a different corpus")
    check_source(report, root, forced=forced)
    suites = report.get("suites", {})
    require(isinstance(suites, dict), "Invalid native suites")
    for suite, count in (("golden", len(golden)), ("adversarial", len(adversarial))):
        row = suites.get(suite, {})
        require(isinstance(row, dict) and row.get("requested") == row.get("completed") == count
                and row.get("preservation_failures") == [], "Incomplete suite or must-keep regression")
    if forced:
        require(report.get("measurement_complete") is True and report.get("throughput_complete") is True,
                "Forced model measurement incomplete")
        require(suites["adversarial"].get("client_replies_with_token_counts") == len(adversarial),
                "Adversarial fallback cannot earn model generation credit")
    else:
        require(report.get("policy_measurement_complete") is True and report.get("interactive_budget_gate") is True
                and report.get("interactive_prompt_preparation") is True and report.get("quality_timeout_ms") == 800,
                "Production policy evidence missing or budget changed")


def _decoder_rates(report, *, forced):
    if forced:
        samples = report.get("throughput_60_tokens", [])
        require(isinstance(samples, list) and len(samples) == 3 and all(
            isinstance(sample, dict) and sample.get("valid") is True and sample.get("reason") == "ok"
            and sample.get("tokens") == 60 for sample in samples), "Invalid forced decoder calibration")
        rates = [sample.get("tokens_per_second") for sample in samples]
    else:
        measurement = report.get("live_decoder_calibration") or {}
        require(isinstance(measurement, dict) and measurement.get("tokens_per_sample") == 60
                and measurement.get("sample_count") == 3, "Invalid live decoder calibration")
        rates = measurement.get("tokens_per_second", [])
    require(isinstance(rates, list) and len(rates) == 3 and all(
        type(rate) in (int, float) and math.isfinite(rate) and rate > 0 for rate in rates),
        "Invalid live decoder calibration")
    return rates


def _quality_failures(report, *, forced, count):
    row = report["suites"]["golden"]
    failures = []
    require(isinstance(row.get("decisions", {}), dict), "Invalid golden decision counts")
    passed, accepted = row.get("exact_passes", -1), row.get("accepted_replies", 0)
    if not (type(passed) is int and .92 * count <= passed <= count and row.get("regressions") == []):
        failures.append("Hybrid exact quality below 92% or golden regression")
    if not forced and not (type(accepted) is int and accepted > 0
            and row.get("decisions", {}).get("accepted") == accepted
            and accepted <= row.get("client_replies_with_token_counts", 0)):
        failures.append("Rules fallback cannot earn accepted model credit")
    return failures


def assess(policy_index=POLICY_INDEX, forced_index=FORCED_INDEX, *, root=ROOT):
    """Report every stage's evidence, quality and speed without promoting defaults."""
    policy, forced = reports(Path(policy_index), root=root), reports(Path(forced_index), root=root)
    golden = load_eval_corpus(root / "tests/eval_corpus.jsonl")
    adversarial = load_cases(root / DEFAULT_CORPUS.relative_to(ROOT))
    require(len(golden) >= 556 and len(adversarial) >= 100, "Cleanup corpus shrank")
    results = []
    for name, (identifier, backend, minimum) in PAIR.items():
        for report, is_forced in ((policy[name], False), (forced[name], True)):
            result = {"candidate": identifier, "backend": backend, "mode": "forced" if is_forced else "policy",
                      "source_commit": report.get("git_commit"), "evidence_valid": False,
                      "quality_passed": False, "rate_target_met": False, "passed": False}
            try:
                _validate_report(report, root=root, identifier=identifier, backend=backend,
                                 forced=is_forced, golden=golden, adversarial=adversarial)
                rates = _decoder_rates(report, forced=is_forced)
                failures = _quality_failures(report, forced=is_forced, count=len(golden))
                row = report["suites"]["golden"]
                median = statistics.median(rates)
                result.update(evidence_valid=True, quality_passed=not failures, quality_failures=failures,
                    hybrid_exact_passes=row.get("exact_passes"), golden_cases=len(golden),
                    accepted_replies=row.get("accepted_replies", 0), golden_regressions=row.get("regressions"),
                    decoder_median_tps=median, rate_target_tps=minimum, rate_target_met=median >= minimum,
                    passed=not failures and median >= minimum)
            except (OSError, TypeError, KeyError, ValueError) as error:
                result["reason"] = str(error)
            results.append(result)
    return {"passed": all(row["passed"] for row in results),
            "evidence_valid": all(row["evidence_valid"] for row in results),
            "quality_passed": all(row["quality_passed"] for row in results),
            "performance_passed": all(row["rate_target_met"] for row in results),
            "reports": results, "scope": "retained native quality and decoder speed; no tier/latency/default acceptance"}


def check(policy_index=POLICY_INDEX, forced_index=FORCED_INDEX, *, root=ROOT):
    """Legacy quality-only API; callers inspect speed separately from quality."""
    result = assess(policy_index, forced_index, root=root)
    for row in result["reports"]:
        require(row["evidence_valid"], row.get("reason", "Invalid native evidence"))
        require(row["quality_passed"], "; ".join(row["quality_failures"]))
    fields = ("candidate", "hybrid_exact_passes", "accepted_replies", "decoder_median_tps",
              "rate_target_tps", "rate_target_met")
    return {"passed": True, "reports": [{key: row[key] for key in fields}
            for row in result["reports"] if row["mode"] == "policy"],
            "scope": "retained native quality; no tier/latency/default acceptance"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-index", type=Path, default=POLICY_INDEX)
    parser.add_argument("--forced-index", type=Path, default=FORCED_INDEX)
    args = parser.parse_args(argv)
    try:
        result = assess(args.policy_index, args.forced_index)
        print(json.dumps(result, allow_nan=False))
    except (OSError, TypeError, KeyError, ValueError, tarfile.TarError) as error:
        print(json.dumps({"passed": False, "reason": str(error)}))
        return 1
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
