"""Pull-based microphone and desktop tracks for an isolated meeting worker.

No backend is imported and no endpoint is enumerated until explicitly entered.
Readers belong to their opening capture thread. SoundCard reads can block in
the driver: the application must host these in an owned, terminable child,
not a GUI thread. No recording is written to disk by this module.
"""

from contextlib import ExitStack, contextmanager
import ctypes
import sys
import threading
import warnings

import numpy as np

from saydraft.audio.devices import InputSelection, selected_input_stream

SAMPLE_RATE = 16_000
NATIVE_RATE = 48_000
BLOCK_FRAMES = 4_800


class AudioGapError(OSError):
    """Native capture reported missing frames; retain an incomplete recording."""


def mono_float(samples, *, frames=None):
    value = np.asarray(samples)
    if (value.dtype.kind != 'f' or value.ndim not in (1, 2)
            or value.shape[0] > NATIVE_RATE * 5
            or value.ndim == 2 and not 1 <= value.shape[1] <= 32
            or frames is not None and value.shape[0] != frames
            or not np.isfinite(value).all() or np.any(np.abs(value) > 8)):
        raise ValueError('Meeting audio must contain finite normalized floating-point frames')
    if value.ndim == 2:
        value = value.mean(axis=1, dtype=np.float64)
    return np.array(value, dtype=np.float32, copy=True)


class DesktopResampler:
    """48 kHz -> 16 kHz with a centered 97-tap Kaiser low-pass filter.

    Keeps 1 ms of lookahead and a bounded tail between calls. Integer sample
    phase survives arbitrary native block boundaries; flush pads only the end.
    Low-pass filtering precedes decimation to reduce aliasing into speech.
    """

    def __init__(self):
        indices = np.arange(-48, 49, dtype=np.float64)
        cutoff = .94 / 3
        kernel = cutoff * np.sinc(cutoff * indices) * np.kaiser(97, 8.6)
        self._kernel = kernel / kernel.sum()
        self._pending = np.zeros(48, dtype=np.float32)
        self._closed = False
        self.input_frames = self.output_frames = 0

    def push(self, samples, *, final=False):
        if self._closed:
            raise RuntimeError('Meeting resampler has already finished')
        if type(final) is not bool:
            raise ValueError('Final audio flag must be boolean')
        mono = mono_float(samples)
        self.input_frames += len(mono)
        self._pending = np.concatenate((self._pending, mono))
        if final:
            self._pending = np.pad(self._pending, (0, 48))
        if len(self._pending) < len(self._kernel):
            result = np.empty(0, dtype=np.float32)
        else:
            result = np.convolve(self._pending, self._kernel, mode='valid')[::3].astype(np.float32)
            self._pending = self._pending[len(result) * 3:]
        self.output_frames += len(result)
        if final:
            self._closed = True
            self._pending = np.empty(0, dtype=np.float32)
            if self.output_frames != (self.input_frames + 2) // 3:
                raise RuntimeError('Meeting resampling lost its sample phase')
        return result


@contextmanager
def audio_com_context():
    """Balance the capture thread's COM reference, including an existing STA.

    Adapted from the owner's Translito windows_audio.py (blob 000d0de3);
    do not pass SoundCard's native objects between COM apartments.
    """
    if sys.platform != 'win32':
        yield
        return
    api = ctypes.WinDLL('ole32', winmode=0x800)
    api.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.CoInitializeEx.restype = ctypes.c_long
    api.CoUninitialize.argtypes = []
    api.CoUninitialize.restype = None
    result = api.CoInitializeEx(None, 0) & 0xFFFFFFFF
    owned = result in (0, 1)
    if not owned and result != 0x80010106:
        raise OSError('Windows meeting audio initialization failed')
    try:
        yield
    finally:
        if owned:
            api.CoUninitialize()


