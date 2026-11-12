import ctypes as c
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes as w
from pathlib import Path

import pytest

from saydraft.cleanup.llm.windows_process import WindowsJobProcess, _environment

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Native Windows Job Object contract")


def environment():
    return {key: value for key, value in os.environ.items() if key.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")}


def kernel():
    api = c.WinDLL("kernel32", use_last_error=True)
    for name, result, args in [
        ("OpenProcess", w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
        ("WaitForSingleObject", w.DWORD, [w.HANDLE, w.DWORD]),
        ("TerminateProcess", w.BOOL, [w.HANDLE, w.UINT]),
        ("CloseHandle", w.BOOL, [w.HANDLE]),
        ("IsProcessInJob", w.BOOL, [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)]),
    ]:
        function = getattr(api, name)
        function.restype, function.argtypes = result, args
    return api


def wait_file(path):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.01)
    pytest.fail("Fixture process did not publish its ready data")


def test_hidden_process_uses_literal_unicode_arguments_and_explicit_environment(tmp_path):
    result = tmp_path / "arguments output.json"
    script = "import ctypes,json,os,sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps({'args':sys.argv[2:],'custom':os.getenv('SAYDRAFT_FIXTURE'),'console':ctypes.windll.kernel32.GetConsoleWindow(),'input':sys.stdin.read()}),encoding='utf-8')"
    arguments = ["বাংলা العربية", 'literal "quote" and trailing\\', "$(literal) & `literal` ;"]
    with WindowsJobProcess([sys.executable, "-c", script, str(result), *arguments],
                           env={**environment(), "SAYDRAFT_FIXTURE": "explicit value"}) as process:
        in_job = w.BOOL()
        assert kernel().IsProcessInJob(process._process, process._job, c.byref(in_job)) and in_job.value
        assert process.wait(5) == 0
    info = json.loads(result.read_text(encoding="utf-8"))
    assert info == {"args": arguments, "custom": "explicit value", "console": 0, "input": ""}


def test_poll_wait_timeout_terminate_and_valid_exit_code_259():
    with WindowsJobProcess([sys.executable, "-c", "import time; time.sleep(60)"], env=environment()) as process:
        assert process.poll() is None
        with pytest.raises(TimeoutError):
            process.wait(0.001)
        process.terminate()
        assert process.wait(5) == 1
    with WindowsJobProcess([sys.executable, "-c", "import sys; sys.exit(259)"], env=environment()) as process:
        assert process.wait(5) == process.poll() == 259
    process.close()  # Idempotent; never closes a recycled handle.


def test_job_closure_terminates_child_and_its_descendant(tmp_path):
    ready = tmp_path / "descendant.json"
    script = "import json,os,subprocess,sys,time; from pathlib import Path; child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW); Path(sys.argv[1]).write_text(json.dumps({'pid':child.pid})); time.sleep(60)"
    process = WindowsJobProcess([sys.executable, "-c", script, str(ready)], env=environment())
    api, handle = kernel(), None
    try:
        child = wait_file(ready)["pid"]
        handle = api.OpenProcess(0x100001, False, child)  # SYNCHRONIZE | PROCESS_TERMINATE, fixture only.
        assert handle
        process.terminate()
        assert process.wait(5) == 1
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        process.close()
        if handle:
            api.TerminateProcess(handle, 1)
            api.CloseHandle(handle)


def test_abrupt_owner_exit_closes_job_without_python_cleanup(tmp_path):
    ready, release = tmp_path / "owned-child.json", tmp_path / "release-owner"
    source = "from saydraft.cleanup.llm.windows_process import WindowsJobProcess; import json,os,sys,time; from pathlib import Path; env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP')}; child=WindowsJobProcess([sys.executable,'-c','import time;time.sleep(60)'],env=env); Path(sys.argv[1]).write_text(json.dumps({'pid':child.pid}));\nwhile not Path(sys.argv[2]).exists(): time.sleep(.01)\nos._exit(0)"
    owner = subprocess.Popen([sys.executable, "-c", source, str(ready), str(release)],
        cwd=Path(__file__).resolve().parents[1], env=environment(), creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    api, handle = kernel(), None
    try:
        handle = api.OpenProcess(0x100001, False, wait_file(ready)["pid"])
        assert handle and api.WaitForSingleObject(handle, 0) == 258
        release.write_text("exit", encoding="utf-8")
        assert owner.wait(timeout=5) == 0
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        if handle:
            api.TerminateProcess(handle, 1)
            api.CloseHandle(handle)


def test_explicit_job_close_kills_a_running_process_and_is_idempotent():
    process = WindowsJobProcess([sys.executable, "-c", "import time; time.sleep(60)"], env=environment())
    api = kernel()
    handle = api.OpenProcess(0x100001, False, process.pid)
    assert handle
    try:
        process.close()
        process.close()
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        process.close()
        api.TerminateProcess(handle, 1)
        api.CloseHandle(handle)


@pytest.mark.parametrize("values", [{"A": "one", "a": "two"}, {"bad=name": "value"}, {"valid": "bad\0value"}])
def test_invalid_environment_is_rejected_without_launch(values):
    with pytest.raises(ValueError):
        _environment(values)


def test_failed_native_creation_does_not_leave_owner_handles_open(tmp_path):
    invalid = tmp_path / "invalid-image.exe"
    invalid.write_text("fixture, not a PE executable", encoding="utf-8")
    # Process-wide counts cannot attribute handles opened by concurrent Qt/native
    # test workers. Keep the same zero-growth assertion in a quiet child process.
    code = """
import ctypes as c
import json, os, sys
from ctypes import wintypes as w
from saydraft.cleanup.llm.windows_process import WindowsJobProcess
api = c.WinDLL('kernel32', use_last_error=True)
api.GetCurrentProcess.restype = w.HANDLE
api.GetProcessHandleCount.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
env = {k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP')}
def attempt():
    try:
        WindowsJobProcess([sys.argv[1]], env=env)
    except OSError:
        return
    raise AssertionError('Invalid executable unexpectedly launched')
attempt()  # Exclude one-time Windows loader initialization.
before, after = w.DWORD(), w.DWORD()
assert api.GetProcessHandleCount(api.GetCurrentProcess(), c.byref(before))
for _ in range(10):
    attempt()
assert api.GetProcessHandleCount(api.GetCurrentProcess(), c.byref(after))
print(json.dumps([before.value, after.value]))
"""
    result = subprocess.run([sys.executable, "-c", code, str(invalid)], env=environment(),
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10, check=True)
    before, after = json.loads(result.stdout)
    assert after <= before
