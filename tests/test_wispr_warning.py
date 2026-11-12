"""Snapshot lifetime and advisory clash detection, without controlling processes."""

import ctypes as ct
from types import SimpleNamespace

import pytest

from saydraft.hotkeys.wispr import ProcessEntry, shortcut_warning, wispr_running


def snapshot(names, *, error=18, invalid=False):
    names, closed = iter(names), []
    def create(flags, process):
        assert (flags, process) == (2, 0)
        return ct.c_void_p(-1).value if invalid else 123
    def read(handle, pointer):
        assert handle == 123 and pointer._obj.dwSize == ct.sizeof(ProcessEntry)
        try:
            pointer._obj.szExeFile = next(names)
            return True
        except StopIteration:
            ct.set_last_error(error)
            return False
    def close(handle):
        closed.append(handle)
        return True
    return SimpleNamespace(CreateToolhelp32Snapshot=create, Process32FirstW=read,
                           Process32NextW=read, CloseHandle=close), closed


@pytest.mark.parametrize("names, expected", [([], False), (["Wispr Flow.exe"], True),
    (["unrelated.exe", "WISPR FLOW.EXE", "later.exe"], True),
    (["Wispr Flow helper.exe", "Wispr Flow.exe.old", "notepad.exe"], False)])
def test_snapshot_matches_exact_name_and_closes_on_found_and_exhausted(names, expected):
    kernel, closed = snapshot(names)
    assert wispr_running(kernel=kernel) is expected
    assert closed == [123]
    if ct.sizeof(ct.c_void_p) == 8:
        assert ct.sizeof(ProcessEntry) == 568


def test_unavailable_or_partial_snapshot_is_unknown_and_closes_only_valid_handle():
    kernel, closed = snapshot([], invalid=True)
    assert wispr_running(kernel=kernel) is None and not closed
    kernel, closed = snapshot(["unrelated.exe"], error=5)
    assert wispr_running(kernel=kernel) is None and closed == [123]


def test_advisory_checks_ctrl_win_prefix_aliases_and_sides_without_scanning_unrelated_chords():
    calls = []
    def running():
        calls.append(True)
        return True
    for chord in ("Control + Windows", "right_win+left_ctrl", "ctrl+win+space"):
        assert "may also use Ctrl+Win" in shortcut_warning({"speech": chord}, detector=running)
    assert len(calls) == 3
    assert not shortcut_warning({"speech": "f9", "speech_mouse": "xbutton1"}, detector=running)
    assert not shortcut_warning({"speech": "invalid"}, detector=running)
    assert len(calls) == 3
    for state in (False, None):
        assert not shortcut_warning({"save": "ctrl+win+s"}, detector=lambda: state)


def test_settings_warning_is_advisory_refreshes_and_tracks_unsaved_rebinding(monkeypatch, tmp_path):
    from tests.test_settings_window import make_window
    calls = []
    def running():
        calls.append(True)
        return True
    monkeypatch.setattr("saydraft.ui.settings_page.wispr_running", running)
    window, path, _autostart = make_window(tmp_path)
    before = path.read_bytes()
    assert "Wispr Flow is running" in window.shortcut_warning_label.text()
    count = len(calls)
    window.speech_hotkey_edit.setText("f8")
    assert "Wispr Flow is running" in window.shortcut_warning_label.text() and len(calls) == count
    window.hands_free_hotkey_edit.setText("ctrl+alt+h")
    assert not window.shortcut_warning_label.text() and len(calls) == count
    assert path.read_bytes() == before
    assert window.apply_changes()
    assert len(calls) > count
    window.close()


def test_native_listening_notifies_about_possible_wispr_clash_without_blocking(monkeypatch):
    from saydraft.config import default_config
    from saydraft.core.hotkey_service import HotkeyService
    from tests.test_native_recording import factory
    create, _owners = factory()
    notices = []
    monkeypatch.setattr("saydraft.core.hotkey_service.shortcut_warning", lambda config: "Possible Wispr clash")
    service = HotkeyService(default_config(), start=lambda: None, stop=lambda: None,
        cancel=lambda: None, save=lambda: None, notify=notices.append, native_factory=create)
    service.start()
    assert service.enabled and notices == ["Possible Wispr clash"]
    assert service.stop()
