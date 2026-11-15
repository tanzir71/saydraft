"""Confirmation admission and denominator checks; no owner I/O or inference."""

from copy import deepcopy
from pathlib import Path

import pytest

from tools import confirm_whisper_alignment as confirm
from tools import probe_whisper_alignment as probe
from tools.asr_accuracy import digest


def frozen_plan():
    plan = deepcopy(probe.read(confirm.DEVELOPMENT / "comparison/plan.json"))
    state = probe.read(confirm.RESERVATION / "state.json")
    corpora = {lang: probe.read(confirm.RESERVATION / f"{lang}-corpus.json")
               for lang in ("bn", "ta", "te")}
    plan.update(
        cohort=confirm.COHORT, criteria=deepcopy(confirm.CRITERIA),
        clips=confirm.reserved_selection(state, corpora), repeat_control_index=39,
        confirmation_producer_sha256=digest(confirm.__file__),
        development_evidence=confirm.evidence_binding(),
        reservation_sha256=digest(confirm.RESERVATION / "state.json"),
        case_timeout_seconds=600,
        consumption_claim_path=str(confirm.claim_path()),
    )
    return plan, state, corpora


def test_exact_previously_reserved_suffix_is_required():
    plan, state, _ = frozen_plan()
    rows = probe.selection_for_plan(plan)
    assert len(rows) == 60 and probe.criteria_for_plan(plan) == confirm.CRITERIA
    assert all(r["id"] not in next(s for s in state["languages"]
                                  if s["language"] == r["language"])["excluded_observed_ids"]
               for r in rows)
    assert probe.arm_options(plan, "word_alignment") == {
        "word_timestamps": True, "temperature": 0.0,
    }


@pytest.mark.parametrize("drift", [
    "missing_clip", "clip_order", "audio", "candidate", "criterion", "producer",
    "reservation", "evidence", "seed", "repeat", "timeout", "claim", "cohort",
])
def test_confirmation_refuses_candidate_selection_or_gate_drift(drift):
    plan, _, _ = frozen_plan()
    if drift == "missing_clip":
        plan["clips"].pop()
    elif drift == "clip_order":
        plan["clips"].reverse()
    elif drift == "audio":
        plan["clips"][0]["audio_sha256"] = "0" * 64
    elif drift == "candidate":
        plan["candidate_model"]["mode"] = "another-decoder"
    elif drift == "criterion":
        plan["criteria"]["each_language_cer_strictly_better"] = False
    elif drift == "producer":
        plan["confirmation_producer_sha256"] = "0" * 64
    elif drift == "reservation":
        plan["reservation_sha256"] = "0" * 64
    elif drift == "evidence":
        plan["development_evidence"]["manifest.json"] = "0" * 64
    elif drift == "seed":
        plan["seed"] += 1
    elif drift == "repeat":
        plan["repeat_control_index"] -= 1
    elif drift == "timeout":
        plan["case_timeout_seconds"] = 601
    elif drift == "claim":
        plan["consumption_claim_path"] = "arbitrary-claim.json"
    else:
        plan["cohort"] = "arbitrary-clips"
    with pytest.raises(ValueError):
        probe.selection_for_plan(plan)


@pytest.mark.parametrize("drift", ["missing", "duplicate_id", "same_audio", "inferred"])
def test_reserved_overlap_or_previous_consumption_is_refused(drift):
    _, state, corpora = frozen_plan()
    if drift == "missing":
        corpora["bn"]["clips"].pop()
    elif drift == "duplicate_id":
        corpora["bn"]["clips"][20]["id"] = corpora["bn"]["clips"][0]["id"]
    elif drift == "same_audio":
        corpora["bn"]["clips"][20]["sha256"] = corpora["bn"]["clips"][0]["sha256"]
    else:
        state["languages"][0]["inference_run"] = True
    with pytest.raises(ValueError):
        confirm.reserved_selection(state, corpora)


def test_failed_or_tampered_development_cannot_admit_confirmation():
    plan = probe.read(confirm.DEVELOPMENT / "comparison/plan.json")
    original = probe.read(confirm.DEVELOPMENT / "comparison/native/report.json")
    confirm.require_development(plan, original)
    for key in ("complete", "measurement_integrity", "control_reproduced"):
        report = deepcopy(original)
        report[key] = False
        with pytest.raises(ValueError):
            confirm.require_development(plan, report)
    report = deepcopy(original)
    report["cases"][0]["scores"]["word_errors"] = 0
    with pytest.raises(ValueError, match="scores changed"):
        confirm.require_development(plan, report)


