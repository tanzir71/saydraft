"""Foreground metadata is bounded, stable and independent of browser/network access."""

import ctypes as ct
import subprocess
import sys
from ctypes import wintypes as wt
from types import SimpleNamespace

import pytest

from saydraft.context.app_groups import app_group, browser_site
from saydraft.context.foreground import ForegroundContextProvider, NativeForegroundApi
from saydraft.core.interfaces import TargetContext


class Api:
    def foreground(self):
        return 123

    def window_pid(self, window):
        assert window == 123
        return 42

    def title(self, window, pid):
        assert (window, pid) == (123, 42)
        return "Inbox - Gmail - Google Chrome"

    def executable(self, pid):
        assert pid == 42
        return "chrome.exe"


def test_capture_enriches_stable_context_and_focus_checks_do_not_enrich():
    api = Api()
    provider = ForegroundContextProvider(api=api)
    assert provider.capture() == TargetContext(focus=123, app_title="Inbox - Gmail - Google Chrome",
        app_exe="chrome.exe", app_group="email", app_site="mail.google.com", process_id=42)
    api.window_pid = lambda window: pytest.fail("A delivery focus check must not enrich context")
    assert provider.focus() == 123


@pytest.mark.parametrize("field,values", [("foreground", [123, 456]), ("window_pid", [42, 43])])
def test_capture_refuses_mixed_window_or_process_generations(field, values):
    api, calls = Api(), iter(values)
    setattr(api, field, lambda *args: next(calls))
    assert ForegroundContextProvider(api=api).capture() == TargetContext()


def test_unknown_image_keeps_stable_target_without_guessing_a_group_from_title():
    api = Api()
    def denied(pid):
        raise OSError("Fixture access denied")
    api.executable = denied
    target = ForegroundContextProvider(api=api).capture()
    assert target.focus == 123 and target.app_title and target.app_group == "general"
    assert target.app_exe == target.app_site == ""


@pytest.mark.parametrize("field", ["foreground", "window_pid", "title"])
def test_unavailable_foreground_returns_unknown_context(field):
    api = Api()
    def gone(*args):
        raise OSError("Fixture target disappeared")
    setattr(api, field, gone)
    assert ForegroundContextProvider(api=api).capture() == TargetContext()


def test_no_foreground_never_queries_pid_or_image():
    api = Api()
    api.foreground = lambda: 0
    assert ForegroundContextProvider(api=api).capture() == TargetContext()


def test_non_windows_adapter_is_inert_without_loading_native_libraries(monkeypatch):
    import saydraft.context.foreground as module
    monkeypatch.setattr(module.sys, "platform", "other")
    monkeypatch.setattr(module, "NativeForegroundApi", lambda: pytest.fail("No native load"))
    provider = ForegroundContextProvider()
    assert provider.capture() == TargetContext() and provider.focus() is None


@pytest.mark.parametrize("exe,group", [("Telegram.exe", "messages"), ("MS-Teams.exe", "work_chat"),
    ("OUTLOOK.EXE", "email"), ("C:\\Apps\\Obsidian.exe", "docs"), ("Code.exe", "code"),
    ("Claude.exe", "ai_chat"), ("unknown.exe", "general")])
def test_executable_defaults_are_case_insensitive_and_exact(exe, group):
    assert app_group(exe) == group
    assert app_group(exe + ".spoof") == "general"


@pytest.mark.parametrize("exe,title,site,group", [
    ("chrome.exe", "Draft - Gmail - Google Chrome", "mail.google.com", "email"),
    ("msedge.exe", "Team | Slack — Microsoft Edge", "slack.com", "work_chat"),
    ("firefox.exe", "Draft – Google Docs — Mozilla Firefox", "docs.google.com", "docs"),
    ("chrome.exe", "ChatGPT - Google Chrome", "chatgpt.com", "ai_chat"),
    ("chrome.exe", "chat.example.org - Google Chrome", "chat.example.org", "general"),
    ("chrome.exe", "How to use Gmail - Google Chrome", "", "general"),
    ("chrome.exe", "Draft - Gmail - Mozilla Firefox", "", "general"),
    ("other.exe", "Draft - Gmail - Google Chrome", "", "general"),
    ("chrome.exe", "Gmail", "", "general"),
    ("chrome.exe", "x" * 4097, "", "general"),
])
def test_browser_hints_require_browser_identity_and_final_title_segment(exe, title, site, group):
    assert browser_site(exe, title) == site
    assert app_group(exe, site) == group


