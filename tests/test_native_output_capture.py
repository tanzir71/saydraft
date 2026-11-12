import os
import sys
import time

import pytest

from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from tests.test_sidecar_process import environment, kernel

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native probe ownership")


def test_probe_captures_both_streams_without_inheriting_stdin_or_environment(monkeypatch):
    monkeypatch.setenv("SAYDRAFT_PRIVATE", "fixture value that must not be inherited")
    script = "import os,sys; assert sys.stdin.read()==''; assert os.getenv('SAYDRAFT_PRIVATE') is None; os.write(1,b'probe stdout\\n'); os.write(2,b'probe stderr\\n')"
    with WindowsJobProcess([sys.executable, "-c", script], env=environment(), capture_output=True) as process:
        assert process.wait(5) == 0
        assert process.read_output() == b"probe stdout\nprobe stderr\n"
    assert not process._reader.is_alive()


def test_inference_default_still_discards_output():
    with WindowsJobProcess([sys.executable, "-c", "print('discarded')"], env=environment()) as process:
        assert process.wait(5) == 0
        with pytest.raises(RuntimeError, match="disabled"):
            process.read_output()
    assert process._reader is None


def test_flooding_probe_is_terminated_at_the_buffer_bound():
    script = "import os,time; os.write(1,b'x'*1000000); time.sleep(60)"
    with WindowsJobProcess([sys.executable, "-c", script], env=environment(), capture_output=True,
                           max_output_bytes=1024) as process:
        assert process.wait(5) != 0
        with pytest.raises(OSError, match="exceeded"):
            process.read_output()
        assert len(process._output) <= 1024
    assert not process._reader.is_alive()


def test_closing_a_stuck_probe_kills_it_and_unblocks_the_pipe_reader():
    process = WindowsJobProcess([sys.executable, "-c", "import time; time.sleep(60)"],
                                env=environment(), capture_output=True)
    api = kernel()
    handle = api.OpenProcess(0x100001, False, process.pid)
    assert handle
    try:
        with pytest.raises(TimeoutError):
            process.read_output(.001)
        started = time.monotonic()
        process.close()
        assert time.monotonic() - started < 2
        assert api.WaitForSingleObject(handle, 5000) == 0
        assert not process._reader.is_alive()
        process.close()
    finally:
        process.close()
        api.TerminateProcess(handle, 1)
        api.CloseHandle(handle)


def test_failed_probe_creation_closes_pipe_handles(tmp_path):
    import ctypes as c
    from ctypes import wintypes as w

    api = kernel()
    api.GetCurrentProcess.restype = w.HANDLE
    api.GetProcessHandleCount.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    invalid = tmp_path / "invalid.exe"
    invalid.write_bytes(b"not an executable")
    with pytest.raises(OSError):  # Exclude one-time Windows invalid-image loader initialization.
        WindowsJobProcess([str(invalid)], env=environment(), capture_output=True)
    before, after = w.DWORD(), w.DWORD()
    assert api.GetProcessHandleCount(api.GetCurrentProcess(), c.byref(before))
    for _ in range(10):
        with pytest.raises(OSError):
            WindowsJobProcess([str(invalid)], env=environment(), capture_output=True)
    assert api.GetProcessHandleCount(api.GetCurrentProcess(), c.byref(after))
    assert after.value <= before.value


def test_exception_after_reader_thread_starts_does_not_leak_a_reader_or_child(monkeypatch):
    import threading

    api, observed = kernel(), {}
    original = threading.Thread.start
    def fail_after_start(thread):
        if thread.name == "Saydraft-native-metadata":
            process = thread._target.__self__
            observed["handle"] = api.OpenProcess(0x100001, False, process.pid)
            observed["thread"] = thread
            original(thread)
            raise RuntimeError("injected thread adoption failure")
        original(thread)
    monkeypatch.setattr(threading.Thread, "start", fail_after_start)
    try:
        with pytest.raises(RuntimeError, match="adoption failure"):
            WindowsJobProcess([sys.executable, "-c", "import time;time.sleep(60)"],
                              env=environment(), capture_output=True)
        assert observed["handle"] and api.WaitForSingleObject(observed["handle"], 5000) == 0
        observed["thread"].join(1)
        assert not observed["thread"].is_alive()
    finally:
        if observed.get("handle"):
            api.TerminateProcess(observed["handle"], 1)
            api.CloseHandle(observed["handle"])
