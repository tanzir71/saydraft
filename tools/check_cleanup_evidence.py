"""Check retained native quality evidence; never download or run a model in CI."""

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

from saydraft.cleanup.llm.bakeoff import corpus_digest
from saydraft.cleanup.llm.candidates import ROOT, get_candidate
from saydraft.cleanup.llm.eval_validation import DEFAULT_CORPUS, load_cases
from saydraft.eval import load_eval_corpus
from saydraft.models.manifest import safe_member
from saydraft.models.runtime_ids import runtime_model_id

POLICY_INDEX = ROOT / "eval/cleanup/results/2026-11-12-rpc-policy/index.json"
FORCED_INDEX = ROOT / "eval/cleanup/results/2026-11-12-isolated/index.json"
REQUIRED = {"saydraft/cleanup/llm/client.py", "saydraft/cleanup/llm/gate.py",
    "saydraft/cleanup/llm/validate.py", "saydraft/dictation/pipeline.py",
    "saydraft/dictation/llm_local.py", "saydraft/core/processing.py", "saydraft/core/preferences.py", "saydraft/eval.py",
    "saydraft/cleanup/styles.py",
    "saydraft/text_boundaries.py", "saydraft/text_entities.py"}
GUARDS = {"saydraft/cleanup/llm/validate.py", "saydraft/cleanup/llm/structure.py",
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
    for name, value in report.get("source_fingerprints", {}).items():
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
    current = {path.name: path for path in (root / "saydraft/cleanup/llm/prompts").iterdir()
               if path.suffix in (".txt", ".json", ".py")}
    require(prompts.keys() == current.keys(), "Prompt evidence file set changed")
    require(all(source_matches(current[name], value) for name, value in prompts.items()), "Stale cleanup prompts")


def reports(index_path):
    index = load(index_path)
    require(index.get("schema_version") == 1 and index.get("selection_performed") is False, "Invalid evidence index")
    require(isinstance(index.get("source_commit"), str) and re.fullmatch(r"[a-f0-9]{7,40}", index["source_commit"]),
            "Invalid evidence source commit")
    result = {}
    for entry in index.get("reports", []):
        name = entry.get("report", "")
        require(safe_member(name) and Path(name).name == name and name not in result, "Invalid report filename")
        path = index_path.parent / name
        require(digest(path.read_bytes()) == entry.get("report_sha256"), "Native report bytes changed")
        report = load(path)
        commit = report.get("git_commit", "")
        require(re.fullmatch(r"[a-f0-9]{40}", commit) and commit.startswith(index.get("source_commit", "!")),
                "Native report source commit differs")
        result[name] = report
    require(result.keys() == PAIR.keys(), "Evidence requires both CPU 0.8B and Vulkan 2B reports")
    return result


def check(policy_index=POLICY_INDEX, forced_index=FORCED_INDEX, *, root=ROOT):
    policy, forced = reports(Path(policy_index)), reports(Path(forced_index))
    golden = load_eval_corpus(root / "tests/eval_corpus.jsonl")
    adversarial = load_cases(root / DEFAULT_CORPUS.relative_to(ROOT))
    require(len(golden) >= 472 and len(adversarial) >= 100, "Cleanup corpus shrank")
    golden_sha = corpus_digest(golden)
    adversarial_sha = digest(json.dumps(adversarial, sort_keys=True).encode())
    results = []
    for name, (identifier, backend, minimum) in PAIR.items():
        for report, is_forced in ((policy[name], False), (forced[name], True)):
            require(report.get("candidate") == get_candidate(identifier), "Candidate identity or pinned artifact changed")
            require(report.get("backend") == backend and report.get("full_corpus") is True
                    and report.get("source_dirty") is False and report.get("isolation_declared") is True,
                    "Native evidence is partial, dirty or not isolated")
            require(report.get("runtime") == runtime_model_id(backend) and report.get("context_size") == 4096
                    and report.get("max_output_tokens") == 256 and report.get("decoding_temperature") == 0,
                    "Native generation contract changed")
            exits = report.get("native_exit_observed", [])
            require(exits and all(value is True for value in exits) and not report.get("error_type"), "Native exit/failure evidence missing")
            require(report.get("golden_sha256") == golden_sha and report.get("adversarial_sha256") == adversarial_sha,
                    "Native evidence uses a different corpus")
            check_source(report, root, forced=is_forced)
            suites = report.get("suites", {})
            for suite, count in (("golden", len(golden)), ("adversarial", len(adversarial))):
                row = suites.get(suite, {})
                require(row.get("requested") == row.get("completed") == count and row.get("preservation_failures") == [],
                        "Incomplete suite or must-keep regression")
            if is_forced:
                require(report.get("measurement_complete") is True and report.get("throughput_complete") is True,
                        "Forced model measurement incomplete")
                require(suites["adversarial"].get("client_replies_with_token_counts") == len(adversarial),
                        "Adversarial fallback cannot earn model generation credit")
                continue
            require(report.get("policy_measurement_complete") is True and report.get("interactive_budget_gate") is True
                    and report.get("interactive_prompt_preparation") is True and report.get("quality_timeout_ms") == 800,
                    "Production policy evidence missing or budget changed")
            row = suites["golden"]
            passed, accepted = row.get("exact_passes", -1), row.get("accepted_replies", 0)
            require(type(passed) is int and .92 * len(golden) <= passed <= len(golden)
                    and row.get("regressions") == [], "Hybrid exact quality below 92% or golden regression")
            require(type(accepted) is int and accepted > 0 and row.get("decisions", {}).get("accepted") == accepted
                    and accepted <= row.get("client_replies_with_token_counts", 0), "Rules fallback cannot earn accepted model credit")
            measurement = report.get("live_decoder_calibration") or {}
            rates = measurement.get("tokens_per_second", [])
            require(measurement.get("tokens_per_sample") == 60 and measurement.get("sample_count") == 3
                    and len(rates) == 3 and all(type(rate) in (int, float) and math.isfinite(rate) and rate > 0
                    for rate in rates), "Invalid live decoder calibration")
        median = statistics.median(policy[name]["live_decoder_calibration"]["tokens_per_second"])
        results.append({"candidate": identifier, "hybrid_exact_passes": policy[name]["suites"]["golden"]["exact_passes"],
            "accepted_replies": policy[name]["suites"]["golden"]["accepted_replies"],
            "decoder_median_tps": median, "rate_target_tps": minimum, "rate_target_met": median >= minimum})
    return {"passed": True, "reports": results, "scope": "retained native quality; no tier/latency/default acceptance"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-index", type=Path, default=POLICY_INDEX)
    parser.add_argument("--forced-index", type=Path, default=FORCED_INDEX)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check(args.policy_index, args.forced_index)))
    except (OSError, TypeError, KeyError, ValueError) as error:
        print(json.dumps({"passed": False, "reason": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
