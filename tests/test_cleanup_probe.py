import pytest

from tools.probe_cleanup_app import expected_outcomes


@pytest.mark.parametrize("normal,killed,passed", [
    (["incomplete", "timeout"], ["unavailable", "timeout"], True),
    (["timeout"], ["unavailable"], False),
    (["incomplete", "unavailable"], ["unavailable"], False),
    (["incomplete"], ["accepted"], False),
])
def test_probe_requires_stream_evidence_and_rejects_normal_protocol_failure(normal, killed, passed):
    cycles = [{"decision": decision, "termination_after_tokenization": False} for decision in normal]
    cycles += [{"decision": decision, "termination_after_tokenization": True} for decision in killed]
    assert bool(expected_outcomes(cycles)) is passed
