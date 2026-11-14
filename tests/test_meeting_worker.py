import io
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.meetings.audio import AudioGapError
from saydraft.meetings.child import REQUEST_ENV, helper_main, run_capture
from saydraft.meetings.protocol import CaptureDecoder
from saydraft.meetings.request import CaptureRequest


class Signal:
    def __init__(self): self.event = threading.Event()
    def is_set(self): return self.event.is_set()
    def __enter__(self): return self
    def __exit__(self, *_exc): pass


class Output(io.BytesIO):
    def close(self): pass


class Reader:
    def __init__(self, signal, *, gap=False, hang=None):
        self.signal, self.gap, self.hang = signal, gap, hang
        self.reads, self.closed, self.thread = 0, False, None
    def __enter__(self):
        self.thread = threading.current_thread()
        return self
    def __exit__(self, *_exc): self.closed = True
    def read(self):
        if self.hang is not None:
            self.hang.wait(5)
        time.sleep(.005)
        self.reads += 1
        if self.gap:
            raise AudioGapError('Fixture missing frames')
        if self.reads >= 3:
            self.signal.event.set()
        return np.full(1600, .125, dtype=np.float32)
    def finish_audio(self):
        assert self.closed
        return np.full(16, .25, dtype=np.float32)


def decode(output):
    events = []
    decoder = CaptureDecoder(events.append, max_seconds=5)
    data = output.getvalue()
    for offset in range(0, len(data), 4096):
        decoder.feed(data[offset:offset + 4096])
    return decoder.finish(), events


def test_connected_capture_threads_close_before_end_and_preserve_the_desktop_tail():
    signal, output = Signal(), Output()
    mic, desktop = Reader(signal), Reader(signal)
    code = run_capture(CaptureRequest(consent=True, max_seconds=5), signal, output,
        microphone_factory=lambda: mic, desktop_factory=lambda: desktop)
    end, events = decode(output)
    assert code == 0 and end.complete and mic.closed and desktop.closed
    assert end.microphone_frames == mic.reads * 1600
    assert end.desktop_frames == desktop.reads * 1600 + 16
    parts = [event.value for event in events if event.kind == 'audio' and event.value.track == 'desktop']
    assert len(parts[-1].samples) == 16
    assert sum(event.kind == 'ready' for event in events) == 1


def test_cancel_before_start_opens_no_reader_or_device():
    signal, output = Signal(), Output()
    signal.event.set()
    def forbidden(): pytest.fail('Cancelled capture opened a reader')
    assert run_capture(CaptureRequest(consent=True, max_seconds=5), signal, output,
        microphone_factory=forbidden, desktop_factory=forbidden) == 2
    end, events = decode(output)
    assert not end.complete and end.reason == 'cancelled'
    assert (end.microphone_frames, end.desktop_frames) == (0, 0)
    assert [event.kind for event in events] == ['end']


def test_audio_gap_stops_both_tracks_and_cannot_become_success():
    signal, output = Signal(), Output()
    mic, desktop = Reader(signal, gap=True), Reader(signal)
    assert run_capture(CaptureRequest(consent=True, max_seconds=5), signal, output,
        microphone_factory=lambda: mic, desktop_factory=lambda: desktop) == 2
    end, events = decode(output)
    assert not end.complete and end.reason == 'capture_failed'
    assert 'audio_gap' in [event.value for event in events if event.kind == 'error']
    assert mic.closed and (desktop.closed or desktop.thread is None)


def test_hung_readers_get_no_packet_admission_after_the_failure_receipt():
    signal, output, release = Signal(), Output(), threading.Event()
    mic, desktop = Reader(signal, hang=release), Reader(signal, hang=release)
    timer = threading.Timer(.03, signal.event.set)
    timer.start()
    try:
        assert run_capture(CaptureRequest(consent=True, max_seconds=5), signal, output,
            microphone_factory=lambda: mic, desktop_factory=lambda: desktop, stop_grace=.03) == 2
        before = output.getvalue()
        end, _ = decode(output)
        assert not end.complete and end.reason == 'capture_failed'
    finally:
        release.set()
        timer.cancel()
        for reader in (mic, desktop):
            if reader.thread is not None:
                reader.thread.join(2)
                assert not reader.thread.is_alive()
    assert output.getvalue() == before


def test_unconfirmed_requests_fail_before_any_capture_factory():
    with pytest.raises(PermissionError):
        run_capture(CaptureRequest(), Signal(), Output(),
                    microphone_factory=lambda: pytest.fail('No consent'))


def test_helper_rejects_invalid_arguments_before_native_resources():
    def forbidden(*_args): pytest.fail('Invalid helper invocation reached native resources')
    assert helper_main(['not-a-meeting-event'], signal_factory=forbidden, output_factory=forbidden) == 2
    exits = []
    assert helper_main(['Local' + chr(92) + 'SaydraftMeetingStop-' + 'a' * 32],
        environment={REQUEST_ENV: '{}'}, signal_factory=forbidden, output_factory=forbidden,
        exit_process=exits.append) == 2
    assert exits == [2]


def test_cancelled_helper_uses_the_private_exit_boundary_without_default_audio_backends():
    signal, output, exits = Signal(), Output(), []
    signal.event.set()
    name = 'Local' + chr(92) + 'SaydraftMeetingStop-' + 'b' * 32
    environment = {REQUEST_ENV: CaptureRequest(consent=True, max_seconds=5).to_json()}
    assert helper_main([name], environment=environment, signal_factory=lambda _name: signal,
        output_factory=lambda: output, exit_process=exits.append) == 2
    assert REQUEST_ENV not in environment and exits == [2]
    assert decode(output)[0].reason == 'cancelled'


def test_main_dispatches_capture_after_network_guard_and_before_profile_or_app_start(monkeypatch):
    import sys
    from saydraft.main import main
    from saydraft.privacy.netguard import NetworkGuard
    calls = []
    def helper(args):
        assert NetworkGuard.is_installed()
        calls.append(args)
        return 17
    previously = NetworkGuard.is_installed()
    monkeypatch.setattr(sys, 'argv', ['Saydraft', '--meeting-capture', 'fixture-name'])
    monkeypatch.setattr('saydraft.meetings.child.helper_main', helper)
    trap = SimpleNamespace(__getattr__=lambda _name: pytest.fail('Owner profile was touched'))
    # A wrong dispatch cannot proceed to migration or application services.
    monkeypatch.setitem(sys.modules, 'saydraft.compat.migrate', trap)
    monkeypatch.setitem(sys.modules, 'saydraft.app', trap)
    try:
        assert main() == 17 and calls == [['fixture-name']]
    finally:
        if not previously:
            NetworkGuard.uninstall()
