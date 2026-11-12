"""Session orchestration with injected services and one serial processing worker."""

from __future__ import annotations

import logging
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from saydraft.insert.inserter import InsertionResult
from .container import Services, create_services
from .hotkey_service import HotkeyService
from .preferences import select_context
from .session import DictationSession, SessionInput as Input, SessionState as State
from .segments import SegmentTranscriber
from .preview import PreviewSession, choose_preview_result

logger = logging.getLogger(__name__)


class SessionWorker:
    def __init__(self, services: Services, *, emit=lambda name, *args: None, executor=None,
                 session=None, timer_factory=threading.Timer, keyboard_module=None,
                 services_factory=create_services):
        self.services = services
        self.emit_callback = emit
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-session")
        self.session = session or DictationSession()
        self.timer_factory = timer_factory
        self.services_factory = services_factory
        self._lock = threading.RLock()
        self._timers = []
        self._inflight = 0
        self._closing = False
        self._pending_config = None
        self._background = None
        self._preview = None
        self._preview_language_blocked = False
        self.last_failed_audio = None
        self.last_result = None
        self._retrying_history = False
        self._benchmarking = False
        self.hotkeys = HotkeyService(services.config, start=self.start_recording, stop=self.stop_recording,
                                     cancel=self.cancel, save=self.record_note,
                                     notify=lambda message: self.emit("notification_requested", message),
                                     keyboard_module=keyboard_module)
        self._warm_cleanup()

    def _warm_cleanup(self):
        try:
            warm = getattr(self.services.cleaner, "warm", None)
            if warm is not None:
                warm()
        except Exception:
            logger.warning("Local cleanup warmup unavailable; rules remain available")

    @staticmethod
    def _close_cleanup(cleaner):
        try:
            close = getattr(cleaner, "close", None)
            if close is not None:
                close()
        except Exception:
            logger.warning("Local cleanup closure unavailable; owner-exit job cleanup remains active")

    @property
    def busy(self):
        return self._inflight > 0 or self.session.active

    def _submit(self, function, *args):
        self._inflight += 1

        def run():
            try:
                function(*args)
            finally:
                with self._lock:
                    self._inflight -= 1
                    if self._pending_config is not None and not self.busy and not self._closing:
                        config, self._pending_config = self._pending_config, None
                        self.configure(config)

        try:
            self.executor.submit(run)
        except Exception:
            self._inflight -= 1
            raise

    def emit(self, name, *args):
        try:
            self.emit_callback(name, *args)
        except Exception:
            logger.debug("UI receiver unavailable for %s", name, exc_info=True)

    def _schedule(self, seconds, callback):
        timer = self.timer_factory(seconds, callback)
        timer.daemon = True
        self._timers.append(timer)
        timer.start()

    def _cancel_timers(self):
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()

    def start_recording(self, *, insert_text=True):
        with self._lock:
            if self.busy or self._closing:
                if self._retrying_history:
                    self.emit("notification_requested", "History retry is in progress. Dictation will be ready when it finishes.")
                elif self._benchmarking:
                    self.emit("notification_requested", "Performance check is in progress. Dictation will be ready when it finishes.")
                return False
            target = self.services.context.capture()
            context = select_context(self.services.config, self.services.profiles, target.app_title)
            self.session.dispatch(Input.START)
            generation = self.session.session_id
            self._target = target
            self._context = context
            self._insert_text = insert_text
            self._submit(self._arm, generation)
            return True

    def _arm(self, generation):
        preparing_asr = False
        try:
            self._warm_cleanup()
            set_context = getattr(self.services.asr, "set_context", None)
            if set_context is not None:
                set_context(self._target)
            prepare = getattr(self.services.asr, "prepare", None)
            if prepare is not None:
                preparing_asr = True
                prepare()
                preparing_asr = False
            with self._lock:
                if generation != self.session.session_id or self.session.state != State.ARMING:
                    self.emit("processing_finished", "")
                    return
            recorder = self.services.recorder
            self._background = None
            self._preview_language_blocked = False
            if (hasattr(recorder, "chunk_callback")
                    and self.services.config["stt"].get("background_transcription", True)):
                stt = self.services.config["stt"]
                self._background = SegmentTranscriber(
                    self.services.asr, sample_rate=recorder.sample_rate,
                    energy_threshold=stt.get("vad_energy_threshold", 0.003),
                    aggressiveness=stt.get("vad_aggressiveness", 2))
                self._background.start()
            self._start_preview(generation)
            if hasattr(recorder, "chunk_callback"):
                background, preview = self._background, self._preview

                def feed(audio):
                    if background is not None:
                        background.feed(audio)
                    if preview is not None:
                        try:
                            preview.feed(audio)
                        except Exception:
                            preview.request_finish(discard=True)
                            self.emit("preview_unavailable", generation)

                recorder.chunk_callback = feed if background or preview else None
            with self._lock:
                current = generation == self.session.session_id and self.session.state == State.ARMING
            if not current:
                self._close_background(discard=True)
                self._close_preview(discard=True)
                self.emit("processing_finished", "")
                return
            self.services.recorder.start()
            with self._lock:
                event = self.session.dispatch(Input.ARMED, session_id=generation)
                if event is not None:
                    self.emit("recording_started")
                    limits = self.services.config["recording"]
                    maximum = limits["max_seconds"]
                    warning = limits["warning_seconds"]
                    if 0 < warning < maximum:
                        self._schedule(warning, lambda: self._warn(generation, maximum))
                    self._schedule(maximum, lambda: self._cap(generation))
                    return
            self.services.recorder.stop()  # Released/cancelled while the device opened.
            self._close_background(discard=True)
            self._close_preview(discard=True)
            self.emit("processing_finished", "")
        except Exception:
            logger.exception("Could not arm microphone")
            self.hotkeys._controller.discard_active_recording()
            self._close_background(discard=True)
            self._close_preview(discard=True)
            with self._lock:
                self.session.dispatch(Input.FAIL, session_id=generation)
            self.emit("error", "Speech model unavailable. Download or resume it in Settings → Models."
                      if preparing_asr else "No microphone")

    def _warn(self, generation, maximum):
        with self._lock:
            if generation == self.session.session_id and self.session.state == State.LISTENING:
                self.emit("notification_requested", f"Recording will stop at {maximum // 60}:{maximum % 60:02}. Finish up soon.")

    def _cap(self, generation):
        with self._lock:
            if generation == self.session.session_id and self.session.state == State.LISTENING:
                self.emit("notification_requested", "Recording stopped at the configured time limit.")
                if self.hotkeys._controller.force_stop() is None:
                    self.stop_recording()

    def stop_recording(self):
        with self._lock:
            event = self.session.dispatch(Input.RELEASE)
            if event is None:
                return
            self._cancel_timers()
            self.emit("recording_stopped", float(event.recording_seconds or 0))
            if event.previous == State.ARMING:
                return  # _arm closes the device once its start call returns.
            self._submit(self._finalize, event.session_id, event.recording_seconds,
                         event.state == State.CANCELLED)

    def cancel(self):
        with self._lock:
            previous = self.session.state
            event = self.session.dispatch(Input.CANCEL)
            if event is None:
                return
            self.hotkeys._controller.discard_active_recording()
            self._cancel_timers()
            if self._preview is not None:
                self._preview.request_finish(discard=True)
            if previous == State.LISTENING:
                self.emit("recording_stopped", float(event.recording_seconds or 0))
                self._submit(self._finalize, event.session_id, event.recording_seconds, True)

    def _insert_if_current(self, generation, action):
        with self._lock:
            if (generation != self.session.session_id or self.session.state != State.CLEANING
                    or self._closing):
                return InsertionResult("not_inserted", "none", "cancelled")
            self.session.dispatch(Input.CLEANED, session_id=generation)
            result = action()
            outcome = Input.INSERTED if result.status == "inserted" else Input.NOT_INSERTED
            self.session.dispatch(outcome, session_id=generation, reason=result.reason)
            return result

    def _finalize(self, generation, duration, discard):
        completed_text = ""
        failed = False
        audio_path = None
        raw = ""
        asr_error = None
        try:
            audio = self.services.recorder.stop()
            use_streaming = self.services.config.get("labs", {}).get("use_streaming_result", False)
            if self._preview is not None:
                self._preview.request_finish(discard=discard, flush=use_streaming)
            if not discard:
                self.emit("processing_started")
                if self.services.config["recording"].get("retain_audio", False) and self.services.audio_store:
                    try:
                        audio_path = str(self.services.audio_store.save(
                            audio, getattr(self.services.recorder, "sample_rate", 16000)))
                    except Exception:
                        self.last_failed_audio = audio
                        logger.warning("Audio retention failed; continuing recognition")
                        logger.debug("Audio retention failure detail", exc_info=True)
                        self.emit("notification_requested", "Could not retain audio for retry. Recognition will continue.")
            background = self._close_background(discard=discard)
            if discard:
                return
            if background is not None and not background.failed:
                raw = background.text
            else:
                try:
                    raw = self.services.asr.transcribe(audio).strip()
                    if not raw and background is not None and background.text:
                        raw = background.text
                        self.last_failed_audio = audio
                except Exception as error:
                    self.last_failed_audio = audio
                    if background is None or not background.text:
                        asr_error = error
                    else:
                        raw = background.text
                        self.emit("notification_requested", "Some speech needs retry. The recording is kept in this session.")
            preview_wait = time.perf_counter()
            preview = self._close_preview(discard=not self._english_preview())
            preview_wait = time.perf_counter() - preview_wait
            choice = choose_preview_result(raw, self._model_id(),
                getattr(self.services.asr, "last_language", None) or
                self.services.config["stt"].get("language", "auto"), preview, use_streaming=use_streaming)
            raw = choice.text
            if asr_error is not None and not raw:
                raise asr_error
            if not raw:
                self._save_unrecognized_audio(audio_path, duration, "asr_empty")
                if not audio_path and getattr(self.services.asr, "retry_recommended", False):
                    self.last_failed_audio = audio
                    self.emit("notification_requested", "Try All languages or pin your language in Settings. "
                              "Enable audio history to keep future recordings for retry.")
                with self._lock:
                    self.session.dispatch(Input.NO_SPEECH, session_id=generation)
                return
            with self._lock:
                self.session.dispatch(Input.TRANSCRIBED, session_id=generation)
            timings = {"record": float(duration or 0), **getattr(self.services.asr, "last_timings", {})}
            if background is not None:
                timings["background_stt"] = background.background_asr_seconds
                if not background.failed:
                    timings["vad"] = 0.0
                    timings["lid"] = 0.0  # Tail wall time already includes these stages.
                    timings["stt"] = background.tail_seconds
            if preview is not None:
                timings["background_preview_stt"] = preview.compute_seconds
                timings["stt"] = timings.get("stt", 0) + preview_wait
            result = self.services.processor.process(
                raw, target=self._target, context=self._context,
                model=choice.model, duration_seconds=duration, language=choice.language,
                insert_text=self._insert_text and not choice.review_only, edits=list(choice.edits),
                insert_action=lambda action: self._insert_if_current(generation, action), timings=timings,
                audio_path=audio_path,
            )
            self.last_result = result
            completed_text = result.cleaned_text
            if choice.review_only:
                self.emit("notification_requested", "Preview words saved for review in History; recognition did not finish.")
            if result.history_id is not None:
                self.emit("history_updated", result.history_id)
                if getattr(self.services.asr, "retry_recommended", False):
                    self.emit("notification_requested",
                              "A multilingual retry is available for this recording in History." if audio_path else
                              "Try All languages or pin your language in Settings. "
                              "Enable audio history to keep future recordings for retry.")
            with self._lock:
                if self.session.state == State.CLEANING:
                    if result.history_id is None:
                        self.session.dispatch(Input.FAIL, session_id=generation, reason="history_unavailable")
                    else:
                        self.session.dispatch(Input.CLEANED, session_id=generation)
                        self.session.dispatch(Input.NOT_INSERTED, session_id=generation, reason=result.insertion.reason)
        except Exception:
            failed = True
            if not raw:
                self._save_unrecognized_audio(audio_path, duration, "asr_error")
            logger.exception("Could not complete dictation")
            with self._lock:
                self.session.dispatch(Input.FAIL, session_id=generation)
            self.emit("error", "Could not complete dictation; saved words remain in history.")
        finally:
            self._close_background(discard=True)
            self._close_preview(discard=True)
            if not failed:
                self.emit("processing_finished", completed_text)

    def _save_unrecognized_audio(self, path, duration, reason):
        if not path:
            return
        from saydraft.history import HistoryEntry

        try:
            row_id = self.services.history.append(HistoryEntry(
                self._target.app_title, "", "", self._context.mode, self._context.profile,
                duration, self._model_id(), app_exe=self._target.app_exe,
                app_group=self._target.app_group, audio_path=path,
                language=getattr(self.services.asr, "last_language", None) or
                         self.services.config["stt"].get("language", "auto"),
                edits_json=json.dumps([{"type": reason}])))
            self.emit("history_updated", row_id)
            self.emit("notification_requested", "Recording saved locally. You can retry recognition in History.")
        except Exception:
            logger.error("Could not index retained audio; the local file is preserved")
            logger.debug("Audio history failure detail", exc_info=True)

    def retry_history(self, row):
        with self._lock:
            if (self.busy or self._closing or not row.audio_path or
                    self.services.audio_store is None or self.services.retry_asr is None):
                return False
            self._retrying_history = True
            try:
                self._submit(self._retry_history, row)
            except Exception:
                self._retrying_history = False
                logger.warning("Could not queue History retry")
                self.emit("notification_requested", "Could not start the History retry. Try again after the current work finishes.")
                return False
            return True

    def _retry_history(self, row):
        reading_audio = True
        new_id = 0
        try:
            from saydraft.dictation.types import DictationContext
            from .interfaces import TargetContext

            audio, rate = self.services.audio_store.load(row.audio_path)
            reading_audio = False
            asr = self.services.retry_asr
            raw = asr.transcribe(audio).strip()
            if not raw:
                self.emit("notification_requested", "No speech was recognized in the saved recording.")
                return
            target = TargetContext(app_title=row.app_name, app_exe=row.app_exe or "",
                                   app_group=row.app_group or "general")
            result = self.services.processor.process(
                raw, target=target, context=DictationContext(row.mode, row.profile, row.app_name),
                model=asr.model_id, duration_seconds=len(audio) / rate,
                language=getattr(asr, "last_language", None) or "auto",
                insert_text=False, audio_path=row.audio_path,
                timings=dict(getattr(asr, "last_timings", {})),
                edits=[{"type": "asr_retry", "source_history_id": row.id}])
            self.last_result = result
            if result.history_id is not None:
                new_id = result.history_id
                self.emit("history_updated", new_id)
            else:
                self.emit("notification_requested", "Retry text is kept in this session while History is unavailable.")
        except Exception:
            logger.warning("History recognition retry failed")
            logger.debug("History retry failure detail", exc_info=True)
            self.emit("notification_requested", "Saved recording is unavailable or invalid." if reading_audio else
                      "All languages retry failed. Check the model in Settings → Models.")
        finally:
            self._retrying_history = False
            self.hotkeys._controller.discard_active_recording()
            self.emit("history_retry_finished", new_id)

    def benchmark_hardware(self, *, benchmark=None):
        with self._lock:
            if self.busy or self._closing:
                return False
            if benchmark is None:
                from saydraft.models.benchmark import run_benchmark

                benchmark = run_benchmark
            self._benchmarking = True
            try:
                self._submit(self._benchmark_hardware, benchmark)
            except Exception:
                self._benchmarking = False
                logger.warning("Could not queue performance check")
                return False
            return True

    def _benchmark_hardware(self, benchmark):
        report = None
        try:
            report = benchmark(self.services.asr)
        except Exception:
            logger.warning("Local performance check failed")
            logger.debug("Performance check failure detail", exc_info=True)
        finally:
            self._benchmarking = False
            self.hotkeys._controller.discard_active_recording()
            self.emit("hardware_benchmark_finished", report)

    def _english_preview(self):
        if getattr(self.services.asr, "last_language", None) not in (None, "", "auto", "en"):
            self._preview_language_blocked = True
        return not self._preview_language_blocked

    def is_current_preview(self, generation, *, listening_only=True):
        with self._lock:
            states = (State.LISTENING,) if listening_only else (State.ARMING, State.LISTENING)
            return (generation == self.session.session_id and self.session.state in states
                    and not self._closing and (not listening_only or self._english_preview()))

    def _start_preview(self, generation):
        self._preview = None
        if self.services.preview is None:
            return
        recorder = self.services.recorder
        if not hasattr(recorder, "chunk_callback") or getattr(recorder, "sample_rate", None) != 16000:
            self.emit("preview_unavailable", generation)
            return

        def partial(text):
            # The Qt receiver checks generation/state when queued signals arrive.
            # Never acquire the worker lock from the decoder thread while joining it.
            if self._english_preview():
                self.emit("preview_text_changed", generation, text)
            else:
                preview = self._preview
                if preview is not None:
                    preview.request_finish(discard=True)
                self.emit("preview_unavailable", generation)

        self._preview = PreviewSession(self.services.preview, on_partial=partial,
            on_failed=lambda: self.emit("preview_unavailable", generation))
        self._preview.start()

    def _close_preview(self, *, discard):
        preview, self._preview = self._preview, None
        return preview.finish(discard=discard) if preview is not None else None

    def _close_background(self, *, discard):
        background, self._background = self._background, None
        if hasattr(self.services.recorder, "chunk_callback"):
            self.services.recorder.chunk_callback = None
        return background.finish(discard=discard) if background is not None else None

    def _model_id(self):
        from saydraft.asr.selection import configured_model_id

        used = getattr(self.services.asr, "models_used", None)
        if used:
            return " + ".join(used)
        return getattr(self.services.asr, "model_id", configured_model_id(self.services.config))

    def record_note(self):
        if self.start_recording(insert_text=False):
            self._schedule(3.0, self.stop_recording)

    def configure(self, config):
        with self._lock:
            if self.busy:
                self._pending_config = config
                self.emit("notification_requested", "Settings will apply after the current dictation.")
                return
            pending = self.services.processor.pending_results
            previous = self.services.cleaner
            self.services = self.services_factory(
                config, level_callback=lambda level: self.emit("audio_level_changed", level),
                notify=lambda message: self.emit("notification_requested", message))
            self.services.processor.pending_results.extend(pending)
            if previous is not self.services.cleaner:
                self._close_cleanup(previous)
            self._warm_cleanup()
            self.hotkeys.configure(config)

    def shutdown(self):
        self._closing = True
        self.cancel()
        self.hotkeys.stop()
        self._cancel_timers()
        self._close_cleanup(self.services.cleaner)
        # An in-flight ASR may finish and persist its words, but can no longer paste.
        self.executor.shutdown(wait=False, cancel_futures=False)
