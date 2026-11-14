import ctypes as c
from ctypes import wintypes as w
import os
import sys
import time
import weakref

import pytest

from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from saydraft.meetings.process import CaptureProcess, capture_command
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.stop import StopEvent

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Owned Windows event, pipe and Job Object contract')

# This child intentionally cannot import either real audio backend or the app.
# Generated PCM exercises the production capture loop/transport, not devices.
CHILD = '''
import importlib.abc, os, sys, time
class NoOwnerAudio(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('sounddevice','soundcard') or fullname in ('saydraft.app','saydraft.compat.migrate'):
            raise AssertionError('Native fixture must not reach owner audio or application services')
sys.meta_path.insert(0, NoOwnerAudio())
from saydraft.privacy.netguard import NetworkGuard, NetworkBlockedError
from saydraft.privacy.telemetry import configure_process_privacy
NetworkGuard.install()
configure_process_privacy()
import numpy as np
import socket
from saydraft.meetings.child import run_capture, open_capture_output, REQUEST_ENV
from saydraft.meetings.request import CaptureRequest
from saydraft.meetings.stop import StopEvent
request = CaptureRequest.from_json(os.environ.pop(REQUEST_ENV))
mode = sys.argv[2]
class Reader:
    def __enter__(self): return self
    def __exit__(self, *_args): pass
    def read(self):
        if mode in ('hang','uncooperative'): time.sleep(60)
        elif mode != 'flood': time.sleep(.01)
        try: socket.getaddrinfo('meeting-fixture.invalid',443)
        except NetworkBlockedError: pass
        else: raise AssertionError('Python network policy disappeared during capture')
        return np.full(1600,.125,dtype=np.float32)
    def finish_audio(self): return np.full(16,.25,dtype=np.float32)
class IgnoreStop:
    def is_set(self): return False
sys.stdout = None  # Same Python-level absence as a windowed frozen executable.
with StopEvent.open(sys.argv[1]) as signal, open_capture_output() as output:
    code = run_capture(request, IgnoreStop() if mode == 'uncooperative' else signal, output,
        microphone_factory=Reader, desktop_factory=Reader, stop_grace=.05)
os._exit(code)
'''


def owner(tmp_path, mode, *, queue_size=200):
    script = tmp_path / 'owned-capture-child.py'
    script.write_text(CHILD, encoding='utf-8')
    created = []
    def factory(argv, **kwargs):
        assert argv[-2] == '--meeting-capture'
        process = WindowsJobProcess([sys.executable, str(script), argv[-1], mode], **kwargs)
        created.append(process)
        return process
    capture = CaptureProcess(CaptureRequest(consent=True, max_seconds=60),
                             process_factory=factory, queue_size=queue_size)
    capture.start(indicator_ready=True)
    return capture, created


def await_events(capture, predicate):
    seen = []
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        seen.extend(capture.take())
        if predicate(seen):
            return seen
        time.sleep(.01)
    pytest.fail('Owned generated-PCM helper did not reach the expected state')


def cleanup(capture):
    if capture.active:
        capture.stop(timeout=0)


def test_native_capture_owner_round_trips_both_tracks_stops_and_accounts_for_every_admitted_frame(tmp_path):
    capture, _ = owner(tmp_path, 'normal')
    try:
        events = await_events(capture, lambda rows: {event.value.track for event in rows if event.kind == 'audio'}
                              == {'microphone', 'desktop'})
        outcome = capture.stop()
        events.extend(capture.take(limit=400))
        assert outcome.stopped and outcome.complete and not outcome.forced and outcome.exit_code == 0
        assert not capture.active
        counts = {track: sum(len(event.value.samples) for event in events
                            if event.kind == 'audio' and event.value.track == track)
                  for track in ('microphone', 'desktop')}
        assert counts == {'microphone': outcome.end.microphone_frames, 'desktop': outcome.end.desktop_frames}
        assert outcome.end.desktop_frames % 1600 == 16
    finally:
        cleanup(capture)


@pytest.mark.parametrize('mode', ['hang', 'uncooperative'])
def test_hung_driver_or_uncooperative_helper_cannot_outlive_a_confirmed_stop(tmp_path, mode):
    capture, _ = owner(tmp_path, mode)
    try:
        await_events(capture, lambda rows: any(event.kind == 'ready' for event in rows))
        capture.request_stop()
        assert capture.active  # Stop intent does not hide the recording indicator.
        outcome = capture.stop(timeout=.2)
        assert outcome.stopped and not outcome.complete and not capture.active
        assert outcome.forced == (mode == 'uncooperative')
    finally:
        cleanup(capture)


def test_receiver_backpressure_terminates_the_native_worker_without_growing_the_queue(tmp_path):
    capture, created = owner(tmp_path, 'flood', queue_size=8)
    try:
        # Deliberately do not consume. The callback must terminate, never block
        # or allocate an unbounded PCM backlog.
        assert created[0].wait_tree(8) != 0
        result = capture.finish()
        assert result.stopped and not result.complete and result.reason == 'backpressure'
        assert len(capture.take(limit=400)) == 8 and not capture.active
    finally:
        cleanup(capture)


def test_lost_owner_closes_the_real_job_even_while_native_reads_are_stalled(tmp_path):
    capture, created = owner(tmp_path, 'uncooperative')
    api = c.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    api.OpenProcess.restype, api.OpenProcess.argtypes = w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]
    api.WaitForSingleObject.restype, api.WaitForSingleObject.argtypes = w.DWORD, [w.HANDLE, w.DWORD]
    api.CloseHandle.restype, api.CloseHandle.argtypes = w.BOOL, [w.HANDLE]
    handle = None
    try:
        await_events(capture, lambda rows: any(event.kind == 'ready' for event in rows))
        handle = api.OpenProcess(0x100000, False, created[0].pid)
        assert handle
        reference = weakref.ref(capture)
        del capture
        assert reference() is None
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        if handle:
            api.CloseHandle(handle)
        for process in created:
            process.close()


def test_pipe_adapter_preserves_the_original_stdout_handle_when_python_stdout_is_none():
    command, cwd, env = capture_command(CaptureRequest(consent=True), 'unused-fixture-event')
    source = "import os,sys;sys.stdout=None;from saydraft.meetings.child import open_capture_output;\nwith open_capture_output() as output: output.write(b'a')\nos.write(1,b'b');os._exit(0)"
    received = []
    with WindowsJobProcess([command[0], '-c', source], cwd=cwd, env=env, on_output=received.append) as process:
        assert process.wait_tree(8) == 0
        process.finish_output(2)
    assert b''.join(received) == b'ab'


def test_stop_event_observers_cannot_reset_signal_or_adopt_a_colliding_event():
    with StopEvent.create() as original, StopEvent.open(original.name) as observer:
        assert not original.is_set() and not observer.is_set()
        with pytest.raises(PermissionError):
            observer.set()
        with pytest.raises(FileExistsError):
            StopEvent.create(original.name)
        assert not original.is_set()
        original.set()
        assert original.is_set() and observer.is_set()
    original.close()
    with pytest.raises(RuntimeError, match='closed'):
        observer.is_set()
