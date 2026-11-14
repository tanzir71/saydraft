from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
import threading
import socket
import subprocess
import sys
import warnings

import numpy as np
import pytest

from saydraft.audio.devices import InputSelection
from saydraft.meetings.audio import DesktopReader, DesktopResampler, MicrophoneReader, audio_com_context, mono_float


def test_importing_meeting_capture_does_not_load_audio_backends():
    subprocess.run([sys.executable, '-c', 'import sys; import saydraft.meetings.audio; '
        'assert "soundcard" not in sys.modules; assert "sounddevice" not in sys.modules'], check=True, timeout=20)


def test_low_pass_removes_aliases_without_losing_in_band_speech_energy():
    time = np.arange(48_000) / 48_000
    def convert(frequency):
        source = np.sin(2 * np.pi * frequency * time).astype(np.float32)
        return DesktopResampler().push(source, final=True)[100:-100]
    def rms(value):
        return float(np.sqrt(np.mean(value ** 2)))
    assert rms(convert(1000)) == pytest.approx(2 ** -.5, rel=.003)
    assert rms(convert(6000)) == pytest.approx(2 ** -.5, rel=.02)
    assert rms(convert(12000)) < .0002
    # Straight every-third-sample decimation aliases this tone into speech.
    assert rms(np.sin(2 * np.pi * 12000 * time)[::3]) > .7


@pytest.mark.parametrize('length', [0, 1, 2, 3, 47, 48, 49, 4801, 48000])
def test_filter_phase_and_tail_are_identical_across_arbitrary_native_blocks(length):
    audio = np.random.default_rng(14).uniform(-.8, .8, length).astype(np.float32)
    reference = DesktopResampler().push(audio, final=True)
    reader = DesktopResampler()
    chunks, offset = [], 0
    for count in [1, 17, 2, 480, 3, 1699, 7, 1, 2048]:
        chunks.append(reader.push(audio[offset:offset + count]))
        offset += count
        assert len(reader._pending) <= 96
    chunks.append(reader.push(audio[offset:], final=True))
    actual = np.concatenate(chunks)
    assert len(actual) == (length + 2) // 3
    np.testing.assert_array_equal(actual, reference)
    assert reader.input_frames == length and reader.output_frames == len(actual)
    with pytest.raises(RuntimeError, match='already finished'):
        reader.push(np.empty(0, dtype=np.float32))


def test_native_buffers_are_downmixed_and_copied_without_reusing_driver_memory():
    native = np.array([[.2, .6], [-.4, .2]], dtype=np.float32)
    converted = mono_float(native, frames=2)
    native[:] = 0
    np.testing.assert_allclose(converted, [.4, -.1])


@pytest.mark.parametrize('audio', [np.array([np.nan]), np.array([np.inf]), np.array([9.]),
    np.zeros((10, 0)), np.zeros((10, 33)), np.zeros((2, 2, 2)), np.zeros(2, dtype=np.int16),
    np.zeros(48_000 * 5 + 1)])
def test_invalid_audio_fails_before_asr_instead_of_silently_becoming_a_transcript(audio):
    with pytest.raises(ValueError, match='finite normalized'):
        mono_float(audio)


class Native:
    def __init__(self):
        self.closed = False
        self.frames = np.ones((4800, 2), dtype=np.float32) * .25

    def record(self, numframes):
        assert numframes == 4800
        return self.frames


class Endpoint:
    def __init__(self, identity='render-id', *, loopback=True, channels=2):
        self.id, self.isloopback, self.channels = identity, loopback, channels
        self.native, self.options, self.entered = Native(), None, False

    @contextmanager
    def recorder(self, **kwargs):
        self.options, self.entered = kwargs, True
        try:
            yield self.native
        finally:
            self.native.closed = True


class Backend:
    def __init__(self, *devices):
        self.devices, self.queries = devices, []

    def default_speaker(self):
        self.queries.append('default')
        return SimpleNamespace(id='render-id')

    def all_microphones(self, *, include_loopback):
        assert include_loopback is True
        self.queries.append('endpoints')
        return self.devices


def test_explicit_desktop_reader_uses_exact_output_id_all_channels_and_closes_after_failure():
    device = Endpoint()
    backend = Backend(Endpoint(loopback=False), device)
    with pytest.raises(ValueError, match='finite normalized'):
        with DesktopReader(consent=True, backend=backend, com_context=nullcontext) as reader:
            assert backend.queries == ['default', 'endpoints']
            assert device.options == {'samplerate': 48000, 'channels': None, 'blocksize': 9600}
            assert len(reader.read()) == 1584  # 1 ms lookahead is flushed at capture end.
            device.native.frames[0, 0] = np.nan
            reader.read()
    assert device.native.closed
    with pytest.raises(RuntimeError, match='active capture thread'):
        reader.read()
    assert len(reader.resampler.push(np.empty(0, dtype=np.float32), final=True)) == 16


@pytest.mark.parametrize('devices', [[], [Endpoint('other-id')], [Endpoint(), Endpoint()],
    [Endpoint(loopback=False)], [Endpoint(channels=1)], [Endpoint(channels=33)]])
