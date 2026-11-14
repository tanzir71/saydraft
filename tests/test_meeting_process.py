import gc
import threading
import weakref

import pytest

from saydraft.meetings.process import CaptureProcess, capture_command
from saydraft.meetings.protocol import END, json_frame
from saydraft.meetings.request import CaptureRequest
from tests.test_meeting_protocol import complete_packets, feed


class Signal:
    name = 'Local' + chr(92) + 'SaydraftMeetingStop-' + 'c' * 32
    def __init__(self): self.sets, self.closed = 0, False
    def set(self): self.sets += 1
    def close(self): self.closed = True


class Process:
    def __init__(self, callback=None):
        self.callback = callback
        self.code, self.closed, self.killed = None, False, False
        self.output_ready, self.output_error, self.never_exit = True, False, False
    def poll_tree(self): return self.code
    def wait_tree(self, _timeout):
        if self.code is None:
            raise TimeoutError('Fixture still running')
        return self.code
    def finish_output(self, _timeout):
        if not self.output_ready:
            raise TimeoutError('Fixture pipe still open')
        if self.output_error:
            raise OSError('Fixture transport failed')
    def terminate(self):
        self.killed = True
        if not self.never_exit:
            self.code = 1
    def close(self): self.closed = True


def finished_owner(*, output_ready=True):
    signal, created = Signal(), []
    def factory(_argv, **kwargs):
        process = Process(kwargs['on_output'])
        feed(type('Receiver', (), {'feed': staticmethod(process.callback)})(), complete_packets())
        process.code, process.output_ready = 0, output_ready
        created.append(process)
        return process
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=factory, event_factory=lambda: signal)
    owner.start(indicator_ready=True)
    return owner, signal, created[0]


@pytest.mark.parametrize('consent,indicator', [(False, True), (True, False), (True, 1)])
def test_consent_and_the_visible_indicator_gate_all_native_resource_creation(consent, indicator):
    def forbidden(*_a, **_kw): pytest.fail('Unconfirmed capture allocated resources')
    owner = CaptureProcess(CaptureRequest(consent=consent), process_factory=forbidden, event_factory=forbidden)
    with pytest.raises(PermissionError):
        owner.start(indicator_ready=indicator)
    assert not owner.active


def test_success_requires_kernel_tree_exit_and_drained_valid_transport():
    owner, signal, process = finished_owner()
    assert owner.active and not signal.closed
    result = owner.finish()
    assert result.stopped and result.complete and result.reason == 'stopped'
    assert result.end.microphone_frames == result.end.desktop_frames == 1600
    assert process.closed and signal.closed and not owner.active
    assert owner.poll() is result
    assert len(owner.take()) == 7
    with pytest.raises(RuntimeError, match='only once'):
        owner.start(indicator_ready=True)


def test_primary_exit_without_pipe_eof_keeps_the_owner_and_indicator_active():
    owner, signal, process = finished_owner(output_ready=False)
    assert owner.poll() is None and owner.active and not signal.closed
    process.output_ready = True
    assert owner.finish().stopped and signal.closed


def test_stop_before_a_queued_start_prevents_even_event_or_process_creation():
    def forbidden(*_a, **_kw): pytest.fail('Retired queued capture allocated resources')
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=forbidden, event_factory=forbidden)
    assert owner.stop().stopped
    owner.start(indicator_ready=True)
    assert not owner.active and owner.poll().reason == 'cancelled'


def test_failed_creation_closes_only_the_new_owned_signal():
    signal = Signal()
    def failure(*_a, **_kw): raise OSError('Fixture launch failed')
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=failure, event_factory=lambda: signal)
    with pytest.raises(OSError, match='launch failed'):
        owner.start(indicator_ready=True)
    assert not owner.active and signal.closed


def test_cancellation_during_launch_is_nonblocking_and_is_forwarded_before_capture():
    signal, entered, release, errors = Signal(), threading.Event(), threading.Event(), []
    def factory(_argv, **kwargs):
        entered.set()
        assert release.wait(2)
        process = Process(kwargs['on_output'])
        feed(type('Receiver', (), {'feed': staticmethod(process.callback)})(), [json_frame(END,
            {'complete': False, 'reason': 'cancelled', 'frames': {'microphone': 0, 'desktop': 0}})])
        process.code = 2
        return process
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=factory, event_factory=lambda: signal)
    def start():
        try:
            owner.start(indicator_ready=True)
        except Exception as error:
            errors.append(error)
    thread = threading.Thread(target=start)
    thread.start()
    try:
        assert entered.wait(1)
        assert owner.stop().reason == 'starting' and owner.active and signal.sets == 1
    finally:
        release.set()
        thread.join(2)
    assert not errors and not thread.is_alive()
    assert owner.finish().reason == 'cancelled' and signal.sets == 2 and signal.closed


def test_unconfirmed_forced_stop_never_retires_the_owner_or_claims_recording_stopped():
    signal, process = Signal(), Process()
    process.never_exit = True
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=lambda *_a, **_kw: process,
                           event_factory=lambda: signal)
    owner.start(indicator_ready=True)
    result = owner.stop(timeout=0)
    assert not result.stopped and not result.complete and process.killed
    assert owner.active and not signal.closed and not process.closed
    process.code = 1
    assert owner.finish().stopped and not owner.active and signal.closed


def test_losing_the_capture_owner_closes_the_job_instead_of_leaving_a_callback_cycle():
    signal, created = Signal(), []
    def factory(_argv, **kwargs):
        process = Process(kwargs['on_output'])
        created.append(process)
        return process
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=factory, event_factory=lambda: signal)
    owner.start(indicator_ready=True)
    reference = weakref.ref(owner)
    del owner
    gc.collect()
    assert reference() is None and created[0].closed and signal.closed


def test_a_post_launch_signal_failure_terminates_and_retains_the_child_until_observed():
    class FailingSignal(Signal):
        def set(self):
            super().set()
            if self.sets >= 2:
                raise OSError('Fixture stop event failed')
    signal, process = FailingSignal(), Process()
    def factory(_argv, **_kwargs):
        owner.request_stop()
        return process
    owner = CaptureProcess(CaptureRequest(consent=True), process_factory=factory, event_factory=lambda: signal)
    with pytest.raises(OSError, match='event failed'):
        owner.start(indicator_ready=True)
    assert process.killed and owner.active and not signal.closed
    outcome = owner.finish()
    assert outcome.stopped and not outcome.complete and outcome.forced
    assert not owner.active and signal.closed


def test_source_child_environment_omits_credentials_proxy_settings_and_ambient_pythonpath(monkeypatch):
    monkeypatch.setenv('HF_TOKEN', 'fixture-secret')
    monkeypatch.setenv('HTTPS_PROXY', 'fixture-proxy')
    monkeypatch.setenv('PYTHONPATH', 'fixture-untrusted-startup')
    argv, cwd, env = capture_command(CaptureRequest(consent=True), Signal.name)
    assert argv[-2:] == ['--meeting-capture', Signal.name]
    assert 'HF_TOKEN' not in env and 'HTTPS_PROXY' not in env
    assert 'fixture-untrusted-startup' not in env['PYTHONPATH']
    assert env['PYTHONNOUSERSITE'] == '1' and env['HF_HUB_OFFLINE'] == '1' and cwd