def test_group_overrides_use_first_valid_exact_exe_and_site_match():
    profiles = [None, {"exe": "chrome.exe", "app_group": []},
        {"app_group": "code"}, {"match": "Gmail", "app_group": "code"},
        {"exe": "C:\\Apps\\chrome.exe", "app_group": "code"},
        {"exe": "chrome.exe", "site": "other.example.org", "app_group": "code"},
        {"exe": "CHROME.EXE", "site": "MAIL.GOOGLE.COM", "app_group": "general"},
        {"exe": "chrome.exe", "app_group": "code"}]
    assert app_group("chrome.exe", "mail.google.com", profiles) == "general"
    assert app_group("chrome.exe", "", profiles) == "code"
    assert app_group("outlook.exe", "", profiles) == "email"
    assert app_group("chrome.exe", "", [{}] * 128 + profiles) == "general"


def test_provider_uses_user_overrides_without_changing_the_legacy_profile():
    provider = ForegroundContextProvider(api=Api(), profiles=[{"site": "mail.google.com", "app_group": "code"}])
    assert provider.capture().app_group == "code"


@pytest.mark.parametrize("succeeds,length", [(True, 20), (False, 0), (True, 32768)])
def test_image_query_owns_only_a_limited_process_handle_and_closes_on_failure(succeeds, length):
    opened, closed = [], []
    api = NativeForegroundApi.__new__(NativeForegroundApi)
    def query(handle, flags, buffer, size):
        assert handle == 999 and flags == 0 and ct.cast(size, ct.POINTER(wt.DWORD))[0] == 32768
        buffer.value = r"C:\Public\Chrome.exe"
        ct.cast(size, ct.POINTER(wt.DWORD))[0] = length
        return succeeds
    api.kernel = SimpleNamespace(OpenProcess=lambda *args: opened.append(args) or 999,
        QueryFullProcessImageNameW=query, CloseHandle=lambda handle: closed.append(handle) or True)
    if succeeds and length < 32768:
        assert api.executable(42) == "chrome.exe"
    else:
        with pytest.raises(OSError):
            api.executable(42)
    assert opened == [(0x1000, False, 42)] and closed == [999]


def test_image_open_failure_never_closes_an_unowned_handle_and_own_title_sends_no_gui_message():
    api = NativeForegroundApi.__new__(NativeForegroundApi)
    api.kernel = SimpleNamespace(OpenProcess=lambda *args: 0, GetCurrentProcessId=lambda: 42,
        CloseHandle=lambda handle: pytest.fail("No handle was acquired"))
    api.user = SimpleNamespace(GetWindowTextW=lambda *args: pytest.fail("No same-process GUI message"))
    with pytest.raises(OSError):
        api.executable(42)
    assert api.title(123, 42) == ""


def test_foreign_caption_has_a_fixed_buffer_and_no_length_based_allocation():
    api = NativeForegroundApi.__new__(NativeForegroundApi)
    api.kernel = SimpleNamespace(GetCurrentProcessId=lambda: 99)
    def title(window, buffer, maximum):
        assert window == 123 and maximum == len(buffer) == 4097
        buffer.value = "Public window title"
        return len(buffer.value)
    api.user = SimpleNamespace(GetWindowTextW=title)
    assert api.title(123, 42) == "Public window title"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process-image API required")
def test_native_own_process_image_queries_have_no_handle_growth_in_a_quiet_child():
    # A quiet child avoids unrelated audio/Qt/background-test handle fluctuations.
    script = '''
import ctypes as ct, os
from ctypes import wintypes as wt
from saydraft.context.foreground import NativeForegroundApi
api=NativeForegroundApi()
api.kernel.GetCurrentProcess.restype=wt.HANDLE
api.kernel.GetProcessHandleCount.argtypes=[wt.HANDLE,ct.POINTER(wt.DWORD)]
api.kernel.GetProcessHandleCount.restype=wt.BOOL
process=api.kernel.GetCurrentProcess()
def count():
    value=wt.DWORD()
    assert api.kernel.GetProcessHandleCount(process,ct.byref(value))
    return value.value
assert api.executable(os.getpid()).endswith('.exe')
before=count()
for _ in range(50):
    assert api.executable(os.getpid()).endswith('.exe')
assert count()==before
'''
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, timeout=30)
