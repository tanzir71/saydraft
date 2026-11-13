import pytest

from tools.probe_firewall import run_probe
from saydraft.privacy.firewall_verification import frozen_smoke


@pytest.mark.parametrize("actions,environment", [("false", "github-hosted"), ("true", "self-hosted"), (None, None)])
def test_native_mutation_probe_refuses_owner_and_self_hosted_machines_before_creating_files(tmp_path, monkeypatch, actions, environment):
    for name, value in (("GITHUB_ACTIONS", actions), ("RUNNER_ENVIRONMENT", environment)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    output = tmp_path / "must-not-exist"
    with pytest.raises(RuntimeError, match="restricted to disposable"):
        run_probe(output)
    assert not output.exists()


def test_frozen_smoke_refuses_source_python_before_importing_speech_or_creating_files(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    with pytest.raises(RuntimeError, match="Frozen application required"):
        frozen_smoke(tmp_path / "missing-model", tmp_path)
    assert list(tmp_path.iterdir()) == []
