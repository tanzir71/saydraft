import subprocess
import sys
import json
from pathlib import Path

import pytest

def test_eval_corpus_has_required_size_and_coverage():
    from saydraft.eval import DEFAULT_CORPUS_PATH, load_eval_corpus

    cases = load_eval_corpus(DEFAULT_CORPUS_PATH)

    assert len(cases) >= 286
    assert {case.mode for case in cases} >= {"raw", "balanced", "aggressive"}
    assert {case.profile for case in cases} >= {"general", "email", "chat", "notes", "code/comments"}
    assert all(case.input_text.strip() for case in cases)
    assert all(case.expected.strip() for case in cases)


def test_eval_harness_default_corpus_meets_ci_target():
    from saydraft.eval import DEFAULT_CORPUS_PATH, DEFAULT_MIN_PASS_RATE, load_eval_corpus, run_eval

    result = run_eval(load_eval_corpus(DEFAULT_CORPUS_PATH))

    assert result.pass_rate >= DEFAULT_MIN_PASS_RATE
    assert result.failed == 0


def test_eval_cli_prints_pass_rate_and_exits_zero():
    root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "-m", "saydraft.eval"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Pass rate:" in result.stdout
    assert "passed" in result.stdout


def write_cases(tmp_path, rows):
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_full_app_context_reaches_actual_code_path_and_injected_pipeline(tmp_path):
    from saydraft.eval import load_eval_corpus, run_eval

    row = {"id": "code-context", "input": "two files", "expected": "two files", "mode": "aggressive",
           "profile": "general", "intensity": 2, "app_title": "Editor", "app_group": "code",
           "before_caret": "x = ", "language": "bn"}
    cases = load_eval_corpus(write_cases(tmp_path, [row]))
    assert run_eval(cases).passed == 1  # Ignoring app_group would produce prose/ITN edits.
    contexts = []

    class Capture:
        def process_transcript(self, text, context):
            contexts.append(context)
            return text

    assert run_eval(cases, Capture()).passed == 1
    context = contexts[0]
    assert (context.app_title, context.app_group, context.before_caret, context.language, context.intensity) == (
        "Editor", "code", "x = ", "bn", 2)


@pytest.mark.parametrize("changes", [
    {"id": ""}, {"input": 2}, {"expected": None}, {"mode": "unknown"}, {"profile": "unknown"},
    {"intensity": True}, {"intensity": 0}, {"intensity": 5}, {"app_group": []}, {"before_caret": None},
    {"app_goup": "code"},
])
def test_malformed_or_silently_ignored_context_is_rejected(tmp_path, changes):
    from saydraft.eval import load_eval_corpus

    row = {"id": "fixture", "input": "words", "expected": "Words", **changes}
    with pytest.raises(ValueError):
        load_eval_corpus(write_cases(tmp_path, [row]))


def test_duplicate_ids_examples_fields_and_empty_corpora_cannot_inflate_acceptance(tmp_path):
    from saydraft.eval import load_eval_corpus

    row = {"id": "fixture", "input": "words", "expected": "Words"}
    for rows in ([row, {**row, "input": "different"}], [row, {**row, "id": "other"}], []):
        with pytest.raises(ValueError):
            load_eval_corpus(write_cases(tmp_path, rows))
    path = tmp_path / "duplicate-field.jsonl"
    path.write_text('{"id":"fixture","input":"first","input":"second","expected":"Words"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate field"):
        load_eval_corpus(path)


def test_case_count_and_threshold_are_enforced_while_small_custom_evals_remain_available(tmp_path):
    from saydraft.eval import main

    path = write_cases(tmp_path, [{"id": "empty-raw", "input": "", "expected": "", "mode": "raw", "intensity": 0}])
    assert main(["--corpus", str(path), "--min-pass-rate", "100"]) == 0
    assert main(["--corpus", str(path), "--min-cases", "2"]) == 1
    for arguments in (["--min-cases", "0"], ["--min-pass-rate", "nan"], ["--min-pass-rate", "101"]):
        with pytest.raises(SystemExit) as caught:
            main(arguments)
        assert caught.value.code == 2

