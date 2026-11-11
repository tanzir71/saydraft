import threading

import numpy as np

from saydraft.core.segments import SegmentTranscriber


def detector(frame):
    return bool(np.max(np.abs(frame)) > 0.01)


class Engine:
    def __init__(self):
        self.audio = []
        self.twenty_nine_done = threading.Event()
        self.now = 0.0
        self.last_cost = 0.0

    def transcribe(self, audio):
        self.audio.append(audio.copy())
        self.last_cost = len(audio) / 16000 * 0.01
        self.now += self.last_cost
        if len(self.audio) == 29:
            self.twenty_nine_done.set()
        return f"segment{len(self.audio)}"


def test_sixty_second_fixture_release_only_transcribes_the_last_segment():
    engine = Engine()
    transcriber = SegmentTranscriber(engine, detector=detector, clock=lambda: engine.now)
    speech = np.full(16000, 0.1, dtype=np.float32)
    silence = np.zeros(16000, dtype=np.float32)
    audio = np.concatenate([part for _ in range(29) for part in (speech, silence)] + [speech, speech])
    assert len(audio) == 60 * 16000
    transcriber.start()
    for offset in range(0, len(audio), 1600):
        transcriber.feed(audio[offset:offset + 1600])
    assert engine.twenty_nine_done.wait(5)
    released_at = engine.now
    result = transcriber.finish()
    assert engine.now - released_at <= 1.3 * engine.last_cost
    assert result.text == " ".join(f"segment{index}" for index in range(1, 31))
    assert result.segments == 30
    assert not result.failed
    assert result.samples == len(audio)


def test_silence_does_not_load_or_call_recognition_engine():
    engine = Engine()
    transcriber = SegmentTranscriber(engine, detector=detector)
    transcriber.start()
    transcriber.feed(np.zeros(16000 * 3, dtype=np.float32))
    result = transcriber.finish()
    assert result.text == ""
    assert engine.audio == []


def test_continuous_speech_stays_intact_in_one_segment():
    engine = Engine()
    transcriber = SegmentTranscriber(engine, detector=detector)
    transcriber.start()
    transcriber.feed(np.full(16000 * 3, 0.1, dtype=np.float32))
    result = transcriber.finish()
    assert result.segments == 1
    assert len(engine.audio[0]) == 16000 * 3


def test_transcriber_owns_audio_and_refuses_frames_after_finish():
    engine = Engine()
    transcriber = SegmentTranscriber(engine, detector=detector)
    transcriber.start()
    source = np.full(16000, 0.1, dtype=np.float32)
    transcriber.feed(source)
    source[:] = 0
    assert transcriber.finish().text == "segment1"
    assert not transcriber.feed(source)
    assert transcriber.finish().text == "segment1"


def test_failed_segment_marks_full_recording_fallback_without_hiding_earlier_words():
    engine = Engine()
    original = engine.transcribe

    def transcribe(audio):
        if len(engine.audio) == 1:
            raise RuntimeError("model failure")
        return original(audio)

    engine.transcribe = transcribe
    transcriber = SegmentTranscriber(engine, detector=detector)
    transcriber.start()
    transcriber.feed(np.concatenate([np.full(16000, 0.1), np.zeros(16000), np.full(16000, 0.1)]))
    result = transcriber.finish()
    assert result.failed
    assert result.text == "segment1"


def test_discard_shuts_down_background_thread_without_returning_text():
    transcriber = SegmentTranscriber(Engine(), detector=detector)
    transcriber.start()
    transcriber.feed(np.full(16000, 0.1, dtype=np.float32))
    assert transcriber.finish(discard=True).text == ""
    assert not transcriber._thread.is_alive()