def test_missing_ambiguous_or_unsupported_output_never_opens_an_alternative_device(devices):
    backend = Backend(*devices)
    with pytest.raises(OSError):
        with DesktopReader(consent=True, endpoint_id='render-id', backend=backend, com_context=nullcontext):
            pytest.fail('An unsupported endpoint was admitted')
    assert backend.queries == ['endpoints']
    assert not any(device.entered for device in devices)


def test_desktop_discontinuity_finishes_the_native_read_then_reports_a_gap():
    device, completed = Endpoint(), []
    def interrupted(numframes):
        warnings.warn('Fixture discontinuity', RuntimeWarning)
        completed.append(True)  # Simulates the backend releasing its native packet.
        return np.zeros((numframes, 2), dtype=np.float32)
    device.native.record = interrupted
    with pytest.raises(OSError, match='reported a gap'):
        with DesktopReader(consent=True, backend=Backend(device), com_context=nullcontext) as reader:
            reader.read()
    assert completed == [True] and device.native.closed


def test_default_or_false_consent_never_discovers_opens_or_imports_a_backend(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Unconsented capture reached a backend')
    backend = SimpleNamespace(default_speaker=forbidden, all_microphones=forbidden)
    for allowed in (False,):
        with pytest.raises(PermissionError):
            with DesktopReader(consent=allowed, backend=backend, com_context=forbidden):
                pass
        with pytest.raises(PermissionError):
            with MicrophoneReader(consent=allowed, stream_factory=forbidden):
                pass
    # This also refuses before importing SoundCard on an unsupported platform.
    monkeypatch.setattr('saydraft.meetings.audio.sys.platform', 'unsupported')
    with pytest.raises(OSError, match='requires Windows'):
        with DesktopReader(consent=True):
            pass


class Mic:
    def __init__(self, *, overflow=False, start_error=False):
        self.overflow, self.start_error = overflow, start_error
        self.calls = []

    def start(self):
        self.calls.append('start')
        if self.start_error:
            raise OSError('Fixture unavailable')

    def read(self, count):
        return np.zeros((count, 1), dtype=np.float32), self.overflow

    def stop(self): self.calls.append('stop')
    def close(self): self.calls.append('close')


def test_microphone_reuses_saved_selection_and_keeps_overflow_visible():
    native, selection, seen = Mic(overflow=True), InputSelection('Fixture mic', 'Windows WASAPI'), []
    def factory(chosen, **kwargs):
        seen.append((chosen, kwargs))
        return native
    with pytest.raises(OSError, match='contains a gap'):
        with MicrophoneReader(selection, consent=True, stream_factory=factory) as reader:
            reader.read()
    assert seen == [(selection, {'samplerate': 16000, 'channels': 1, 'dtype': 'float32', 'blocksize': 1600})]
    assert native.calls == ['start', 'stop', 'close']


def test_failed_microphone_start_closes_the_allocated_stream():
    native = Mic(start_error=True)
    with pytest.raises(OSError, match='Fixture unavailable'):
        with MicrophoneReader(consent=True, stream_factory=lambda *_a, **_kw: native):
            pass
    assert native.calls == ['start', 'close']


def test_capture_objects_cannot_be_moved_between_threads():
    device, errors = Endpoint(), []
    with DesktopReader(consent=True, backend=Backend(device), com_context=nullcontext) as reader:
        def attempt():
            try:
                reader.read()
            except RuntimeError as error:
                errors.append(str(error))
        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join(2)
        assert not thread.is_alive()
    assert len(errors) == 1 and 'capture thread' in errors[0]
    assert device.native.closed


def test_python_network_guard_stays_active_while_fixture_tracks_are_read():
    from saydraft.privacy.netguard import NetworkBlockedError, NetworkGuard
    previously_installed = NetworkGuard.is_installed()
    NetworkGuard.install()
    try:
        with DesktopReader(consent=True, backend=Backend(Endpoint()), com_context=nullcontext) as desktop:
            with MicrophoneReader(consent=True, stream_factory=lambda *_a, **_kw: Mic()) as microphone:
                for _ in range(3):
                    assert desktop.read().size > 0 and microphone.read().size == 1600
                    with pytest.raises(NetworkBlockedError):
                        socket.create_connection(('203.0.113.1', 443))
                    with pytest.raises(NetworkBlockedError):
                        socket.getaddrinfo('meeting-fixture.invalid', 443)
    finally:
        if not previously_installed:
            NetworkGuard.uninstall()


@pytest.mark.parametrize('result,uninitialize', [(0, True), (1, True), (-2147417850, False)])
def test_com_reference_ownership_is_balanced_even_on_stream_failure(monkeypatch, result, uninitialize):
    calls = []
    class Function:
        def __init__(self, name, value=None): self.name, self.value = name, value
        def __call__(self, *args):
            calls.append(self.name)
            return self.value
    api = SimpleNamespace(CoInitializeEx=Function('init', result), CoUninitialize=Function('uninit'))
    monkeypatch.setattr('saydraft.meetings.audio.sys.platform', 'win32')
    monkeypatch.setattr('saydraft.meetings.audio.ctypes.WinDLL', lambda *a, **kw: api, raising=False)
    with pytest.raises(OSError, match='Fixture stream'):
        with audio_com_context():
            raise OSError('Fixture stream failed')
    assert calls == ['init', 'uninit'] if uninitialize else calls == ['init']
