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


def test_native_probe_forwards_full_cycle_count_and_recipe_to_the_shared_runner(monkeypatch):
    from tools import probe_cleanup_app

    observed = []
    monkeypatch.setattr(probe_cleanup_app, 'soak_main', lambda arguments: observed.extend(arguments) or 7)
    assert probe_cleanup_app.main(['--runtime-dir', 'runtime', '--model', 'fixture.gguf', '--output', 'qa',
        '--cycles', '200', '--isolated', '--fixture-context-override']) == 7
    assert observed[observed.index('--cycles')+1] == '200'
    assert '--isolated' in observed and '--fixture-context-override' in observed
