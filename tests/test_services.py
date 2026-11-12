import importlib
import sys
from pathlib import Path

from saydraft.config import default_config
from saydraft.core.container import create_services


def test_container_wires_local_services_with_separate_user_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    services = create_services(default_config())
    assert services.recorder.max_seconds == 1200
    assert services.asr.model_id == "parakeet-tdt-0-6b-v3-int8"
    assert services.processor.history is services.history
    assert services.processor.cleaner is services.cleaner
    assert services.processor.inserter is services.inserter
    assert services.context.profiles is services.profiles
    assert services.inserter.focus_provider == services.context.focus
    assert services.context._use_uia == (sys.platform == "win32")
    assert services.processor.voice_enter_enabled is False
    assert services.history.db_path == tmp_path / "Saydraft/history.db"
    assert services.cleaner.cfg.glossary_path == str(tmp_path / "Saydraft/glossary.json")


def test_container_preserves_explicit_whisper_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    config = default_config()
    from saydraft.asr.selection import select_model

    select_model(config, "whisper-small")
    config["dictation"]["drop_message_period"] = False
    config["dictation"]["voice_enter_enabled"] = True
    services = create_services(config)
    assert services.asr.config.local_files_only
    assert services.asr.config.model_size == "small"
    assert services.cleaner.cfg.drop_message_period is False
    assert services.processor.voice_enter_enabled is True


def test_runtime_does_not_depend_on_retired_worker():
    import saydraft.app

    assert hasattr(saydraft.app, "WorkerController")
    retired_name = "legacy" + "_app"
    root = Path(__file__).resolve().parents[1] / "saydraft"
    assert not (root / f"{retired_name}.py").exists()
    assert importlib.util.find_spec(f"saydraft.{retired_name}") is None


def test_malformed_profile_fields_and_snippets_do_not_disable_dictation(tmp_path):
    from saydraft.core.preferences import read_snippets, select_context

    context = select_context(default_config(), [{"match": "Notepad", "mode": [], "profile": 123}], "Notepad")
    assert (context.mode, context.profile) == ("balanced", "general")
    snippets = tmp_path / "snippets.txt"
    snippets.write_bytes(b"\xff\xfe\xff")
    assert read_snippets(snippets) == {}
