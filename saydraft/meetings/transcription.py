"""VAD-bounded, speaker-attributed meeting transcription on an analysis worker.

Every retained speech range is transcribed once in chunks of at most 25 seconds.
Prefer speaker changes and quiet boundaries. Overlapping/uncertain speakers stay
explicit instead of assigning the same recognized words to two separate people.
Failures retain other recognized ranges and mark the result incomplete.
"""

from dataclasses import dataclass, replace
import unicodedata

import numpy as np

from .audio import SAMPLE_RATE
from .diarization import DiarizationCancelled
from .timeline import MeetingAudio
from .vad import meeting_detector

_FRAME = 480
_PADDING = 1920
_SILENCE = 9600
_MAX_CHUNK = 25 * SAMPLE_RATE


class AnalysisCancelled(Exception):
    pass


@dataclass(frozen=True)
class Utterance:
    id: int
    track: str
    start: float
    end: float
    speakers: tuple[int, ...]
    text: str
    model_id: str
    language: str | None = None


@dataclass(frozen=True)
class AnalysisIssue:
    track: str
    start: float
    end: float
    reason: str


@dataclass(frozen=True)
class MeetingTranscript:
    utterances: tuple[Utterance, ...]
    issues: tuple[AnalysisIssue, ...]
    capture_complete: bool
    duration: float

    @property
    def complete(self):
        return self.capture_complete and not self.issues


def _check(cancelled):
    if cancelled():
        raise AnalysisCancelled()


