"""Frozen public-file comparison of Whisper word alignment, without app defaults.

Only the nine previously observed bn/ta/te development clips in the supplied
selection plan are eligible. No model downloads, capture, clipboard or input.
"""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import os
import sys
import time

ARMS = ("control", "word_alignment")
CRITERIA = {
    "each_language_wer_nonworse": True,
    "each_language_cer_strictly_better": True,
    "no_new_empty_or_replacement_per_clip": True,
    "complete_verified_pairs": 9,
    "owner_or_broad_accuracy_accepted": False,
    "fresh_control_reproducibility": True,
}


def read(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Oversized probe record")
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    stage = path.with_suffix(".tmp")
    stage.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    stage.replace(path)


def selected_clips(selection):
    rows = selection.get("clips", [])
    identities = {(row["language"], row["id"]) for row in rows}
    if (
        len(rows) != 9
        or len(identities) != 9
        or Counter(row["language"] for row in rows) != {"bn": 3, "ta": 3, "te": 3}
        or "development" not in selection.get("scope", "").lower()
        or "observed" not in selection.get("scope", "").lower()
    ):
        raise ValueError("Use the nine already-observed bn/ta/te development clips")
    return rows


def require_observed(row, clip, journal, model_id):
    matches = [
        case
        for case in journal
        if case.get("language") == row["language"]
        and case.get("id") == row["id"]
        and case.get("model") == model_id
    ]
    if (
        len(matches) != 1
        or matches[0].get("sha256") != clip["sha256"]
        or matches[0].get("reference") != clip["reference"]
    ):
        raise ValueError("Selected clip has no matching previously observed baseline")


def summarize(rows):
    pairs = {}
    for row in rows:
        identity = (row["language"], row["id"])
        pair = pairs.setdefault(identity, {})
        if row["arm"] not in ARMS or row["arm"] in pair:
            raise ValueError("Unexpected or duplicate comparison arm")
        pair[row["arm"]] = row
    summary, no_new_failures = {}, True
    complete = len(pairs) == 9 and all(
        set(pair) == set(ARMS) for pair in pairs.values()
    )
    for language in ("bn", "ta", "te"):
        totals = {}
        for arm in ARMS:
            records = [r for r in rows if r["language"] == language and r["arm"] == arm]
            counts = Counter()
            for row in records:
                counts.update(row["scores"])
            totals[arm] = {**counts, "samples": len(records)}
        control, candidate = totals["control"], totals["word_alignment"]
        eligible = control["samples"] == candidate["samples"] == 3
        totals["passes"] = bool(
            eligible
            and candidate["word_errors"] <= control["word_errors"]
            and candidate["character_errors"] < control["character_errors"]
        )
        summary[language] = totals
    for pair in pairs.values():
        if set(pair) != set(ARMS):
            no_new_failures = False
            continue
        control, candidate = (pair[arm] for arm in ARMS)
        if (
            control["reference"] != candidate["reference"]
            or control["audio_sha256"] != candidate["audio_sha256"]
        ):
            raise ValueError("Comparison changed reference or audio")
        no_new_failures &= not (
            candidate.get("error_type")
            or control.get("error_type")
            or (not candidate["text"].strip() and bool(control["text"].strip()))
            or ("\ufffd" in candidate["text"] and "\ufffd" not in control["text"])
        )
    return {
        "languages": summary,
        "complete_pairs": complete,
        "no_new_empty_or_replacement": no_new_failures,
        "development_gate_met": bool(
            complete and no_new_failures and all(v["passes"] for v in summary.values())
        ),
    }


def freeze(selection_path, model_directory, output):
    from tools.asr_accuracy import _source, digest, load_corpora
    from saydraft.asr.router import ALL_LANGUAGES
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from tools.latency_environment import runtime_environment

    source = _source()
    if source["dirty"]:
        raise ValueError("Commit the probe before freezing a native comparison")
    selected = selected_clips(read(selection_path))
    paths = list(dict.fromkeys(row["corpus"]["path"] for row in selected))
    clips, receipts = load_corpora(paths)
    lookup = {(row["language"], row["id"]): row for row in clips}
    model = get_model(ALL_LANGUAGES)
    if not installation_ready(model, model_directory, check_hashes=True):
        raise ValueError("Supply the explicitly installed pinned turbo model")
    for row in selected:
        if (
            digest(row["corpus"]["path"]) != row["corpus"]["sha256"]
            or digest(row["baseline_journal"]) != row["baseline_journal_sha256"]
            or lookup[row["language"], row["id"]]["sha256"] != row["audio_sha256"]
        ):
            raise ValueError("Observed development selection changed")
        journal_path = Path(row["baseline_journal"])
        if journal_path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Oversized observed baseline journal")
        require_observed(
            row,
            lookup[row["language"], row["id"]],
            [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
            ],
            ALL_LANGUAGES,
        )
    output = Path(output).resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Keep probe output outside the checkout")
    output.mkdir(parents=True, exist_ok=False)
    plan = {
        "schema": 1,
        "scope": "Nine already-observed public development clips; word alignment only. No holdout inference or default promotion.",
        "frozen_epoch": time.time(),
        "source": source,
        "producer_sha256": digest(__file__),
        "child_guard_sha256": digest(Path(__file__).with_name("public_file_guard.py")),
        "selection_path": str(Path(selection_path).resolve()),
        "selection_sha256": digest(selection_path),
        "clips": selected,
        "corpora": receipts,
        "runtime_environment": runtime_environment(),
        "model_id": ALL_LANGUAGES,
        "model_directory": str(Path(model_directory).resolve()),
        "model_descriptor": model,
        "criteria": CRITERIA,
        "seed": 1729,
        "repeat_control_index": max(
            index for index, row in enumerate(selected) if row["language"] == "ta"
        ),
        "generation": "Production engine kwargs in both arms; candidate adds word_timestamps=True. Each arm/clip uses a fresh Python/native process with seed1729 set before model construction. Unchanged 30-second padding, 448 max_length, language pin, beam5, noVAD/previous conditioning/default temperature sequence.",
    }
    write(output / "plan.json", plan)
    return plan


def run_case(plan_path, case_index, case_arm, output):
    from tools.asr_accuracy import _source, digest, load_corpora
    from tools.bench_models import score
    from tools.latency_environment import runtime_environment
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.privacy.netguard import NetworkGuard

    plan = read(plan_path)
    if (
        plan["source"] != _source()
        or plan["producer_sha256"] != digest(__file__)
        or plan["child_guard_sha256"]
        != digest(Path(__file__).with_name("public_file_guard.py"))
        or plan["runtime_environment"] != runtime_environment()
        or plan["criteria"] != CRITERIA
        or read(plan["selection_path"])["clips"] != plan["clips"]
        or digest(plan["selection_path"]) != plan["selection_sha256"]
        or get_model(plan["model_id"]) != plan["model_descriptor"]
    ):
        raise ValueError("Frozen comparison inputs changed")
    selected = selected_clips({"scope": plan["scope"], "clips": plan["clips"]})
    directory = Path(plan["model_directory"])
    if not installation_ready(plan["model_descriptor"], directory, check_hashes=True):
        raise ValueError("Pinned model bytes changed")
    if not 0 <= case_index < 9 or case_arm not in ARMS:
        raise ValueError("Choose an existing frozen case/arm")
    output = Path(output).resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Keep native QA output outside the checkout")
    output.mkdir(exist_ok=False)
    report = {
        "source": plan["source"],
        "plan_sha256": digest(plan_path),
        "started_epoch": time.time(),
        "runtime_environment": plan["runtime_environment"],
        "model_verified_before": True,
        "complete": False,
        "measurement_integrity": False,
        "cases": [],
        "owner_accuracy_accepted": False,
        "broad_language_accuracy_accepted": False,
        "release_latency_qualified": False,
        "fresh_process_per_case_arm": True,
        "native_pid": os.getpid(),
        "network_boundary": "Python guard/local-only; native firewall not measured",
    }
    write(output / "report.json", report)
    NetworkGuard.install()
    try:
        import ctranslate2
        import numpy as np
        import soundfile as sf
        from saydraft.stt.whisper_engine import _import_whisper_model
        from saydraft.asr.whisper_ct2 import (
            TURBO_MODEL,
            WhisperCT2Engine,
            WhisperEngineConfig,
        )

        clips, receipts = load_corpora([row["path"] for row in plan["corpora"]])
        if receipts != plan["corpora"]:
            raise ValueError("Public corpus records changed")
        lookup = {(row["language"], row["id"]): row for row in clips}
        ctranslate2.set_random_seed(plan["seed"])
        model = _import_whisper_model(suppress_ipv6_probe=True)(
            str(directory), device="cpu", compute_type="int8", local_files_only=True
        )
        report["seed_set_before_model"] = True
        if model.max_length != 448 or model.feature_extractor.chunk_length != 30:
            raise ValueError("Unexpected decoder/feature context")
        calls, segments_seen, current = [], [], {}
        native = model.model

        class NativeTrace:
            def __getattr__(self, name):
                return getattr(native, name)

            def generate(self, *args, **kwargs):
                if kwargs.get("max_length") != 448:
                    raise ValueError("Native context override is forbidden")
                result = native.generate(*args, **kwargs)
                calls.append(
                    {
                        "max_length": kwargs["max_length"],
                        "prompt_tokens": len(args[1][0]),
                        "sampling_temperature": kwargs.get("sampling_temperature"),
                        "sequences": [list(row.sequences_ids[0]) for row in result],
                    }
                )
                return result

        class EnginePort:
            def transcribe(self, audio, **kwargs):
                if current["arm"] == "word_alignment":
                    kwargs["word_timestamps"] = True
                segments, info = model.transcribe(audio, **kwargs)

                def capture():
                    for segment in segments:
                        segments_seen.append(
                            {
                                "start": segment.start,
                                "end": segment.end,
                                "seek": segment.seek,
                                "tokens": segment.tokens,
                                "text": segment.text,
                                "temperature": segment.temperature,
                                "words": [asdict(word) for word in segment.words]
                                if segment.words
                                else None,
                            }
                        )
                        yield segment

                return capture(), info

        model.model = NativeTrace()
        engine = WhisperCT2Engine(
            WhisperEngineConfig(model_size=TURBO_MODEL, silence_trim=False),
            model_factory=lambda *args, **kwargs: EnginePort(),
        )
        engine.prepare()
        with (output / "cases.jsonl").open("x", encoding="utf-8") as journal:
            for index, selection in enumerate(selected):
                if index != case_index:
                    continue
                clip = lookup[selection["language"], selection["id"]]
                audio, rate = sf.read(clip["audio_path"], dtype="float32")
                if (
                    rate != 16000
                    or audio.ndim != 1
                    or len(audio) != clip["num_samples"]
                    or not np.isfinite(audio).all()
                ):
                    raise ValueError("Invalid frozen audio")
                engine.set_language(clip["language"])
                for arm in ARMS if index % 2 == 0 else reversed(ARMS):
                    if arm != case_arm:
                        continue
                    ctranslate2.set_random_seed(plan["seed"])
                    current["arm"] = arm
                    calls.clear()
                    segments_seen.clear()
                    started = time.perf_counter()
                    error, text = None, ""
                    try:
                        text = engine.transcribe(audio)
                    except Exception as exc:
                        error = type(exc).__name__
                    row = {
                        "language": clip["language"],
                        "id": clip["id"],
                        "arm": arm,
                        "audio_sha256": clip["sha256"],
                        "audio_samples": len(audio),
                        "reference": clip["reference"],
                        "text": text,
                        "scores": score(clip["reference"], text),
                        "error_type": error,
                        "seconds": time.perf_counter() - started,
                        "decode_calls": list(calls),
                        "segments": list(segments_seen),
                    }
                    report["cases"].append(row)
                    journal.write(json.dumps(row, ensure_ascii=False) + "\n")
                    journal.flush()
                    write(output / "report.json", report)
                    print(
                        json.dumps(
                            {
                                key: row[key]
                                for key in (
                                    "language",
                                    "id",
                                    "arm",
                                    "scores",
                                    "error_type",
                                )
                            }
                        ),
                        flush=True,
                    )
        report["complete"] = len(report["cases"]) == 1
    finally:
        report["ended_epoch"] = time.time()
        report["source_unchanged"] = _source() == plan["source"]
        report["runtime_unchanged"] = (
            runtime_environment() == plan["runtime_environment"]
        )
        report["plan_unchanged"] = digest(plan_path) == report["plan_sha256"]
        report["producer_unchanged"] = digest(__file__) == plan["producer_sha256"]
        report["corpora_verified_after"] = (
            load_corpora([row["path"] for row in plan["corpora"]])[1] == plan["corpora"]
        )
        report["model_verified_after"] = installation_ready(
            plan["model_descriptor"], directory, check_hashes=True
        )
        report["journal_sha256"] = (
            digest(output / "cases.jsonl")
            if (output / "cases.jsonl").exists()
            else None
        )
        report["measurement_integrity"] = bool(
            report["complete"]
            and not plan["source"]["dirty"]
            and all(
                report[key]
                for key in (
                    "source_unchanged",
                    "runtime_unchanged",
                    "plan_unchanged",
                    "producer_unchanged",
                    "corpora_verified_after",
                    "model_verified_after",
                )
            )
            and not any(row["error_type"] for row in report["cases"])
        )
        report["comparison"] = summarize(report["cases"])
        NetworkGuard.uninstall()
        write(output / "report.json", report)
    return report


def same_recognition(first, second):
    return all(
        first[key] == second[key]
        for key in ["text", "scores", "decode_calls", "segments"]
    )


def run(plan_path):
    from tools.asr_accuracy import _source, digest
    from tools.latency_environment import runtime_environment
    from saydraft.models.downloader import installation_ready
    from saydraft.cleanup.llm.windows_process import WindowsJobProcess

    plan_path = Path(plan_path).resolve()
    plan = read(plan_path)
    if (
        _source() != plan["source"]
        or digest(__file__) != plan["producer_sha256"]
        or digest(Path(__file__).with_name("public_file_guard.py"))
        != plan["child_guard_sha256"]
        or runtime_environment() != plan["runtime_environment"]
        or plan["criteria"] != CRITERIA
    ):
        raise ValueError("Frozen parent inputs changed")
    output = plan_path.parent / "native"
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Keep native QA output outside the checkout")
    output.mkdir(exist_ok=False)
    for directory in ["cases", "guards", "processes"]:
        (output / directory).mkdir()
    report = {
        "source": plan["source"],
        "plan_sha256": digest(plan_path),
        "started_epoch": time.time(),
        "runtime_environment": plan["runtime_environment"],
        "cases": [],
        "processes": [],
        "complete": False,
        "measurement_integrity": False,
        "control_reproduced": False,
        "fresh_process_per_case_arm": True,
        "owner_accuracy_accepted": False,
        "broad_language_accuracy_accepted": False,
        "release_latency_qualified": False,
    }
    write(output / "report.json", report)
    try:
        with (output / "cases.jsonl").open("x", encoding="utf-8") as journal:
            selected = selected_clips({"scope": plan["scope"], "clips": plan["clips"]})
            repeat_index = plan["repeat_control_index"]
            if repeat_index != max(
                index for index, row in enumerate(selected) if row["language"] == "ta"
            ):
                raise ValueError("Frozen repeat selection changed")
            for slot, selection in enumerate([*selected, selected[repeat_index]]):
                index = slot if slot < 9 else repeat_index
                arms = (
                    (ARMS if index % 2 == 0 else reversed(ARMS))
                    if slot < 9
                    else ("control",)
                )
                for arm in arms:
                    name = f"{selection['language']}-{selection['id']}-{arm}"
                    if slot == 9:
                        name += "-repeat"
                    case_output = output / "cases" / name
                    guard_path = output / "guards" / f"{name}.json"
                    command = [
                        sys.executable,
                        "-m",
                        "tools.probe_whisper_alignment",
                        "case",
                        "--plan",
                        str(plan_path),
                        "--index",
                        str(index),
                        "--arm",
                        arm,
                        "--output",
                        str(case_output),
                        "--guard-output",
                        str(guard_path),
                    ]
                    process = {
                        "args": command,
                        "started_epoch": time.time(),
                        "native_exit_observed": False,
                        "timeout_reached": False,
                    }
                    process_path = output / "processes" / f"{name}.json"
                    with WindowsJobProcess(
                        command,
                        env=os.environ.copy(),
                        cwd=Path(__file__).resolve().parents[1],
                        capture_output=True,
                    ) as child:
                        process["launcher_pid"] = child.pid
                        write(process_path, process)
                        try:
                            process["returncode"] = child.wait_tree(timeout=180)
                        except TimeoutError:
                            process["timeout_reached"] = True
                            child.terminate()
                            process["returncode"] = child.wait_tree(timeout=3)
                        except BaseException:
                            child.terminate()
                            child.wait_tree(timeout=3)
                            raise
                        process["job_tree_exit_observed"] = True
                        process["combined_child_output"] = True
                        process_path.with_suffix(".stdout.txt").write_bytes(
                            child.read_output(timeout=2)
                        )
                        process_path.with_suffix(".stderr.txt").write_bytes(b"")
                    process.update(native_exit_observed=True, ended_epoch=time.time())
                    for suffix in [".stdout.txt", ".stderr.txt"]:
                        process[suffix] = digest(process_path.with_suffix(suffix))
                    case_report = (
                        read(case_output / "report.json")
                        if (case_output / "report.json").exists()
                        else {}
                    )
                    process["native_pid"] = case_report.get("native_pid")
                    write(process_path, process)
                    report["processes"].append(process)
                    if process["returncode"] != 0 or not case_report.get(
                        "measurement_integrity"
                    ):
                        raise RuntimeError(
                            "A fresh native case failed; retain partial evidence"
                        )
                    row = case_report["cases"][0]
                    if (
                        row["language"] != selection["language"]
                        or row["id"] != selection["id"]
                        or row["arm"] != arm
                    ):
                        raise ValueError("Fresh child returned a different case")
                    if slot < 9:
                        report["cases"].append(row)
                        journal.write(json.dumps(row, ensure_ascii=False) + "\n")
                        journal.flush()
                    else:
                        report["reproducibility_case"] = row
                        first = next(
                            case
                            for case in report["cases"]
                            if case["language"] == row["language"]
                            and case["id"] == row["id"]
                            and case["arm"] == "control"
                        )
                        report["control_reproduced"] = same_recognition(first, row)
                    write(output / "report.json", report)
                    print(
                        json.dumps(
                            {
                                key: row[key]
                                for key in ["language", "id", "arm", "scores"]
                            }
                        ),
                        flush=True,
                    )
        report["complete"] = (
            len(report["cases"]) == 18 and len(report["processes"]) == 19
        )
    finally:
        report["ended_epoch"] = time.time()
        report["source_unchanged"] = _source() == plan["source"]
        report["runtime_unchanged"] = (
            runtime_environment() == plan["runtime_environment"]
        )
        report["producer_unchanged"] = digest(__file__) == plan["producer_sha256"]
        report["plan_unchanged"] = digest(plan_path) == report["plan_sha256"]
        report["model_verified_after"] = installation_ready(
            plan["model_descriptor"], Path(plan["model_directory"]), check_hashes=True
        )
        report["journal_sha256"] = (
            digest(output / "cases.jsonl")
            if (output / "cases.jsonl").exists()
            else None
        )
        report["measurement_integrity"] = bool(
            report["complete"]
            and all(
                report[key]
                for key in [
                    "source_unchanged",
                    "runtime_unchanged",
                    "producer_unchanged",
                    "plan_unchanged",
                    "model_verified_after",
                    "control_reproduced",
                ]
            )
        )
        report["comparison"] = summarize(report["cases"])
        write(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("freeze")
    prepare.add_argument("--selection-plan", type=Path, required=True)
    prepare.add_argument("--model-dir", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    native = commands.add_parser("run")
    native.add_argument("--plan", type=Path, required=True)
    case = commands.add_parser("case")
    case.add_argument("--plan", type=Path, required=True)
    case.add_argument("--index", type=int, required=True)
    case.add_argument("--arm", choices=ARMS, required=True)
    case.add_argument("--output", type=Path, required=True)
    case.add_argument("--guard-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        freeze(args.selection_plan, args.model_dir, args.output)
        print("Frozen nine development pairs; no inference performed.")
        return 0
    if args.command == "case":
        from tools.public_file_guard import install

        install(args.guard_output)
        report = run_case(args.plan, args.index, args.arm, args.output)
    else:
        report = run(args.plan)
    print(json.dumps(report["comparison"], ensure_ascii=False))
    return 0 if report["measurement_integrity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
