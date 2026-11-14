"""Bounded, versioned PCM transport over the owned capture child's stdout pipe.

No pickle, dynamic object loading or file paths. Separate tracks retain their
sample counts; clocks give estimated origins, not exact cross-device sync.
The receiver raises on corruption, dropped/duplicate samples or backpressure.
"""

from dataclasses import dataclass
import json
import math
import struct
import threading
import zlib

import numpy as np

from .audio import SAMPLE_RATE, mono_float
from .limits import MAX_AUDIO_SAMPLES
from .request import MAX_SECONDS, strict_json

HEADER = struct.Struct('<4sBII')
PCM_HEADER = struct.Struct('<BQ')
MAGIC = b'SDM1'
MAX_PAYLOAD = 16 * 1024
MAX_INPUT_CHUNK = 4096
TRACKS = ('microphone', 'desktop')
TRACK_NUMBERS = {'microphone': 1, 'desktop': 2}
START, AUDIO, READY, END, ERROR = range(1, 6)
ERROR_REASONS = frozenset(('device_unavailable', 'audio_gap', 'invalid_audio', 'capture_failed', 'transport_failed'))
END_REASONS = frozenset(('stopped', 'limit', 'capture_failed', 'cancelled', 'transport_failed'))


@dataclass(frozen=True)
class TrackStarted:
    track: str
    offset_seconds: float


@dataclass(frozen=True, eq=False)
class AudioChunk:
    track: str
    start_frame: int
    samples: np.ndarray


@dataclass(frozen=True)
class CaptureEnd:
    complete: bool
    reason: str
    microphone_frames: int
    desktop_frames: int


@dataclass(frozen=True)
class CaptureEvent:
    kind: str
    value: object = None


def frame(kind, payload):
    if type(kind) is not int or kind not in (START, AUDIO, READY, END, ERROR) or type(payload) is not bytes:
        raise ValueError('Invalid meeting packet')
    if not 0 < len(payload) <= MAX_PAYLOAD:
        raise ValueError('Meeting packet exceeds its bound')
    return HEADER.pack(MAGIC, kind, len(payload), zlib.crc32(payload)) + payload


def json_frame(kind, value):
    return frame(kind, json.dumps(value, ensure_ascii=True, allow_nan=False,
                                  separators=(',', ':')).encode('ascii'))


def audio_frame(track, start_frame, samples):
    if type(track) is not str or track not in TRACKS or type(start_frame) is not int or start_frame < 0:
        raise ValueError('Invalid meeting PCM header')
    values = mono_float(samples)
    if not 0 < len(values) <= MAX_AUDIO_SAMPLES or start_frame + len(values) > MAX_SECONDS * SAMPLE_RATE + MAX_AUDIO_SAMPLES:
        raise ValueError('Meeting PCM block exceeds its bound')
    return frame(AUDIO, PCM_HEADER.pack(TRACK_NUMBERS[track], start_frame) + values.astype('<f4').tobytes())


class PacketWriter:
    """Serialize both capture threads and handle short binary pipe writes."""

    def __init__(self, output):
        self.output, self._lock = output, threading.Lock()

    def write(self, packet):
        if type(packet) is not bytes or len(packet) > MAX_PAYLOAD + HEADER.size:
            raise ValueError('Invalid meeting output packet')
        with self._lock:
            remaining = memoryview(packet)
            while remaining:
                sent = self.output.write(remaining)
                if type(sent) is not int or not 0 < sent <= len(remaining):
                    raise OSError('Meeting output pipe stopped accepting data')
                remaining = remaining[sent:]
            self.output.flush()