class DesktopReader:
    """Explicit WASAPI output capture, re-resolved by exact endpoint ID.

    A backend can be injected without opening real endpoints. A single-channel
    endpoint is refused because SoundCard documents corrupted mono WASAPI data.
    Capture all native channels, then downmix and filter to the ASR rate.
    """

    def __init__(self, *, consent=False, endpoint_id='', backend=None, com_context=audio_com_context):
        if type(consent) is not bool or type(endpoint_id) is not str or len(endpoint_id) > 1024 or '\0' in endpoint_id:
            raise ValueError('Invalid meeting capture request')
        self.consent, self.endpoint_id = consent, endpoint_id
        self.backend, self.com_context = backend, com_context
        self._stack = self._stream = self._thread = None
        self._used = self._opened = self._closed = self._finished = False
        self._native_tail = np.empty(0, dtype=np.float32)
        self.resampler = DesktopResampler()

    def __enter__(self):
        if self.consent is not True:
            raise PermissionError('Start meeting recording explicitly after confirming participant consent')
        if self._used:
            raise RuntimeError('Create a new reader for each meeting capture')
        self._used = True
        if self.backend is None:
            if sys.platform != 'win32':
                raise OSError('Desktop meeting capture requires Windows WASAPI')
            import soundcard
            self.backend = soundcard
        stack = ExitStack()
        try:
            stack.enter_context(self.com_context())
            identity = self.endpoint_id or self.backend.default_speaker().id
            if type(identity) is not str or not identity:
                raise OSError('No desktop audio endpoint is selected')
            matches = [device for device in self.backend.all_microphones(include_loopback=True)
                       if device.id == identity and device.isloopback is True]
            if len(matches) != 1:
                raise OSError('Selected desktop audio endpoint is unavailable or ambiguous')
            device = matches[0]
            if type(device.channels) is not int or not 2 <= device.channels <= 32:
                raise OSError('This desktop endpoint cannot provide supported multichannel WASAPI capture')
            self._stream = stack.enter_context(device.recorder(samplerate=NATIVE_RATE,
                channels=None, blocksize=BLOCK_FRAMES * 2))
            self._stack, self._thread = stack, threading.get_ident()
            self._opened = True
            return self
        except BaseException:
            stack.close()
            self._stream = None
            raise

    def read(self):
        self._check()
        # Let the backend release its packet before turning its discontinuity
        # warning into a failure. Do not manufacture a continuous transcript
        # across lost desktop audio. This belongs inside the isolated worker.
        with warnings.catch_warnings(record=True) as issues:
            warnings.simplefilter('always', RuntimeWarning)
            data = self._stream.record(numframes=BLOCK_FRAMES)
        if any(issubclass(issue.category, RuntimeWarning) for issue in issues):
            raise AudioGapError('Desktop meeting audio reported a gap or capture problem')
        for issue in issues:
            warnings.warn_explicit(issue.message, issue.category, issue.filename, issue.lineno)
        native = mono_float(data, frames=BLOCK_FRAMES)
        return self.resampler.push(native)

    def _check(self):
        if self._stack is None or self._thread != threading.get_ident():
            raise RuntimeError('Meeting reader belongs to its active capture thread')

    def __exit__(self, *exc):
        self._check()
        stack, stream = self._stack, self._stream
        self._stack = None
        self._stream = None
        self._closed = True
        try:
            if exc[0] is None:
                # SoundCard has already read these native frames while filling
                # its last exact-size block. Its pinned flush is memory-only.
                self._native_tail = mono_float(stream.flush())
        except BaseException:
            stack.__exit__(*sys.exc_info())
            raise
        else:
            stack.__exit__(*exc)
            return False  # A backend cannot suppress an incomplete recording.

    def finish_audio(self):
        """Drain already-read SDK frames and filter lookahead after context exit."""
        if not self._opened or not self._closed or self._finished:
            raise RuntimeError('Meeting audio can finish once after its capture context exits')
        self._finished = True
        native, self._native_tail = self._native_tail, np.empty(0, dtype=np.float32)
        return self.resampler.push(native, final=True)


class MicrophoneReader:
    """Reuse the normal microphone's stable selection and pinned PortAudio."""

    def __init__(self, selection=None, *, consent=False, stream_factory=selected_input_stream):
        if type(consent) is not bool or selection is not None and type(selection) is not InputSelection:
            raise ValueError('Invalid meeting microphone request')
        self.selection, self.consent = selection or InputSelection(), consent
        self.stream_factory = stream_factory
        self._stream = self._thread = None
        self._used = False

    def __enter__(self):
        if self.consent is not True:
            raise PermissionError('Start meeting recording explicitly after confirming participant consent')
        if self._used:
            raise RuntimeError('Create a new microphone reader for each meeting')
        self._used = True
        stream = self.stream_factory(self.selection, samplerate=SAMPLE_RATE,
            channels=1, dtype='float32', blocksize=1600)
        try:
            stream.start()
        except BaseException:
            stream.close()
            raise
        self._stream, self._thread = stream, threading.get_ident()
        return self

    def read(self):
        if self._stream is None or self._thread != threading.get_ident():
            raise RuntimeError('Meeting microphone belongs to its active capture thread')
        data, overflowed = self._stream.read(1600)
        if overflowed:
            raise AudioGapError('Meeting microphone overflowed; recording contains a gap')
        return mono_float(data, frames=1600)

    def __exit__(self, *exc):
        if self._stream is None or self._thread != threading.get_ident():
            raise RuntimeError('Meeting microphone belongs to its active capture thread')
        stream, self._stream = self._stream, None
        try:
            stream.stop()
        finally:
            stream.close()
