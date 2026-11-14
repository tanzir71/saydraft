from types import SimpleNamespace as NS

import numpy as np
import pytest

from saydraft.meetings.vad import MeetingSileroVad
from saydraft.meetings.transcription import MeetingTranscriber
from tests.test_meeting_timeline import captured
from tests.test_meeting_transcription import Asr, Diarizer


class Detector:
    def __init__(self):
        self.queue, self.frames = [], []
    def reset(self):
        self.queue.clear()
    def accept_waveform(self, frame):
        self.frames.append(frame.copy())
    def flush(self):
        # Segment starts before the delayed streaming speech flag would rise.
        self.queue.extend([NS(start=1600, samples=np.zeros(3200, np.float32)),
                           NS(start=6000, samples=np.zeros(2000, np.float32))])
    def empty(self):
        return not self.queue
    @property
    def front(self):
        return self.queue[0]
    def pop(self):
        self.queue.pop(0)


def test_retrospective_onsets_and_tail_are_preserved_and_overlapping_padding_is_merged(tmp_path):
    model = tmp_path / 'silero.onnx'
    model.write_bytes(b'fixture')
    detector = Detector()
    vad = MeetingSileroVad(model, factory=lambda path: detector)
    ranges = vad.speech_ranges(np.ones(8100, np.float32))
    assert ranges == ((0, 8100),)
    assert all(len(frame) == 512 for frame in detector.frames)
    assert not detector.queue


def test_native_range_results_enter_recognition_once_without_using_delayed_frame_flags():
    class Ranges:
        def speech_ranges(self, audio, *, check):
            check()
            return ((0, len(audio)),)
    waveform = np.linspace(.1, .3, 16000, dtype=np.float32)
    audio = captured(waveform, np.empty(0, np.float32), complete=False)
    asr = Asr()
    result = MeetingTranscriber(asr, Diarizer(), detector_factory=Ranges).transcribe(audio)
    assert len(result.utterances) == 1 and np.array_equal(asr.calls[0], waveform)


@pytest.mark.parametrize('ranges', [((-1, 100),), ((0, 17000),), ((0, 8000), (7000, 16000))])
def test_invalid_native_bounds_are_an_explicit_vad_failure(ranges):
    class Ranges:
        def speech_ranges(self, audio, *, check):
            return ranges
    audio = captured(np.ones(16000, np.float32), np.empty(0, np.float32), complete=False)
    result = MeetingTranscriber(Asr(), Diarizer(), detector_factory=Ranges).transcribe(audio)
    assert any(issue.reason == 'vad_failed' for issue in result.issues) and not result.complete
