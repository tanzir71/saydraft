import json
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.model_ids import PREVIEW_MODEL
from saydraft.core.session import SessionState as State
from tests.test_session_worker import Recorder, make_worker


class ChunkRecorder(Recorder):
    sample_rate = 16000
    chunk_callback = None

    def start(self):
        super().start()
        for _ in range(10):
            if self.chunk_callback:
                self.chunk_callback(np.ones(1600, dtype=np.float32))


class Stream:
    complete = True
    compute_seconds = 0.1

    def __init__(self, callback):
        self.callback = callback
        self.decoded = threading.Event()
        self.finished = self.discarded = 0
        self.fail = False

    def feed(self, audio):
        self.callback("available partial words")
        self.decoded.set()
        if self.fail:
            raise RuntimeError("preview failed")

    def finish(self):
        self.finished += 1
        return "complete streaming words"

    def discard(self):
        self.discarded += 1


def fixture(*, use_streaming=False, create=None, background=False):
    worker, clock, executor, events, signals, keyboard = make_worker(recorder=ChunkRecorder())
    worker.services.asr.last_language = 'en'
    streams = []

    def factory(callback):
        stream = Stream(callback)
        streams.append(stream)
        return stream

    worker.services.config["stt"]["background_transcription"] = background
    worker.services.config["labs"].update(live_preview=True, use_streaming_result=use_streaming)
    worker.services.preview = SimpleNamespace(create_session=create or factory)
    return worker, clock, events, signals, streams


def test_unknown_primary_language_cannot_be_replaced_by_english_preview():
    worker, clock, events, signals, streams = fixture(use_streaming=True)
    worker.services.asr.last_language = None
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    clock.now = 1
    worker.stop_recording()
    assert events[0][1].raw_text == 'raw transcript'
    assert events[0][1].language == 'und'
    assert streams[0].finished == 1  # Preview completes, but cannot replace the unknown primary.


@pytest.mark.parametrize("streaming", [False, True])
def test_default_result_wins_unless_complete_streaming_explicitly_selected(streaming):
    worker, clock, events, signals, streams = fixture(use_streaming=streaming)
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    generation = worker.session.session_id
    assert not events  # No partial can persist or insert before release.
    assert worker.is_current_preview(generation)
    clock.now = 1
    worker.stop_recording()
    entry = events[0][1]
    assert entry.raw_text == ("complete streaming words" if streaming else "raw transcript")
    assert (entry.model == PREVIEW_MODEL) is streaming
    if streaming:
        assert json.loads(entry.edits_json)[1]["text"] == "raw transcript"
    assert streams[0].finished == int(streaming) and streams[0].discarded == 1
    assert worker._preview is None and worker.services.recorder.chunk_callback is None
    assert worker.session.state == State.DONE and not worker.is_current_preview(generation)


@pytest.mark.parametrize("error", [False, True])
def test_primary_empty_or_failed_recovers_available_preview_for_review_only(error):
    worker, clock, events, signals, streams = fixture()

    def primary(audio):
        if error:
            raise RuntimeError("primary decoder failed")
        return ""

    worker.services.asr.transcribe = primary
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    clock.now = 1
    worker.stop_recording()
    assert [event[0] for event in events] == ["history"]
    assert events[0][1].raw_text == "available partial words"
    assert json.loads(events[0][1].edits_json)[0]["type"] == "preview_recovery"
    assert worker.session.state == State.NOT_INSERTED and streams[0].finished == 0


def test_missing_preview_keeps_normal_dictation_available():
    def missing(callback):
        raise FileNotFoundError("optional weights missing")

    worker, clock, events, signals, streams = fixture(create=missing)
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert events[0][1].raw_text == "raw transcript"
    assert any(signal[0] == "preview_unavailable" for signal in signals)
    assert worker.session.state == State.DONE


def test_cancel_during_preview_preparation_does_not_open_microphone():
    def prepare(callback):
        worker.cancel()
        stream = Stream(callback)
        streams.append(stream)
        return stream

    streams = []
    worker, clock, events, signals, _created = fixture(create=prepare)
    worker.start_recording()
    assert worker.services.recorder.started == 0
    assert worker.session.state == State.CANCELLED and not events
    assert streams[0].discarded == 1 and worker._preview is None and not worker.busy


def test_cancelled_preview_never_saves_or_inserts_words_and_old_updates_are_stale():
    worker, clock, events, signals, streams = fixture(use_streaming=True)
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    generation = worker.session.session_id
    clock.now = 1
    worker.cancel()
    assert not events and streams[0].finished == 0 and streams[0].discarded == 1
    worker.start_recording()
    assert not worker.is_current_preview(generation)
    worker.cancel()


def test_detected_non_english_blocks_stream_selection_even_after_later_english_segment():
    worker, clock, events, signals, streams = fixture(use_streaming=True)
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    worker.services.asr.last_language = "bn"
    assert not worker.is_current_preview(worker.session.session_id)
    worker.services.asr.last_language = "en"
    clock.now = 1
    worker.stop_recording()
    assert events[0][1].raw_text == "raw transcript"


def test_optional_preview_and_background_final_recognition_receive_same_recording():
    worker, clock, events, signals, streams = fixture(background=True)
    worker.start_recording()
    assert streams[0].decoded.wait(1)
    clock.now = 1
    worker.stop_recording()
    assert events[0][1].raw_text == "raw transcript"
    assert "background_preview_stt" in json.loads(events[0][1].timings_json)
    assert worker._preview is worker._background is None
