import pytest

from tools.probe_firewall import run_probe


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
