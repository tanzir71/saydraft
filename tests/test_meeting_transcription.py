import numpy as np
import pytest

from saydraft.meetings.diarization import SpeakerTurn
from saydraft.meetings.transcription import AnalysisCancelled, MeetingTranscriber
from tests.test_meeting_timeline import captured


class Asr:
    model_id, last_language = 'parakeet-fixture', 'en'
    def __init__(self, outputs=None, action=lambda: None):
        self.outputs, self.action, self.calls, self.prepares = outputs, action, [], 0
    def prepare(self):
        self.prepares += 1
    def transcribe(self, audio):
        self.calls.append(audio.copy())
        self.action()
        value = self.outputs[len(self.calls) - 1] if self.outputs is not None else 'Recognized words.'
        if isinstance(value, Exception):
            raise value
        return value


class Diarizer:
    def __init__(self, turns=(), error=None):
        self.turns, self.error, self.calls = turns, error, []
    def diarize(self, audio, **kwargs):
        self.calls.append(audio.copy())
        if self.error:
            raise self.error
        return self.turns


def transcriber(asr, diarizer, *, detector_factory=None):
    return MeetingTranscriber(asr, diarizer, detector_factory=detector_factory or (
        lambda: lambda frame: np.max(np.abs(frame)) > .001))


def test_two_tracks_keep_original_clock_origins_and_use_one_global_speaker_analysis():
    audio = captured(np.full(16000, .1, np.float32), np.full(32000, .2, np.float32), offsets=(.2, 1.5))
    asr = Asr(['Local words.', 'Remote words.'])
    speakers = Diarizer([SpeakerTurn(0., 1., 0), SpeakerTurn(2., 4., 1)])
    result = transcriber(asr, speakers).transcribe(audio)
    assert result.complete and len(speakers.calls) == 1 and asr.prepares == 1
    assert [(u.id, u.track, u.start, u.end, u.speakers, u.text) for u in result.utterances] == [
        (1, 'microphone', .2, 1.2, (0,), 'Local words.'), (2, 'desktop', 1.5, 3.5, (1,), 'Remote words.')]
    assert all(u.model_id == 'parakeet-fixture' and u.language == 'en' for u in result.utterances)


def test_continuous_speech_is_bounded_without_missing_or_repeating_a_sample():
    waveform = np.linspace(.1, .5, 60 * 16000, dtype=np.float32)
    audio = captured(waveform, np.empty(0, np.float32), complete=False)
    asr = Asr()
    result = transcriber(asr, Diarizer([SpeakerTurn(0., 60., 0)])).transcribe(audio)
    assert len(asr.calls) == 3 and max(map(len, asr.calls)) <= 25 * 16000
    assert np.array_equal(np.concatenate(asr.calls), waveform)
    assert not result.complete and result.issues[0].reason == 'incomplete_capture'


def test_speaker_changes_split_at_the_gap_but_overlapping_speakers_do_not_duplicate_words():
    audio = captured(np.full(64000, .1, np.float32), np.empty(0, np.float32), complete=False)
    asr = Asr()
    result = transcriber(asr, Diarizer([SpeakerTurn(0., 2., 0), SpeakerTurn(2., 4., 1)])).transcribe(audio)
    assert [u.speakers for u in result.utterances] == [(0,), (1,)]
    assert np.array_equal(np.concatenate(asr.calls), audio.samples)
    asr = Asr()
    result = transcriber(asr, Diarizer([SpeakerTurn(0., 3., 0), SpeakerTurn(1., 4., 1)])).transcribe(audio)
    assert len(asr.calls) == 1 and result.utterances[0].speakers == (0, 1)


def test_long_speech_prefers_a_short_quiet_pause_before_the_limit():
    waveform = np.full(30 * 16000, .1, np.float32)
    waveform[24 * 16000:round(24.3 * 16000)] = 0
    audio = captured(waveform, np.empty(0, np.float32), complete=False)
    asr = Asr()
    transcriber(asr, Diarizer()).transcribe(audio)
    assert len(asr.calls) == 2 and 24 * 16000 < len(asr.calls[0]) < 25 * 16000
    assert np.array_equal(np.concatenate(asr.calls), waveform)


def test_silence_does_not_create_transcript_text_and_each_track_gets_fresh_vad_state():
    audio = captured(np.zeros(16000, np.float32), np.zeros(16000, np.float32))
    detectors = []
    def factory():
        detectors.append(object())
        return lambda _frame: False
    asr = Asr()
    result = transcriber(asr, Diarizer(), detector_factory=factory).transcribe(audio)
    assert result.complete and not result.utterances and not asr.calls and len(detectors) == 2


def test_native_speaker_failure_retains_recognition_with_unknown_speakers():
    audio = captured(np.ones(16000, np.float32), np.ones(16000, np.float32))
    result = transcriber(Asr(), Diarizer(error=ValueError('native error'))).transcribe(audio)
    assert len(result.utterances) == 2 and all(not u.speakers for u in result.utterances)
    assert not result.complete and result.issues[0].reason == 'speaker_analysis_failed'


@pytest.mark.parametrize('output,reason', [(RuntimeError('model failed'), 'recognition_failed'),
    ('', 'empty_recognition'), ('bad\0text', 'invalid_recognition'), ('\ud800', 'invalid_recognition')])
def test_failed_ranges_do_not_discard_other_recognition_or_claim_completeness(output, reason):
    audio = captured(np.ones(16000, np.float32), np.ones(16000, np.float32))
    result = transcriber(Asr([output, 'Remaining words.']), Diarizer()).transcribe(audio)
    assert len(result.utterances) == 1 and result.utterances[0].text == 'Remaining words.'
    assert not result.complete and result.issues[0].reason == reason


@pytest.mark.parametrize('text', ['বাংলা কথা।', 'هذه ملاحظات.', '会議のメモです。', '会议记录。', '회의 메모입니다.'])
def test_recognized_scripts_are_preserved_without_ascii_rewrites(text):
    audio = captured(np.ones(16000, np.float32), np.empty(0, np.float32), complete=False)
    assert transcriber(Asr([text]), Diarizer()).transcribe(audio).utterances[0].text == text


def test_cancellation_before_analysis_and_during_asr_discards_late_text():
    audio = captured(np.ones(16000, np.float32), np.empty(0, np.float32), complete=False)
    asr, speakers = Asr(), Diarizer()
    with pytest.raises(AnalysisCancelled):
        transcriber(asr, speakers).transcribe(audio, cancelled=lambda: True)
    assert not speakers.calls and not asr.calls
    cancelled = [False]
    asr.action = lambda: cancelled.__setitem__(0, True)
    with pytest.raises(AnalysisCancelled):
        transcriber(asr, speakers).transcribe(audio, cancelled=lambda: cancelled[0])


def test_vad_model_failure_on_one_track_preserves_the_other_track():
    audio = captured(np.ones(16000, np.float32), np.ones(16000, np.float32))
    calls = []
    def detector_factory():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('unavailable VAD')
        return lambda _frame: True
    result = transcriber(Asr(), Diarizer(), detector_factory=detector_factory).transcribe(audio)
    assert len(result.utterances) == 1 and result.utterances[0].track == 'desktop'
    assert result.issues[0].reason == 'vad_unavailable' and not result.complete
