import types
from concurrent.futures import Future

import numpy as np
import pytest

from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter
from saydraft.core.session import DictationSession, SessionState as State
from saydraft.core.worker import SessionWorker
from tests.test_processing import make_processor


class Executor:
    def __init__(self, queued=False):
        self.queued = queued
        self.jobs = []
        self.closed = False

    def submit(self, function, *args):
        if self.queued:
            self.jobs.append((function, args))
            return Future()
        future = Future()
        future.set_result(function(*args))
        return future

    def drain(self):
        while self.jobs:
            function, args = self.jobs.pop(0)
            function(*args)

    def shutdown(self, **kwargs):
        self.closed = True


class Recorder:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1
        return np.ones(16000, dtype=np.float32)


class Timer:
    def __init__(self, seconds, callback):
        self.seconds = seconds
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class Keyboard:
    def __init__(self):
        self.added = []
        self.removed = []

    def add_hotkey(self, key, callback, **kwargs):
        self.added.append((key, callback))
        return len(self.added)

    def remove_hotkey(self, handle):
        self.removed.append(handle)


def make_worker(*, queued=False, recorder=None, processor=None):
    clock = types.SimpleNamespace(now=0.0)
    processor, events, notifications = processor or make_processor()
    recorder = recorder or Recorder()
    asr = types.SimpleNamespace(transcribe=lambda audio: "raw transcript", last_timings={"stt": 0.1})
    config = default_config()
    target = TargetContext("start-hwnd", "Notepad")
    services = Services(config, recorder, asr, processor.cleaner, IdentityFormatter(), processor.inserter,
                        types.SimpleNamespace(capture=lambda: target), processor.history, processor, [])
    signals = []
    keyboard = Keyboard()
    executor = Executor(queued)
    worker = SessionWorker(services, emit=lambda *args: signals.append(args), executor=executor,
                           session=DictationSession(clock=lambda: clock.now), timer_factory=Timer,
                           keyboard_module=keyboard)
    return worker, clock, executor, events, signals, keyboard


def test_capture_and_processing_emit_states_and_persist_before_insertion():
    worker, clock, _executor, events, signals, _keyboard = make_worker()
    assert worker.start_recording()
    clock.now = 1.5
    worker.stop_recording()
    assert (worker.services.recorder.started, worker.services.recorder.stopped) == (1, 1)
    assert [event[0] for event in events] == ["history", "insert"]
    assert events[0][1].duration_seconds == 1.5
    assert signals == [("recording_started",), ("recording_stopped", 1.5),
                       ("processing_started",), ("history_updated", 1),
                       ("processing_finished", "clean raw transcript")]
    assert worker.session.state == State.DONE
    assert not worker.busy


def test_model_is_prepared_before_microphone_and_actual_model_is_saved():
    worker, clock, _executor, events, signals, _keyboard = make_worker()
    ordering = []
    worker.services.asr.prepare = lambda: ordering.append("model")
    worker.services.asr.model_id = "parakeet-actual"
    original = worker.services.recorder.start
    worker.services.recorder.start = lambda: (ordering.append("microphone"), original())
    worker.start_recording()
    assert ordering == ["model", "microphone"]
    clock.now = 2
    worker.stop_recording()
    assert events[0][1].model == "parakeet-actual"


def test_cleanup_warm_failure_does_not_block_microphone_and_shutdown_closes_cleaner():
    worker, _clock, _executor, _events, _signals, _keyboard = make_worker()
    calls = []

    def failed_warm():
        calls.append("warm")
        raise OSError("fixture missing runtime")

    worker.services.cleaner.warm = failed_warm
    worker.services.cleaner.close = lambda: calls.append("close")
    assert worker.start_recording() and worker.services.recorder.started == 1
    worker.shutdown()
    assert calls == ["warm", "close"]


