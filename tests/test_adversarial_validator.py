import json

import pytest

from saydraft.cleanup.llm.eval_validation import evaluate, load_cases, main
from saydraft.cleanup.llm.validate import validate_llm_output

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_checked_in_adversarial_candidate_is_refused(case):
    result = validate_llm_output(case["input"], case["candidate"], mode=case["mode"])
    assert not result.ok, (case["id"], result.reason)


def test_adversarial_acceptance_is_complete_and_ci_command_enforces_count_and_threshold(tmp_path):
    report = evaluate(CASES)
    assert report["total"] == report["caught"] == 100 and report["catch_rate"] == 100
    assert len(report["by_category"]) == 10
    assert main([]) == 0
    corpus = tmp_path / "small.jsonl"
    corpus.write_text(json.dumps(CASES[0]) + "\n", encoding="utf-8")
    assert main(["--corpus", str(corpus)]) == 1  # Cannot pass with a shrunk set.
    row = {**CASES[0], "candidate": CASES[0]["input"]}
    corpus.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert main(["--corpus", str(corpus), "--min-cases", "1"]) == 1


def test_empty_or_duplicate_ids_cannot_inflate_adversarial_acceptance(tmp_path):
    corpus = tmp_path / "invalid.jsonl"
    corpus.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_cases(corpus)
    corpus.write_text((json.dumps(CASES[0]) + "\n") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(corpus)
