"""Session orchestration with injected services and one serial processing worker."""

from __future__ import annotations

import logging
import json
import math
import threading
import time
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

from saydraft.insert.inserter import InsertionResult
from .container import Services, create_services
from .hotkey_service import HotkeyService
from .preferences import select_context
from .session import DictationSession, SessionInput as Input, SessionState as State
from .segments import SegmentTranscriber
from .preview import PreviewSession, choose_preview_result
from .context import ForegroundContextProvider
from .interfaces import insertion_block
from .corrections import CorrectionController, DictionaryChange
from .bar_status import BarPhase, BarStatus

logger = logging.getLogger(__name__)

# §1 row 8: with-LLM release-to-text p95 target. Cleanup retains its smaller cap.
RELEASE_TO_TEXT_BUDGET_SECONDS = 2.0


class SessionWorker:
    def __init__(self, services: Services, *, emit=lambda name, *args: None, executor=None,
                 session=None, timer_factory=threading.Timer, keyboard_module=None,
                 services_factory=create_services, bar_emit=None):
        self.services = services
        self.emit_callback = emit
        self.bar_status = BarStatus(bar_emit)
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-session")
        self.session = session or DictationSession()
        self.timer_factory = timer_factory
        self.services_factory = services_factory
        self._lock = threading.RLock()
        self._cancel_request = threading.Event()
        self._timers = []
        self._inflight = 0
        self._capturing_context = False
        self._closing = False
        self._pending_config = None
        self._background = None
        self._preview = None
        self._preview_language_blocked = False
        self._record_request_current = None
        self.last_failed_audio = None
        self.last_result = None
        self._retrying_history = False
        self._benchmarking = False
        self.corrections = CorrectionController(executor=self.executor,
            current=lambda generation: generation == self.session.session_id and not self._closing
                and not self._cancel_request.is_set(), emit=self.emit, known_terms=self._dictionary_terms)
        self.hotkeys = HotkeyService(services.config, start=lambda: self.start_recording(_return_generation=True),
                                     start_guarded=lambda current: self.start_recording(
                                         _return_generation=True, request_current=current),
                                     stop=self.stop_recording,
                                     cancel=self.cancel, save=self.record_note,
                                     notify=lambda message: self.emit("notification_requested", message),
                                     keyboard_module=keyboard_module,
                                     stop_session=lambda result: self.stop_recording(
                                         released_at=result.stopped_at, session_id=result.session_id),
                                     timer_factory=timer_factory, paste=self.paste_last)
        self._prepare_context()
        self._warm_cleanup()

    def _prepare_context(self):
        prepare = getattr(self.services.context, "prepare", None)
        if prepare is not None:
            try:
                prepare()
            except Exception:
                logger.warning("Field context preparation unavailable; unverified delivery will be refused")

    @staticmethod
    def _close_context(context):
        close = getattr(context, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                logger.warning("Field context retirement unavailable")

    def _field_guard(self, target):
        verify = getattr(self.services.context, "verify", None)
        return (lambda: verify(target)) if verify is not None else None

    def _dictionary_terms(self):
        from itertools import chain, islice
        glossary = getattr(self.services.cleaner, "glossary", None)
        return tuple(islice(chain(getattr(glossary, "user_terms", ()),
            getattr(glossary, "protected_terms", ())), 1024))

    def poll_corrections(self):
        self.corrections.poll()

    def is_current_correction(self, suggestion):
        return self.corrections.is_current(suggestion)

    def preview_style(self, request):
        from .style_preview import MAX_PREVIEW, StylePreviewResult
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if (self.busy or self._closing or not isinstance(request.text, str)
                    or not request.text or len(request.text) > MAX_PREVIEW):
                return False
            if request.model_settings != json.dumps(self.services.config["llm"], sort_keys=True):
                self.emit("style_preview_finished", StylePreviewResult(request, decision="apply_settings"))
                return True
            self._submit(self._preview_style, request)
            return True
        except Exception:
            self.emit("style_preview_finished", StylePreviewResult(request))
            return True
        finally:
            self._lock.release()

    def _preview_style(self, request):
        from .style_preview import StylePreviewResult, render_style_preview
        result = StylePreviewResult(request, decision="obsolete")
        try:
            if not self._closing and self._pending_config is None:
                self._warm_cleanup(request.context)
                result = render_style_preview(request, llm=self.services.cleaner.llm, deadline=time.monotonic() + 2)
        except Exception:
            result = StylePreviewResult(request)
        self.emit("style_preview_finished", result)

    def add_correction(self, suggestion, *, automatic=False):
        if not self._lock.acquire(blocking=False):
            return False
        try:
            cfg = self.services.config["dictation"]
            path = getattr(getattr(self.services.cleaner, "cfg", None), "glossary_path", "")
            if (self.busy or self._closing or not path or not cfg.get("learn_corrections", False)
                    or (automatic and not cfg.get("auto_add_dictionary", False))
                    or not self.corrections.claim(suggestion)):
                return False
            self._submit(self._change_dictionary, path, suggestion, None)
            return True
        except Exception:
            self.emit("dictionary_changed", DictionaryChange("error"))
            return False
        finally:
            self._lock.release()

    def undo_correction(self, receipt):
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self.busy or self._closing:
                return False
            self._submit(self._change_dictionary, receipt.dictionary, None, receipt)
            return True
        except Exception:
            self.emit("dictionary_changed", DictionaryChange("error", receipt))
            return False
        finally:
            self._lock.release()

    def _change_dictionary(self, path, suggestion, receipt):
        from pathlib import Path
        from saydraft.dictionary.store import add_term, undo_learning
        if self._closing or (suggestion is not None and not self.corrections.claim_current(suggestion)):
            self.emit("dictionary_changed", DictionaryChange("obsolete"))
            return
        try:
            if suggestion is not None:
                receipt = add_term(path, suggestion.candidate.term, learned=True)
                status = "added" if receipt is not None else "unchanged"
            else:
                status = "undone" if undo_learning(path, receipt) else "stale"
        except (OSError, ValueError):
            self.emit("dictionary_changed", DictionaryChange("error", receipt if suggestion is None else None))
            return
        # This task shares the transcript executor; cleanup never races its reload.
        try:
            cleaner = self.services.cleaner
            current_path = getattr(getattr(cleaner, "cfg", None), "glossary_path", "")
            reload = getattr(cleaner, "reload_glossary", None)
            if reload is not None and current_path and Path(current_path).resolve() == Path(path).resolve():
                reload()
        except Exception:
            logger.warning("Dictionary refresh unavailable; apply Settings to refresh cleanup")
        self.emit("dictionary_changed", DictionaryChange(status, receipt if status == "added" else None))

    def _warm_cleanup(self, context=None):
        try:
            contextual = getattr(self.services.cleaner, "warm_for_context", None)
            if contextual is not None:
                contextual(context or select_context(self.services.config, self.services.profiles, None))
                return
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
        return self._capturing_context or self._inflight > 0 or self.session.active

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

    @staticmethod
    def _request_current(guard):
        try:
            return guard is None or bool(guard())
        except Exception:
            return False

    def _capture_request_current(self, generation):
        return (generation == self.session.session_id and self.session.state == State.ARMING
            and not self._closing and not self._cancel_request.is_set()
            and self._request_current(self._record_request_current))

    def _reject_arming(self, generation):
        with self._lock:
            self.session.dispatch(Input.CANCEL, session_id=generation, reason="request_expired")
            if generation == self.session.session_id:
                self.hotkeys._controller.discard_active_recording()
        self.bar_status.session(generation, BarPhase.IDLE)
        self.emit("processing_finished", "")

    def start_recording(self, *, insert_text=True, _return_generation=False, request_current=None):
        # Native action dispatch must not wait behind Settings while Settings
        # retires that same dispatcher. A locked worker is temporarily busy.
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self.busy or self._closing or not self._request_current(request_current):
                if self._retrying_history:
                    self.emit("notification_requested", "History retry is in progress. Dictation will be ready when it finishes.")
                elif self._benchmarking:
                    self.emit("notification_requested", "Performance check is in progress. Dictation will be ready when it finishes.")
                return False
            self._cancel_request.clear()
            self._capturing_context = True
            services = self.services
            bar_generation = self.bar_status.begin()
        finally:
            self._lock.release()
        accepted = False
        try:
            self.corrections.cancel()
            # UIA may require GUI message processing. Reserve the start slot,
            # but let Settings/cancel/shutdown return while context is read.
            try:
                target = services.context.capture()
            except Exception:
                logger.warning("Foreground context unavailable; recording did not start")
                self.emit("notification_requested", "Could not read the target field. Try dictation again.")
                return False
            with self._lock:
                if (self._cancel_request.is_set() or self._closing or self._pending_config is not None
                        or not self._request_current(request_current)):
                    return False
                context = select_context(services.config, services.profiles, target.app_title,
                    app_group=target.app_group, app_exe=target.app_exe, app_site=target.app_site)
                self.session.dispatch(Input.START)
                generation = self.session.session_id
                self.bar_status.bind(generation, bar_generation)
                self._target = target
                self._context = context
                self._insert_text = insert_text
                self._record_request_current = request_current
                self._submit(self._arm, generation)
                accepted = True
                return generation if _return_generation else True
        finally:
            if not accepted:
                self.bar_status.publish(bar_generation, BarPhase.IDLE)
            with self._lock:
                self._capturing_context = False
                if self._pending_config is not None and not self.busy and not self._closing:
                    # Apply on the serial worker, never from inside the native
                    # hook dispatcher that Settings may need to retire.
                    self._submit(lambda: None)

    def _arm(self, generation):
        preparing_asr = False
        try:
            with self._lock:
                if not self._capture_request_current(generation):
                    self._reject_arming(generation)
                    return
            self._warm_cleanup(replace(self._context, app_group=self._target.app_group))
            set_context = getattr(self.services.asr, "set_context", None)
            if set_context is not None:
                set_context(self._target)
            prepare = getattr(self.services.asr, "prepare", None)
            if prepare is not None:
                preparing_asr = True
                prepare()
                preparing_asr = False
            with self._lock:
                if not self._capture_request_current(generation):
                    self._reject_arming(generation)
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
                current = self._capture_request_current(generation)
            if not current:
                self._close_background(discard=True)
                self._close_preview(discard=True)
                self._reject_arming(generation)
                return
            self.services.recorder.start()
            self.corrections.prepare(generation, self.services.context, self._target,
                enabled=self._insert_text and self.services.config["dictation"].get("learn_corrections", False),
                lease_seconds=min(3660, max(1, self.services.config["recording"]["max_seconds"] + 60)))
            with self._lock:
                event = self.session.dispatch(Input.ARMED, session_id=generation) if self._capture_request_current(generation) else None
                if event is not None:
                    self.bar_status.session(generation, BarPhase.LISTENING)
                    self.emit("recording_started")
                    limits = self.services.config["recording"]
                    maximum = limits["max_seconds"]
                    warning = limits["warning_seconds"]
                    if 0 < warning < maximum:
                        self._schedule(warning, lambda: self._warn(generation, maximum))
                    self._schedule(maximum, lambda: self._cap(generation))
                    return
            self.corrections.cancel(generation)
            self.services.recorder.stop()  # Released/cancelled while the device opened.
            self._close_background(discard=True)
            self._close_preview(discard=True)
            self._reject_arming(generation)
        except Exception:
            self.corrections.cancel(generation)
            logger.exception("Could not arm microphone")
            self.hotkeys._controller.discard_active_recording()
            self._close_background(discard=True)
            self._close_preview(discard=True)
            with self._lock:
                self.session.dispatch(Input.FAIL, session_id=generation)
            self.bar_status.session(generation, BarPhase.ERROR,
                reason="model_unavailable" if preparing_asr else "microphone_unavailable")
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

    def stop_recording(self, *, released_at=None, session_id=None):
        if self._closing:
            return
        if not self._lock.acquire(blocking=False):
            # Settings may be retiring this native dispatcher while holding the
            # session mutex. Finish on the serial owner without waiting here.
            expected = self.session.session_id if session_id is None else session_id
            try:
                self.executor.submit(lambda: self._stop_recording(released_at=released_at, session_id=expected))
            except RuntimeError:
                if not self._closing:
                    raise
            return
        try:
            self._stop_recording(released_at=released_at, session_id=session_id)
        finally:
            self._lock.release()

    def _stop_recording(self, *, released_at=None, session_id=None):
        with self._lock:
            if session_id is not None and (session_id != self.session.session_id or not self.session.active):
                return  # Includes a newer context capture before its START transition.
            if self._capturing_context and not self.session.active:
                self._cancel_request.set()
                self.bar_status.cancel()
                return
            ended = released_at if type(released_at) in (int, float) and math.isfinite(released_at) else None
            event = self.session.dispatch(Input.RELEASE, recording_stopped_at=ended)
            if event is None:
                return
            if event.state == State.CANCELLED:
                self.bar_status.cancel()
            else:
                self.bar_status.session(event.session_id, BarPhase.PROCESSING)
            if event.previous != State.ARMING and event.state != State.CANCELLED:
                released = (min(event.timestamp, released_at) if type(released_at) in (int, float)
                            and math.isfinite(released_at) else event.timestamp)
                self._context = replace(self._context,
                    cleanup_deadline=released + RELEASE_TO_TEXT_BUDGET_SECONDS)
            self._cancel_timers()
            self.emit("recording_stopped", float(event.recording_seconds or 0))
            if event.previous == State.ARMING:
                return  # _arm closes the device once its start call returns.
            self._submit(self._finalize, event.session_id, event.recording_seconds,
                         event.state == State.CANCELLED)

    def cancel(self):
        # Observed by delivery even while native clipboard rendering is in progress.
        self._cancel_request.set()
        self.bar_status.cancel()
        self.corrections.cancel()
        if not self.session.active:
            return  # Also aborts a pending context capture before START dispatch.
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
                    or self._closing or self._cancel_request.is_set()):
                return InsertionResult("not_inserted", "none", "cancelled")
            self.session.dispatch(Input.CLEANED, session_id=generation)
        # Clipboard rendering can call into the GUI; never hold the session lock across OS delivery.
        try:
            result = action()
        except Exception:
            with self._lock:
                self.session.dispatch(Input.NOT_INSERTED, session_id=generation, reason="insertion_error")
            raise
        with self._lock:
            outcome = Input.INSERTED if result.status == "inserted" else Input.NOT_INSERTED
            self.session.dispatch(outcome, session_id=generation, reason=result.reason)
            return result

    def _finalize(self, generation, duration, discard):
        completed_text = ""
        failed = False
        bar_outcome = False
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
                enter_guard=lambda: not self._cancel_request.is_set() and not self._closing,
                field_guard=self._field_guard(self._target),
                before_insert=self.corrections.hook(generation),
            )
            reason = result.insertion.reason
            if reason == "history_only":
                reason = "review_only" if choice.review_only else "saved_only"
            self.bar_status.session(generation,
                BarPhase.INSERTED if result.insertion.status == "inserted" else BarPhase.NOT_INSERTED,
                reason=reason, saved=result.history_id is not None)
            bar_outcome = True
            self.corrections.complete(generation, result.cleaned_text, result.insertion, choice.language)
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
            if not bar_outcome:
                self.bar_status.session(generation, BarPhase.ERROR, reason="processing_failed")
            self.emit("error", "Could not complete dictation; saved words remain in history.")
        finally:
            self.corrections.finish(generation)
            self._close_background(discard=True)
            self._close_preview(discard=True)
            if not failed:
                if not bar_outcome:
                    self.bar_status.session(generation, BarPhase.IDLE)
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
                raw, target=target, context=DictationContext(row.mode, row.profile, row.app_name,
                    tone=row.style, intensity=row.intensity),
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

                cleanup = getattr(self.services.cleaner, "benchmark", None)
                def benchmark(asr):
                    return run_benchmark(asr, cleanup_benchmark=cleanup)
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
        generation = self.start_recording(insert_text=False, _return_generation=True)
        if generation is not False:
            self._schedule(3.0, lambda: self.stop_recording(session_id=generation))

    def paste_last(self):
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self.busy or self._closing:
                self.emit("notification_requested", "Finish the current work before pasting the last transcript.")
                return False
            self._cancel_request.clear()
            self._capturing_context = True
            context = self.services.context
        finally:
            self._lock.release()
        try:
            capture = getattr(context, "capture_for_insertion", context.capture)
            target = capture()  # Freeze the requested field before the serial History read.
            with self._lock:
                if self._closing or self._cancel_request.is_set() or self._pending_config is not None:
                    return False
                if insertion_block(target):
                    self.emit("notification_requested", "Cannot paste into this field; use Copy in History.")
                    return False
                self._submit(self._paste_last, target)
                return True
        except Exception:
            logger.warning("Could not prepare last-transcript insertion")
            self.emit("notification_requested", "Could not paste the last transcript; use Copy in History.")
            return False
        finally:
            with self._lock:
                self._capturing_context = False
                if self._pending_config is not None and not self.busy and not self._closing:
                    self._submit(lambda: None)  # Settings must not retire its own dispatcher.

    def _paste_last(self, target):
        if self._closing or self._cancel_request.is_set():
            return
        try:
            text = self.services.history.last_transcript()
            if self._closing or self._cancel_request.is_set():
                return
            if text:
                self._reinsert_text(text, target=target)
            else:
                self.emit("notification_requested", "No saved transcript is available yet.")
        except Exception:
            logger.warning("Last saved transcript unavailable")
            self.emit("notification_requested", "Could not read the last transcript; open History to copy it.")

    def reinsert_text(self, text):
        with self._lock:
            if self.busy or self._closing or not isinstance(text, str) or not text:
                return False
            self._cancel_request.clear()
            self._submit(self._reinsert_text, text)
            return True

    def _reinsert_text(self, text, *, target=None):
        generation = self.session.session_id
        try:
            if self._closing or self._cancel_request.is_set():
                return
            target = target if target is not None else self.services.context.capture()
            if insertion_block(target):
                self.emit("notification_requested", "Cannot reinsert into this field; use Copy in History.")
                return
            self.corrections.prepare(generation, self.services.context, target,
                enabled=self.services.config["dictation"].get("learn_corrections", False), lease_seconds=60)
            options = {"start_focus": target.focus, "app_title": target.app_title,
                       "enter_guard": lambda: not self._cancel_request.is_set() and not self._closing}
            if (guard := self._field_guard(target)) is not None:
                options["field_guard"] = guard
            if (hook := self.corrections.hook(generation)) is not None:
                options["before_insert"] = hook
            result = self.services.inserter.insert_text(text, **options)
            self.corrections.complete(generation, text, result, self.services.config["stt"].get("language", "auto"))
            if result.status != "inserted":
                self.emit("notification_requested", "Could not reinsert text; use Copy in History.")
        except Exception:
            logger.warning("History reinsertion unavailable")
            self.emit("notification_requested", "Could not reinsert text; use Copy in History.")
        finally:
            self.corrections.finish(generation)

    def configure(self, config):
        self.corrections.cancel()
        with self._lock:
            if self._closing:
                return
            if self.busy:
                self._pending_config = config
                self.emit("notification_requested", "Settings will apply after the current dictation.")
                return
            pending = self.services.processor.pending_results
            previous = self.services.cleaner
            context = self.services.context
            clipboard = getattr(self.services.inserter, "clipboard", None)
            self.services = self.services_factory(
                config, level_callback=lambda level: self.emit("audio_level_changed", level),
                notify=lambda message: self.emit("notification_requested", message))
            self.services.processor.pending_results.extend(pending)
            replacement = self.services.context
            if isinstance(context, ForegroundContextProvider) and isinstance(replacement, ForegroundContextProvider):
                if replacement is not context:
                    self._close_context(replacement)
                context.set_profiles(self.services.profiles)
                self.services.context = context
                if hasattr(self.services.inserter, "focus_provider"):
                    self.services.inserter.focus_provider = context.focus
            elif context is not replacement:
                self._close_context(context)
            self._prepare_context()
            if clipboard is not None and hasattr(self.services.inserter, "clipboard"):
                self.services.inserter.clipboard = clipboard  # Retain recovery and the History window's shared port.
            if previous is not self.services.cleaner:
                self._close_cleanup(previous)
            self._warm_cleanup()
            self.hotkeys.configure(config)

    def shutdown(self):
        self._closing = True
        self.cancel()
        self._close_context(self.services.context)
        self.hotkeys.stop()
        self._cancel_timers()
        self._close_cleanup(self.services.cleaner)
        close_inserter = getattr(self.services.inserter, "close", None)
        if close_inserter is not None:
            try:
                if not close_inserter():
                    logger.warning("Clipboard transaction or recovery is still active during shutdown")
            except OSError:
                logger.warning("Clipboard recovery could not finish during shutdown")
        # An in-flight ASR may finish and persist its words, but can no longer paste.
        self.executor.shutdown(wait=False, cancel_futures=False)