def test_confirmation_freeze_checks_path_typed_caches_and_observed_prefix(tmp_path, monkeypatch):
    import json

    read = probe.read
    dev = deepcopy(read(confirm.DEVELOPMENT / "comparison/plan.json"))
    state = read(confirm.RESERVATION / "state.json")
    corpora = {r["corpus"]: read(confirm.RESERVATION / f"{r['language']}-corpus.json")
               for r in state["languages"]}
    pinned = {r["corpus"]: r["corpus_sha256"] for r in state["languages"]}
    for receipt in state["languages"]:
        lang = receipt["language"]
        journal = tmp_path / f"{lang}-observed.jsonl"
        journal.write_text("\n".join(json.dumps({
            "language": lang, "id": clip["id"], "model": dev["model_id"],
            "sha256": clip["sha256"], "reference": clip["reference"],
        }) for clip in corpora[receipt["corpus"]]["clips"][:20]), encoding="utf-8")
        for row in dev["clips"]:
            if row["language"] == lang:
                row.update(baseline_journal=str(journal), baseline_journal_sha256=digest(journal))

    def virtual_read(path):
        if Path(path) == confirm.DEVELOPMENT / "comparison/plan.json":
            return deepcopy(dev)
        return deepcopy(corpora[str(path)]) if str(path) in corpora else read(path)

    monkeypatch.setattr(probe, "read", virtual_read)
    monkeypatch.setattr(confirm, "digest", lambda path: pinned[str(path)] if str(path) in pinned else digest(path))
    monkeypatch.setattr(confirm, "claim_path", lambda: tmp_path / "claimed.json")
    monkeypatch.setattr("tools.asr_accuracy._source", lambda: dev["source"])
    monkeypatch.setattr("tools.latency_environment.runtime_environment", lambda: dev["runtime_environment"])
    receipts = [{"path": r["corpus"], "sha256": r["corpus_sha256"], "language": r["language"],
                 "clips": 40, "metadata_sha256": r["metadata_sha256"]} for r in state["languages"]]
    monkeypatch.setattr("tools.asr_accuracy.load_corpora", lambda paths: ([], receipts))
    checked = []

    def ready(descriptor, directory, *, check_hashes):
        checked.append((descriptor, directory))
        return isinstance(directory, Path) and check_hashes

    monkeypatch.setattr("saydraft.models.downloader.installation_ready", ready)
    original_state = tmp_path / "state.json"
    original_state.write_bytes((confirm.RESERVATION / "state.json").read_bytes())
    output = tmp_path / "confirmation"
    plan = confirm.freeze(original_state, output)
    assert len(checked) == 2 and len(plan["clips"]) == 60
    assert (output / "plan.json").exists() and not confirm.claim_path().exists()
    assert "selection_path" not in plan and plan["criteria"] == confirm.CRITERIA
    confirm.claim_path().write_text("existing consumption", encoding="utf-8")
    with pytest.raises(ValueError, match="already committed"):
        confirm.freeze(original_state, tmp_path / "cannot-reclaim")


def test_full_confirmation_requires_sixty_complete_pairs_and_each_language_gate():
    plan, _, _ = frozen_plan()
    rows = []
    for selected in plan["clips"]:
        for arm in probe.ARMS:
            rows.append({**selected, "arm": arm, "reference": "hello", "text": "hello",
                         "scores": {"word_errors": int(arm == "control"), "reference_words": 1,
                                    "character_errors": int(arm == "control"), "reference_characters": 5}})
    result = probe.summary_for_plan(plan, rows)
    assert result["confirmation_gate_met"] and "development_gate_met" not in result
    assert not probe.summary_for_plan(plan, rows[:-1])["confirmation_gate_met"]
    rows[-1]["scores"]["character_errors"] = 20  # Telugu ties, so the strict gate fails.
    assert not probe.summary_for_plan(plan, rows)["confirmation_gate_met"]
    rows[-1]["scores"]["character_errors"] = 0
    rows[-1]["text"] = "\ufffd"
    assert not probe.summary_for_plan(plan, rows)["confirmation_gate_met"]


def test_confirmation_parent_counts_120_cases_and_separate_repeat(tmp_path, monkeypatch):
    import json

    plan, _, _ = frozen_plan()
    monkeypatch.setattr(confirm, "claim_path", lambda: tmp_path / "claimed.json")
    plan["consumption_claim_path"] = str(confirm.claim_path())
    source = {"commit": "a" * 40, "dirty": False}
    environment = {"fixture": True}
    plan.update(source=source, runtime_environment=environment,
                producer_sha256=digest(probe.__file__),
                child_guard_sha256=digest(Path(probe.__file__).with_name("public_file_guard.py")))
    path = tmp_path / "plan.json"
    probe.write(path, plan)
    monkeypatch.setattr("tools.asr_accuracy._source", lambda: source)
    monkeypatch.setattr("tools.latency_environment.runtime_environment", lambda: environment)
    monkeypatch.setattr("saydraft.models.downloader.installation_ready", lambda *a, **k: True)
    launched = []

    class Job:
        def __init__(self, command, **kwargs):
            self.command = command
            self.pid = 1000 + len(launched)
            launched.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait_tree(self, timeout):
            assert timeout == 600
            command = self.command
            index = int(command[command.index("--index") + 1])
            arm = command[command.index("--arm") + 1]
            selected = plan["clips"][index]
            row = {**selected, "arm": arm, "reference": "hello", "text": "hello",
                   "scores": {"word_errors": 0, "reference_words": 1,
                              "character_errors": 0, "reference_characters": 5},
                   "decode_calls": [], "segments": []}
            output = Path(command[command.index("--output") + 1])
            output.mkdir()
            probe.write(output / "report.json", {
                "measurement_integrity": True, "native_pid": self.pid + 100, "cases": [row],
            })
            registration = json.loads((tmp_path / "native/consumption.json").read_bytes())
            assert registration["observed_cases_at_registration"] == 0
            assert len(registration["clips"]) == 60
            return 0

        def read_output(self, timeout):
            return b"owned test output"

    monkeypatch.setattr("saydraft.cleanup.llm.windows_process.WindowsJobProcess", Job)
    result = probe.run(path)
    assert result["complete"] and result["measurement_integrity"] and result["control_reproduced"]
    assert len(result["cases"]) == 120 and len(launched) == len(result["processes"]) == 121
    assert not result["comparison"]["confirmation_gate_met"]  # CER ties in this fixture.
    with pytest.raises(FileExistsError):
        probe.run(path)  # Consumption cannot silently restart in the same folder.
    with pytest.raises(FileExistsError):
        confirm.register_consumption(plan, {})  # A new output cannot reclaim the same set.