def test_contextual_cleanup_preparation_receives_captured_app_and_selected_profile_before_capture():
    from dataclasses import replace

    worker, _clock, _executor, _events, _signals, _keyboard = make_worker()
    warmed = []
    original = worker.services.context.capture()
    worker.services.context.capture = lambda: replace(original, app_title="Mail", app_group="email")
    worker.services.config["dictation"]["profile"] = "email"
    worker.services.cleaner.warm_for_context = lambda context: warmed.append(context)
    assert worker.start_recording() and worker.services.recorder.started == 1
    assert len(warmed) == 1 and (warmed[0].app_title, warmed[0].app_group, warmed[0].profile) == ("Mail", "email", "email")
    worker.shutdown()


def test_settings_replacement_closes_previous_cleaner_before_warming_successor():
    from dataclasses import replace

    worker, _clock, _executor, _events, _signals, _keyboard = make_worker()
    calls = []
    worker.services.cleaner.close = lambda: calls.append("old close")
    cleaner = types.SimpleNamespace(warm=lambda: calls.append("new warm"), close=lambda: None)
    processor, _events, _notifications = make_processor(cleaner=cleaner)
    next_services = replace(worker.services, cleaner=cleaner, processor=processor)
    worker.services_factory = lambda *args, **kwargs: next_services
    worker.configure(default_config())
    assert calls == ["old close", "new warm"] and worker.services is next_services
    worker.shutdown()


def test_missing_model_does_not_open_microphone_and_has_actionable_error():
    worker, clock, executor, events, signals, keyboard = make_worker()

    def missing():
        raise FileNotFoundError("model missing")

    worker.services.asr.prepare = missing
    worker.start_recording()
    assert worker.services.recorder.started == 0
    assert worker.session.state == State.ERROR
    assert "Settings" in signals[-1][1]
    assert not events


def test_route_context_is_set_before_preparation_and_mixed_engine_provenance_is_saved():
    worker, clock, executor, events, signals, keyboard = make_worker()
    ordering = []
    worker.services.asr.set_context = lambda target: ordering.append(("context", target.app_group))
    worker.services.asr.prepare = lambda: ordering.append(("prepare",))
    worker.services.asr.models_used = ["primary", "multilingual"]
    worker.start_recording()
    assert ordering == [("context", "general"), ("prepare",)]
    clock.now = 2
    worker.stop_recording()
    assert events[0][1].model == "primary + multilingual"


def test_audio_retention_is_opt_in_and_write_failure_does_not_drop_words(tmp_path):
    worker, clock, executor, events, signals, keyboard = make_worker()
    calls = []

    def save(*args):
        calls.append(True)
        raise OSError("disk full")

    worker.services.audio_store = types.SimpleNamespace(save=save)
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert not calls
    worker.services.config["recording"]["retain_audio"] = True
    worker.start_recording()
    clock.now = 2
    worker.stop_recording()
    assert calls == [True]
    entries = [event[1] for event in events if event[0] == "history"]
    assert len(entries) == 2
    assert all(entry.raw_text == "raw transcript" and entry.audio_path is None for entry in entries)


def test_unrecognized_opt_in_audio_remains_retriable_in_history(tmp_path):
    from saydraft.data.audio import AudioStore

    worker, clock, executor, events, signals, keyboard = make_worker()
    worker.services.config["recording"]["retain_audio"] = True
    worker.services.audio_store = AudioStore(tmp_path / "audio")
    worker.services.asr.transcribe = lambda audio: ""
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert [event[0] for event in events] == ["history"]
    entry = events[0][1]
    assert entry.raw_text == "" and entry.audio_path
    assert worker.services.audio_store.load(entry.audio_path)[0].size == 16000


def test_cancelled_capture_does_not_retain_audio_even_when_opted_in(tmp_path):
    from saydraft.data.audio import AudioStore

    worker, clock, executor, events, signals, keyboard = make_worker()
    worker.services.config["recording"]["retain_audio"] = True
    worker.services.audio_store = AudioStore(tmp_path / "audio")
    worker.start_recording()
    clock.now = 2
    worker.cancel()
    assert not events
    assert not worker.services.audio_store.root.exists()