class CaptureDecoder:
    def __init__(self, on_event, *, max_seconds=MAX_SECONDS):
        if not callable(on_event) or type(max_seconds) is not int or not 1 <= max_seconds <= MAX_SECONDS:
            raise ValueError('Invalid meeting receiver')
        self._on_event, self._max_frames = on_event, max_seconds * SAMPLE_RATE + MAX_AUDIO_SAMPLES
        self._max_seconds = max_seconds
        self._pending = bytearray()
        self._frames = dict.fromkeys(TRACKS, 0)
        self._offsets = dict.fromkeys(TRACKS, None)
        self._errors = []
        self.ready = self.failed = self.closed = False
        self.end = None

    @property
    def frames(self):
        return dict(self._frames)

    @property
    def errors(self):
        return tuple(self._errors)

    def _emit(self, kind, value=None):
        self._on_event(CaptureEvent(kind, value))

    def feed(self, data):
        if self.closed or self.failed:
            raise ValueError('Meeting receiver is retired')
        try:
            if type(data) is not bytes or len(data) > MAX_INPUT_CHUNK or self.end is not None and data:
                raise ValueError('Invalid meeting transport chunk')
            self._pending.extend(data)
            while len(self._pending) >= HEADER.size:
                magic, kind, length, checksum = HEADER.unpack_from(self._pending)
                if magic != MAGIC or kind not in (START, AUDIO, READY, END, ERROR) or not 0 < length <= MAX_PAYLOAD:
                    raise ValueError('Invalid meeting transport header')
                total = HEADER.size + length
                if len(self._pending) < total:
                    break
                payload = bytes(self._pending[HEADER.size:total])
                del self._pending[:total]
                if zlib.crc32(payload) != checksum:
                    raise ValueError('Corrupted meeting transport')
                self._accept(kind, payload)
                if self.end is not None and self._pending:
                    raise ValueError('Meeting transport continued after completion')
        except Exception:
            self.failed = True
            self._pending.clear()
            raise

    def _accept(self, kind, payload):
        if kind == AUDIO:
            self._audio(payload)
            return
        value = strict_json(payload.decode('utf-8'))
        if type(value) is not dict:
            raise ValueError('Invalid meeting control packet')
        if kind == START:
            if set(value) != {'track', 'offset_seconds'} or type(value['track']) is not str or value['track'] not in TRACKS:
                raise ValueError('Invalid meeting track')
            track, offset = value['track'], value['offset_seconds']
            if (self._offsets[track] is not None or type(offset) not in (int, float)
                    or not math.isfinite(offset) or not 0 <= offset <= self._max_seconds):
                raise ValueError('Invalid meeting track origin')
            self._emit('track', TrackStarted(track, float(offset)))
            self._offsets[track] = float(offset)
        elif kind == READY:
            if value or self.ready or self._errors or any(offset is None for offset in self._offsets.values()):
                raise ValueError('Invalid meeting readiness')
            self._emit('ready')
            self.ready = True
        elif kind == ERROR:
            if (set(value) != {'reason'} or type(value['reason']) is not str
                    or value['reason'] not in ERROR_REASONS or len(self._errors) >= 4):
                raise ValueError('Invalid meeting failure')
            self._emit('error', value['reason'])
            self._errors.append(value['reason'])
        elif kind == END:
            if set(value) != {'complete', 'reason', 'frames'} or type(value['complete']) is not bool:
                raise ValueError('Invalid meeting completion')
            counts, reason, complete = value['frames'], value['reason'], value['complete']
            if (type(reason) is not str or reason not in END_REASONS or type(counts) is not dict or set(counts) != set(TRACKS)
                    or any(type(counts[track]) is not int or counts[track] != self._frames[track] for track in TRACKS)
                    or complete and (not self.ready or self._errors or not all(self._frames.values())
                                     or reason not in ('stopped', 'limit'))):
                raise ValueError('Inconsistent meeting completion')
            result = CaptureEnd(complete, reason, counts['microphone'], counts['desktop'])
            self._emit('end', result)
            self.end = result

    def _audio(self, payload):
        count = (len(payload) - PCM_HEADER.size) // 4
        if (len(payload) < PCM_HEADER.size + 4 or (len(payload) - PCM_HEADER.size) % 4
                or not 1 <= count <= MAX_AUDIO_SAMPLES):
            raise ValueError('Invalid meeting PCM length')
        number, start = PCM_HEADER.unpack_from(payload)
        if number not in (1, 2):
            raise ValueError('Invalid meeting PCM track')
        track = TRACKS[number - 1]
        if self._offsets[track] is None or start != self._frames[track] or start + count > self._max_frames:
            raise ValueError('Meeting PCM is missing, repeated or out of bounds')
        samples = np.array(np.frombuffer(payload, dtype='<f4', offset=PCM_HEADER.size), dtype=np.float32, copy=True)
        if not np.isfinite(samples).all() or np.any(np.abs(samples) > 8):
            raise ValueError('Invalid meeting PCM values')
        samples.setflags(write=False)
        self._emit('audio', AudioChunk(track, start, samples))
        self._frames[track] += count

    def finish(self):
        if self.closed or self.failed or self._pending or self.end is None:
            self.failed = True
            self._pending.clear()
            raise ValueError('Incomplete meeting transport')
        self.closed = True
        return self.end
