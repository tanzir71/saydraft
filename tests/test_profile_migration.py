import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

from saydraft.autostart import WindowsAutoStartManager
from saydraft.compat.migrate import LEGACY_NAME, MARKER_NAME, migrate_autostart, migrate_profile


def profile_fixture(tmp_path):
    source = tmp_path / LEGACY_NAME
    source.mkdir()
    with sqlite3.connect(source / "history.db") as conn:
        conn.execute("CREATE TABLE dictations (raw_text TEXT, cleaned_text TEXT)")
        conn.execute("INSERT INTO dictations VALUES (?, ?)", ("um hello", "Hello"))
    conn.close()
    (source / "config.json").write_text('{"schema_version":1}', encoding="utf-8")
    (source / "glossary.json").write_text('{"user_terms":["Kubernetes"]}', encoding="utf-8")
    (source / "models").mkdir()
    (source / "models/weights.bin").write_bytes(b"model fixture")
    (source / "history.db-wal").write_bytes(b"wal fixture")
    return source


def snapshot(path):
    return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob("*") if file.is_file()}


def test_profile_copy_preserves_all_original_bytes_and_is_idempotent(tmp_path):
    source = profile_fixture(tmp_path)
    before = snapshot(source)
    assert migrate_profile(tmp_path)
    target = tmp_path / "Saydraft"
    assert snapshot(source) == before
    copied = snapshot(target)
    assert all(copied[name] == content for name, content in before.items())
    assert MARKER_NAME in copied
    assert not migrate_profile(tmp_path)
    assert snapshot(target) == copied


def test_partial_copy_resumes_without_overwriting_edits(tmp_path, monkeypatch):
    import saydraft.compat.migrate as migration

    source = profile_fixture(tmp_path)
    before = snapshot(source)
    original_copy = migration.shutil.copy2
    count = 0

    def interrupted_copy(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("simulated interrupted copy")
        return original_copy(*args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(migration.shutil, "copy2", interrupted_copy)
        with pytest.raises(OSError, match="interrupted"):
            migrate_profile(tmp_path)
    (tmp_path / "Saydraft/config.json").write_text("newer configuration", encoding="utf-8")
    assert migrate_profile(tmp_path)
    assert (tmp_path / "Saydraft/config.json").read_text() == "newer configuration"
    assert (tmp_path / "Saydraft/history.db").read_bytes() == before["history.db"]
    assert snapshot(source) == before


def test_independent_new_profile_is_not_filled_from_old_profile(tmp_path):
    profile_fixture(tmp_path)
    (tmp_path / "Saydraft").mkdir()
    (tmp_path / "Saydraft/config.json").write_text("independent profile", encoding="utf-8")
    assert not migrate_profile(tmp_path)
    assert (tmp_path / "Saydraft/config.json").read_text() == "independent profile"


def test_running_old_process_prevents_copy(tmp_path):
    source = profile_fixture(tmp_path)
    (source / "voicetray.lock").write_text(json.dumps({"pid": os.getpid()}))
    with pytest.raises(RuntimeError, match="Close VoiceTray"):
        migrate_profile(tmp_path)
    assert not (tmp_path / "Saydraft").exists()


class Registry:
    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self, command):
        self.values = {LEGACY_NAME: command, "Unrelated": "do not change"}

    def CreateKey(self, *args):
        return "key"

    def QueryValueEx(self, key, name):
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, command):
        self.values[name] = command

    def DeleteValue(self, key, name):
        del self.values[name]

    def CloseKey(self, key):
        pass


@pytest.mark.parametrize("managed", [True, False])
def test_autostart_migration_recognizes_only_app_created_commands(managed):
    old = f'"{Path(sys.executable).with_name("pythonw.exe")}" -m voicetray'
    registry = Registry(old if managed else '"C:\\Owner Scripts\\custom.exe"')
    before = dict(registry.values)
    manager = WindowsAutoStartManager(registry=registry, platform="win32", command="new command")
    assert migrate_autostart(manager) is managed
    if managed:
        assert registry.values == {"Saydraft": "new command", "Unrelated": "do not change"}
    else:
        assert registry.values == before


def test_compatibility_launcher_delegates_to_new_main(monkeypatch, caplog):
    import logging
    import runpy
    import saydraft.main

    monkeypatch.setattr(saydraft.main, "main", lambda: 27)
    monkeypatch.setattr(logging.getLogger("saydraft"), "propagate", True)
    with pytest.raises(SystemExit) as result:
        runpy.run_module("voicetray", run_name="__main__")
    assert result.value.code == 27
    assert "use python -m saydraft" in caplog.text