def test_empty_whole_clip_retry_keeps_previously_recognized_segment_words():
    worker, clock, executor, events, signals, keyboard = make_worker()
    worker.services.asr.transcribe = lambda audio: ""
    worker.start_recording()
    worker._background = types.SimpleNamespace(finish=lambda **kwargs: types.SimpleNamespace(
        failed=True, text="previously recognized words", background_asr_seconds=0.1, tail_seconds=0.0))
    clock.now = 2
    worker.stop_recording()
    assert events[0][0] == "history"
    assert events[0][1].raw_text == "previously recognized words"


def test_history_retry_appends_reviewable_result_without_insertion(tmp_path):
    import json

    from saydraft.data.audio import AudioStore
    from saydraft.history import HistoryEntry, DictationHistoryStore

    processor, events, notifications = make_processor(history=DictationHistoryStore(tmp_path / "history.db"))
    worker, clock, executor, events, signals, keyboard = make_worker(
        processor=(processor, events, notifications), queued=True)
    store = worker.services.history
    worker.services.audio_store = AudioStore(tmp_path / "audio")
    path = str(worker.services.audio_store.save(np.ones(16000, dtype=np.float32)))
    store.append(HistoryEntry("Notepad", "original words", "Original words.", "balanced", "notes",
                              1, "primary", audio_path=path))
    original = store.list_recent()[0]
    worker.services.retry_asr = types.SimpleNamespace(
        transcribe=lambda audio: "recovered words", model_id="whisper-large-v3-turbo", last_language="en", last_timings={})
    assert worker.retry_history(original)
    assert not worker.start_recording() and not worker.retry_history(original)
    executor.drain()
    rows = store.list_recent()
    assert len(rows) == 2 and rows[1] == original
    assert rows[0].raw_text == "recovered words" and rows[0].audio_path == path
    assert json.loads(rows[0].edits_json) == [{"type": "asr_retry", "source_history_id": original.id}]
    assert not [event for event in events if event[0] == "insert"]
    assert ("history_retry_finished", rows[0].id) in signals
    assert not worker.busy


def test_failed_retry_queue_does_not_leave_worker_busy():
    worker, clock, executor, events, signals, keyboard = make_worker()
    worker.services.audio_store = object()
    worker.services.retry_asr = object()

    def rejected(*args):
        raise RuntimeError("executor unavailable")

    executor.submit = rejected
    assert not worker.retry_history(types.SimpleNamespace(audio_path="local.wav"))
    assert not worker.busy and not worker._retrying_history


def test_warning_and_soft_cap_are_configurable_and_stop_once():
    worker, clock, _executor, events, signals, _keyboard = make_worker()
    worker.start_recording()
    timers = list(worker._timers)
    assert [timer.seconds for timer in timers] == [540, 600]
    assert all(timer.started for timer in timers)
    timers[0].callback()
    assert ("notification_requested", "Recording will stop at 10:00. Finish up soon.") in signals
    clock.now = 600
    timers[1].callback()
    assert [event[0] for event in events] == ["history", "insert"]
    assert all(timer.cancelled for timer in timers)
    assert worker.services.recorder.stopped == 1


@pytest.mark.parametrize("seconds", [0, 0.499])
def test_short_recording_does_not_reach_asr_or_history(seconds):
    worker, clock, _executor, events, signals, _keyboard = make_worker()
    worker.services.asr.transcribe = lambda audio: pytest.fail("short audio reached ASR")
    worker.start_recording()
    clock.now = seconds
    worker.stop_recording()
    assert events == []
    assert worker.session.state == State.CANCELLED
    assert signals[-1] == ("processing_finished", "")


