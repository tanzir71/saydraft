"""Bounded in-memory capture collection and a shared speaker-analysis timeline.

Drain the capture owner's queue continuously on a dedicated worker. This class
does no ASR, model loading or disk I/O. Only a confirmed stopped outcome permits
sealing. Tracks are concatenated, not mixed, so a single diarization call can
cluster speakers globally while original track origins remain available.
"""

from dataclasses import dataclass
import math

import numpy as np

from .audio import SAMPLE_RATE
from .limits import MAX_AUDIO_SAMPLES, TRACK_SEPARATOR_SAMPLES, track_frame_limit
from .process import CaptureOutcome
from .protocol import AudioChunk, CaptureEnd, CaptureEvent, ERROR_REASONS, TRACKS, TrackStarted
from .request import MAX_SECONDS

_SLAB_SAMPLES = SAMPLE_RATE

@dataclass(frozen=True)
class TrackSpan:
    track: str
    offset_seconds: float
    start_frame: int
    end_frame: int

    @property
    def frames(self):
        return self.end_frame - self.start_frame


@dataclass(frozen=True, eq=False)
class MeetingAudio:
    samples: np.ndarray
    tracks: tuple[TrackSpan, ...]
    complete: bool
    issues: tuple[str, ...]

    @property
    def duration(self):
        return max((track.offset_seconds + track.frames / SAMPLE_RATE for track in self.tracks), default=0.)

    def waveform(self, track):
        if track not in self.tracks:
            raise ValueError('Track does not belong to this meeting')
        return self.samples[track.start_frame:track.end_frame]


class MeetingAudioBuffer:
    def __init__(self, *, max_seconds=MAX_SECONDS):
        self._limit = track_frame_limit(max_seconds)
        self._max_seconds = max_seconds
        self._parts = {track: [] for track in TRACKS}
        self._frames = dict.fromkeys(TRACKS, 0)
        self._offsets = dict.fromkeys(TRACKS, None)
        self._ready = self._sealed = False
        self._end = None
        self._issues = []

    @property
    def frames(self):
        return dict(self._frames)

    def consume(self, event):
        if self._sealed or self._end is not None:
            raise RuntimeError('Meeting collection is retired')
        if type(event) is not CaptureEvent:
            raise ValueError('Invalid meeting capture event')
        value = event.value
        if event.kind == 'track':
            if (type(value) is not TrackStarted or value.track not in TRACKS
                    or self._offsets[value.track] is not None
                    or type(value.offset_seconds) not in (int, float) or not math.isfinite(value.offset_seconds)
                    or not 0 <= value.offset_seconds <= self._max_seconds):
                raise ValueError('Invalid meeting track start')
            self._offsets[value.track] = float(value.offset_seconds)
        elif event.kind == 'audio':
            if type(value) is not AudioChunk or value.track not in TRACKS:
                raise ValueError('Invalid meeting audio event')
            samples = np.asarray(value.samples)
            if (self._offsets[value.track] is None or type(value.start_frame) is not int
                    or value.start_frame != self._frames[value.track]
                    or samples.ndim != 1 or samples.dtype.kind != 'f'
                    or not 1 <= len(samples) <= MAX_AUDIO_SAMPLES
                    or self._frames[value.track] + len(samples) > self._limit
                    or not np.isfinite(samples).all() or np.any(np.abs(samples) > 8)):
                raise ValueError('Missing, repeated or invalid meeting audio')
            # Coalesce into fixed slabs: many tiny legal packets cannot turn
            # the frame bound into an unbounded number of Python/NumPy objects.
            position = 0
            while position < len(samples):
                used = self._frames[value.track] % _SLAB_SAMPLES
                if not used:
                    self._parts[value.track].append(np.empty(
                        min(_SLAB_SAMPLES, self._limit - self._frames[value.track]), dtype=np.float32))
                slab = self._parts[value.track][-1]
                count = min(len(samples) - position, len(slab) - used)
                slab[used:used + count] = samples[position:position + count]
                position += count
                self._frames[value.track] += count
        elif event.kind == 'ready':
            if value is not None or self._ready or self._issues or any(v is None for v in self._offsets.values()):
                raise ValueError('Invalid meeting readiness')
            self._ready = True
        elif event.kind == 'error':
            if type(value) is not str or value not in ERROR_REASONS:
                raise ValueError('Invalid meeting failure event')
            if value not in self._issues:
                self._issues.append(value)
        elif event.kind == 'end':
            if (type(value) is not CaptureEnd or type(value.complete) is not bool
                    or type(value.microphone_frames) is not int or type(value.desktop_frames) is not int
                    or value.microphone_frames != self._frames['microphone']
                    or value.desktop_frames != self._frames['desktop']):
                raise ValueError('Meeting completion does not match the admitted audio')
            self._end = value
        else:
            raise ValueError('Unknown meeting capture event')

    def freeze(self, outcome):
        if self._sealed:
            raise RuntimeError('Meeting collection is retired')
        if (type(outcome) is not CaptureOutcome or outcome.stopped is not True
                or type(outcome.complete) is not bool):
            raise RuntimeError('Confirm native capture stopped before analyzing a meeting')
        if outcome.complete and (self._end != outcome.end or self._end is None or not self._end.complete
                or self._issues or not self._ready or not all(self._frames.values())):
            raise ValueError('Meeting success is inconsistent with the collected stream')
        present = [track for track in TRACKS if self._frames[track]]
        total = sum(self._frames.values()) + max(0, len(present) - 1) * TRACK_SEPARATOR_SAMPLES
        waveform = np.empty(total, dtype=np.float32)
        spans, cursor = [], 0
        for index, track in enumerate(present):
            if index:
                waveform[cursor:cursor + TRACK_SEPARATOR_SAMPLES] = 0
                cursor += TRACK_SEPARATOR_SAMPLES
            start = cursor
            for part in self._parts[track]:
                count = min(len(part), self._frames[track] - (cursor - start))
                waveform[cursor:cursor + count] = part[:count]
                cursor += count
            spans.append(TrackSpan(track, self._offsets[track], start, cursor))
        waveform.setflags(write=False)
        issues = list(self._issues)
        if not outcome.complete:
            issues.append('incomplete_capture')
        result = MeetingAudio(waveform, tuple(spans), bool(outcome.complete), tuple(dict.fromkeys(issues)))
        self.discard()
        return result

    def discard(self):
        for parts in self._parts.values():
            parts.clear()
        self._sealed = True
