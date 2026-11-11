from pathlib import Path


def _script_text(name: str) -> str:
    return Path(name).read_text(encoding="utf-8").lower()


def test_run_app_uses_pythonw_module_entrypoint_without_console_pause():
    script = _script_text("run_app.bat")

    assert "pythonw -m saydraft" in script
    assert "speech_to_text_app.py" not in script
    assert " pause" not in script
    assert "start" not in script


def test_run_debug_uses_console_python_with_verbose_logging():
    script = _script_text("run_debug.bat")

    assert "set saydraft_log_level=debug" in script
    assert "set saydraft_log_console=1" in script
    assert "python -m saydraft" in script
    assert "pythonw" not in script
    assert "pause" in script