def test_cancelled_recording_is_discarded_without_paste():
    worker, clock, _executor, events, _signals, _keyboard = make_worker()
    worker.start_recording()
    clock.now = 1
    worker.cancel()
    assert events == []
    assert worker.services.recorder.stopped == 1
    assert worker.session.state == State.CANCELLED


def test_release_before_queued_arming_keeps_device_closed_and_ignores_new_press_until_ready():
    worker, _clock, executor, events, _signals, _keyboard = make_worker(queued=True)
    worker.start_recording()
    worker.stop_recording()
    assert not worker.start_recording()
    executor.drain()
    assert worker.services.recorder.started == 0
    assert worker.services.recorder.stopped == 0
    assert events == []
    assert worker.start_recording()
    executor.drain()
    worker.cancel()
    executor.drain()


def test_cancel_during_asr_keeps_words_in_history_without_paste():
    worker, clock, executor, events, _signals, _keyboard = make_worker(queued=True)
    worker.start_recording()
    executor.drain()
    clock.now = 1
    worker.stop_recording()
    worker.cancel()
    assert not worker.start_recording()
    executor.drain()
    assert [event[0] for event in events] == ["history"]
    assert worker.last_result.raw_text == "raw transcript"
    assert worker.session.state == State.CANCELLED


def test_save_hotkey_uses_same_capture_pipeline_without_insertion():
    worker, clock, _executor, events, _signals, _keyboard = make_worker()
    worker.record_note()
    clock.now = 3
    worker._timers[-1].callback()
    assert [event[0] for event in events] == ["history"]
    assert worker.session.state == State.NOT_INSERTED


def test_no_microphone_is_reported_and_does_not_stick_busy():
    class MissingRecorder(Recorder):
        def start(self):
            raise RuntimeError("device unavailable")
    worker, _clock, _executor, events, signals, _keyboard = make_worker(recorder=MissingRecorder())
    worker.start_recording()
    assert ("error", "No microphone") in signals
    assert ("recording_started",) not in signals
    assert not worker.busy
    assert events == []
    assert worker.session.state == State.ERROR


def test_keyboard_backend_lifetime_and_save_hotkey():
    worker, _clock, _executor, _events, _signals, keyboard = make_worker()
    worker.hotkeys.start()
    assert [key for key, callback in keyboard.added] == ["f9", "f9", "ctrl+win", "ctrl+win", "esc", "f10"]
    worker.hotkeys.stop()
    assert sorted(keyboard.removed) == list(range(1, 7))
    assert not worker.hotkeys.enabled


def test_keyboard_health_recovery_reregisters_save_hotkey():
    worker, _clock, _executor, _events, signals, keyboard = make_worker()
    worker.hotkeys.start()
    worker.hotkeys._controller.restart_if_dead = lambda: True
    assert worker.hotkeys.restart_if_dead()
    assert keyboard.removed == [6]
    assert keyboard.added[-1][0] == "f10"
    assert ("notification_requested", "Saydraft restarted hotkeys after a listener error.") in signals
    worker.hotkeys.stop()


def test_shutdown_prevents_paste_but_allows_inflight_words_to_be_saved():
    worker, clock, executor, events, _signals, _keyboard = make_worker(queued=True)
    worker.start_recording()
    executor.drain()
    clock.now = 1
    worker.stop_recording()
    worker.shutdown()
    executor.drain()
    assert [event[0] for event in events] == ["history"]
    assert executor.closed
    assert not worker.start_recording()


def test_empty_asr_result_has_explicit_terminal_state():
    worker, clock, _executor, events, _signals, _keyboard = make_worker()
    worker.services.asr.transcribe = lambda audio: ""
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert events == []
    assert worker.session.state == State.CANCELLED
    assert worker.session.events[-1].reason == "no_speech"