def _speech_regions(waveform, detector, cancelled):
    if hasattr(detector, 'speech_ranges'):
        previous_end = 0
        for start, end in detector.speech_ranges(waveform, check=lambda: _check(cancelled)):
            if (type(start) is not int or type(end) is not int
                    or not previous_end <= start < end <= len(waveform)):
                raise ValueError('Invalid meeting speech bounds')
            yield start, end, ()
            previous_end = end
        return
    start, last_speech, quiet_start, pauses = None, 0, None, []
    for offset in range(0, len(waveform), _FRAME):
        _check(cancelled)
        end = min(len(waveform), offset + _FRAME)
        frame = waveform[offset:end]
        if len(frame) != _FRAME:
            frame = np.pad(frame, (0, _FRAME - len(frame)))
        if bool(detector(frame)):
            if start is None:
                start = max(0, offset - _PADDING)
            elif quiet_start is not None:
                pauses.append((quiet_start + offset) // 2)
            last_speech, quiet_start = end, None
        else:
            quiet_start = offset if quiet_start is None else quiet_start
            if start is not None and end - last_speech >= _SILENCE:
                yield start, min(len(waveform), last_speech + _PADDING), tuple(pauses)
                start, quiet_start, pauses = None, None, []
    if start is not None:
        yield start, min(len(waveform), last_speech + _PADDING), tuple(pauses)


def _recognition_ranges(start, end, pauses, boundaries):
    # Tiny neighboring speaker intervals share one uncertain range rather than
    # forcing a recognizer to invent words from a few milliseconds of audio.
    minimum = SAMPLE_RATE // 2
    cuts = [point for point in boundaries if start + minimum <= point <= end - minimum]
    cuts.append(end)
    cursor = start
    for bound in cuts:
        if bound <= cursor or bound - cursor < minimum and bound != end:
            continue
        while cursor < bound:
            stop = min(bound, cursor + _MAX_CHUNK)
            if stop < bound:
                quiet = [point for point in pauses if stop - 3 * SAMPLE_RATE <= point <= stop
                         and point > cursor]
                stop = quiet[-1] if quiet else stop
                if 0 < bound - stop < minimum:
                    stop = bound - minimum
            yield cursor, stop
            cursor = stop


def _text(value):
    if type(value) is not str or not value.strip() or len(value) > 16384:
        return None
    try:
        if (len(value.encode('utf-8')) > 65536
                or any(unicodedata.category(char) == 'Cc' and char not in '\n\r\t' for char in value)):
            return None
    except UnicodeError:
        return None
    return value.strip()


class MeetingTranscriber:
    def __init__(self, asr, diarizer, *, detector_factory=None):
        self.asr, self.diarizer = asr, diarizer
        self.detector_factory = detector_factory or meeting_detector

    def transcribe(self, audio, *, cancelled=lambda: False, on_progress=None):
        if type(audio) is not MeetingAudio or not callable(cancelled):
            raise ValueError('Invalid meeting analysis request')
        if on_progress is not None and not callable(on_progress):
            raise ValueError('Invalid meeting progress callback')
        _check(cancelled)
        utterances, issues = [], []
        for reason in audio.issues:
            issues.append(AnalysisIssue('capture', 0., audio.duration, reason))
        if not audio.tracks:
            return MeetingTranscript((), tuple(issues), audio.complete, audio.duration)
        try:
            turns = self.diarizer.diarize(audio.samples, cancelled=cancelled)
        except DiarizationCancelled as error:
            raise AnalysisCancelled() from error
        except Exception:
            _check(cancelled)
            turns = ()
            issues.append(AnalysisIssue('meeting', 0., audio.duration, 'speaker_analysis_failed'))
        _check(cancelled)
        self.asr.prepare()
        _check(cancelled)
        total_frames = sum(track.frames for track in audio.tracks)
        done = 0
        for track in audio.tracks:
            waveform = audio.waveform(track)
            native_start, native_end = track.start_frame / SAMPLE_RATE, track.end_frame / SAMPLE_RATE
            local_turns = []
            for turn in turns:
                start, end = max(native_start, turn.start), min(native_end, turn.end)
                if start < end:
                    local_turns.append((max(0, round((start - native_start) * SAMPLE_RATE)),
                                        min(track.frames, round((end - native_start) * SAMPLE_RATE)), turn.speaker))
            boundaries = []
            for previous, current in zip(local_turns, local_turns[1:]):
                if previous[2] != current[2] and previous[1] <= current[0]:
                    boundaries.append((previous[1] + current[0]) // 2)
            try:
                detector = self.detector_factory()  # Each track gets fresh VAD state.
            except Exception:
                _check(cancelled)
                issues.append(AnalysisIssue(track.track, track.offset_seconds,
                                            track.offset_seconds + track.frames / SAMPLE_RATE, 'vad_unavailable'))
                done += track.frames
                continue
            regions = iter(_speech_regions(waveform, detector, cancelled))
            while True:
                try:
                    start, end, pauses = next(regions)
                except StopIteration:
                    break
                except AnalysisCancelled:
                    raise
                except Exception:
                    _check(cancelled)
                    issues.append(AnalysisIssue(track.track, track.offset_seconds,
                        track.offset_seconds + track.frames / SAMPLE_RATE, 'vad_failed'))
                    break
                for first, last in _recognition_ranges(start, end, pauses, boundaries):
                    _check(cancelled)
                    speakers = tuple(sorted({speaker for a, b, speaker in local_turns
                        if min(b, last) - max(a, first) >= min(800, last - first)}))
                    begin, finish = track.offset_seconds + first / SAMPLE_RATE, track.offset_seconds + last / SAMPLE_RATE
                    try:
                        raw = self.asr.transcribe(waveform[first:last])
                    except Exception:
                        _check(cancelled)
                        issues.append(AnalysisIssue(track.track, begin, finish, 'recognition_failed'))
                        continue
                    _check(cancelled)
                    text = _text(raw)
                    if text is None:
                        reason = 'empty_recognition' if raw == '' else 'invalid_recognition'
                        issues.append(AnalysisIssue(track.track, begin, finish, reason))
                        continue
                    model_id = getattr(self.asr, 'model_id', None)
                    language = getattr(self.asr, 'last_language', None)
                    if (type(model_id) is not str or not model_id or len(model_id) > 128
                            or language is not None and (type(language) is not str or len(language) > 24)):
                        raise ValueError('Recognition model provenance is unavailable')
                    utterances.append(Utterance(0, track.track, begin, finish, speakers, text, model_id, language))
                    if on_progress:
                        on_progress((done + last) / total_frames)
            done += track.frames
            if on_progress:
                on_progress(done / total_frames)
        _check(cancelled)
        utterances.sort(key=lambda part: (part.start, part.end, part.track))
        return MeetingTranscript(tuple(replace(part, id=index) for index, part in enumerate(utterances, 1)),
                                 tuple(issues), audio.complete, audio.duration)