@pytest.mark.parametrize("raw", ["", "available primary words"])
def test_unsupported_language_recommends_model_choice_when_audio_history_is_off(raw):
    worker, clock, _executor, _events, signals, _keyboard = make_worker()
    worker.services.asr.transcribe = lambda audio: raw
    worker.services.asr.retry_recommended = True
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert any(item[0] == "notification_requested" and "All languages" in item[1] for item in signals)
    if not raw:
        np.testing.assert_array_equal(worker.last_failed_audio, np.ones(16000, dtype=np.float32))


def test_cancel_during_cleanup_persists_words_but_prevents_insertion():
    worker, clock, _executor, events, _signals, _keyboard = make_worker()

    def clean(raw, context):
        worker.cancel()
        return "preserved cleanup"

    worker.services.cleaner.process_transcript = clean
    worker.start_recording()
    clock.now = 1
    worker.stop_recording()
    assert [event[0] for event in events] == ["history"]
    assert events[0][1].cleaned_text == "preserved cleanup"
    assert worker.session.state == State.CANCELLED


def test_settings_wait_for_active_session_and_preserve_failed_history_results():
    from dataclasses import replace

    def unavailable(entry):
        raise OSError("history locked")

    processor = make_processor(history=types.SimpleNamespace(append=unavailable))
    worker, clock, _executor, _events, _signals, _keyboard = make_worker(processor=processor)
    original = worker.services
    next_processor, _events, _notifications = make_processor()
    replacement = replace(original, processor=next_processor)
    worker.services_factory = lambda config, **kwargs: replacement
    worker.start_recording()
    worker.configure(default_config())
    assert worker.services is original
    clock.now = 1
    worker.stop_recording()
    assert worker.services is replacement
    assert next_processor.pending_results[0].raw_text == "raw transcript"


class SegmentRecorder(Recorder):
    sample_rate = 16000
    chunk_callback = None

    def __init__(self):
        super().__init__()
        self.audio = np.concatenate((np.full(16000, 0.1), np.zeros(16000), np.full(16000, 0.1)))

    def start(self):
        super().start()
        if self.chunk_callback:
            self.chunk_callback(self.audio)

    def stop(self):
        self.stopped += 1
        return self.audio


def test_background_segments_are_wired_through_the_session_without_whole_clip_asr():
    recorder = SegmentRecorder()
    worker, clock, _executor, events, _signals, _keyboard = make_worker(recorder=recorder)
    lengths = []
    worker.services.asr.last_timings = {"vad": 0.1, "lid": 0.2, "stt": 0.3}
    worker.services.asr.transcribe = lambda audio: lengths.append(len(audio)) or "segment words"
    worker.start_recording()
    clock.now = 3
    worker.stop_recording()
    assert len(lengths) == 2
    assert all(length < len(recorder.audio) for length in lengths)
    assert events[0][1].raw_text == "segment words segment words"
    import json

    assert json.loads(events[0][1].timings_json)["lid"] == 0.0
    assert worker.session.state == State.DONE


def test_background_error_falls_back_to_the_complete_retained_recording():
    recorder = SegmentRecorder()
    worker, clock, _executor, events, _signals, _keyboard = make_worker(recorder=recorder)

    def transcribe(audio):
        if len(audio) != len(recorder.audio):
            raise RuntimeError("segment failed")
        return "all words recovered"

    worker.services.asr.transcribe = transcribe
    worker.start_recording()
    clock.now = 3
    worker.stop_recording()
    assert events[0][1].raw_text == "all words recovered"
    assert worker.session.state == State.DONE


def test_background_mode_can_be_disabled_for_a_single_whole_clip_pass():
    recorder = SegmentRecorder()
    worker, clock, _executor, _events, _signals, _keyboard = make_worker(recorder=recorder)
    worker.services.config["stt"]["background_transcription"] = False
    lengths = []
    worker.services.asr.transcribe = lambda audio: lengths.append(len(audio)) or "whole clip"
    worker.start_recording()
    clock.now = 3
    worker.stop_recording()
    assert lengths == [len(recorder.audio)]
