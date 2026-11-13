"""Owned, in-memory dictation practice with independent capture and hook lifetimes."""

import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
import threading
import time
from types import SimpleNamespace

from saydraft.hotkeys import HotkeyConfig, HotkeyController
from saydraft.hotkeys.capture import OwnedWindowGuard
from saydraft.hotkeys.focused import FocusedMatcher, TARGET_LOST
from saydraft.hotkeys.llhook import LowLevelHooks
from saydraft.hotkeys.recording import validate_hotkeys
from saydraft.insert.inserter import InsertionResult
from .interfaces import TargetContext
from .preferences import select_context
from .processing import IdentityFormatter, TranscriptProcessor

MAX_SECONDS = 60
MAX_TEXT = 4096


def practice_recorder(config, on_level):
    from functools import partial
    from saydraft.audio.devices import InputSelection, selected_input_stream
    from saydraft.audio.recorder import AudioRecorder
    selected = InputSelection.from_config(config)
    return AudioRecorder(max_seconds=MAX_SECONDS, level_callback=on_level,
        device=selected.name or None, stream_factory=partial(selected_input_stream, selected))


@dataclass(frozen=True)
class PracticeResult:
    generation: int
    capture: int
    group: str
    raw: str
    text: str
    decision: str
    enter_requested: bool = False


@dataclass
class _Recording:
    generation: int
    cancelled: threading.Event = field(default_factory=threading.Event)
    recorder: object = None
    timer: object = None
    stopping: bool = False
    started: bool = False
    arm_done: threading.Event = field(default_factory=threading.Event)


@dataclass
class _Practice:
    generation: int
    window: int
    valid: object
    config: dict
    group: str
    closing: threading.Event = field(default_factory=threading.Event)
    foreground: object = None
    owner: object = None
    asr: object = None
    record: object = None
    hooks_ready: bool = False
    hooks_done: bool = False
    warming: bool = True
    announced: bool = False
    external_stop: bool = False


class PracticeController:
    def __init__(self, *, schedule, emit, asr_factory, cleaner, snippets=lambda: {}, finished=lambda: None,
                 recorder_factory=practice_recorder, hooks_factory=LowLevelHooks,
                 guard_factory=OwnedWindowGuard, control=None, timer_factory=threading.Timer, clock=time.monotonic):
        self.schedule, self.emit_callback = schedule, emit
        self.asr_factory, self.cleaner, self.snippets = asr_factory, cleaner, snippets
        self.finished, self.recorder_factory = finished, recorder_factory
        self.hooks_factory, self.guard_factory = hooks_factory, guard_factory
        self.control = control or ThreadPoolExecutor(max_workers=1, thread_name_prefix='Saydraft-practice-hooks')
        self.timer_factory, self.clock = timer_factory, clock
        self._lock = threading.RLock()
        self._lease = None
        self.generation = self.capture_generation = 0
        self.closed = False

    def emit(self, *args):
        try:
            self.emit_callback(*args)
        except Exception:
            pass

    @property
    def active(self):
        with self._lock:
            return self._lease is not None

    def open(self, config, window, valid, group):
        if (type(window) is not int or window <= 0 or not callable(valid) or group not in ('messages', 'email')
                or validate_hotkeys(config.get('hotkeys', {}))):
            return 0
        with self._lock:
            if self.closed or self._lease is not None:
                return 0
            self.generation += 1
            lease = self._lease = _Practice(self.generation, window, valid, copy.deepcopy(config), group)
        self.emit('practice_status', lease.generation, 0, 'preparing')
        try:
            self.control.submit(self._open_hooks, lease)
            self.schedule(self._warm, lease)
        except Exception:
            lease.warming = False
            self.emit('practice_status', lease.generation, 0, 'failed')
            self.close_session(lease.generation)
        return lease.generation

    def _current(self, lease):
        return self._lease is lease and not self.closed and not lease.closing.is_set()

    def _allowed(self, lease):
        try:
            return bool(self._current(lease) and lease.valid() and lease.foreground is not None and lease.foreground())
        except Exception:
            return False

    def _open_hooks(self, lease):
        try:
            if not self._current(lease) or not lease.valid():
                self.close_session(lease.generation)
                return
            lease.foreground = self.guard_factory(lease.window)

            def native(bindings, **kwargs):
                bindings = [replace(item, suppress=True) if item.name == 'cancel' else item for item in bindings]
                original = kwargs['on_action']
                kwargs['on_action'] = lambda event, when: (
                    self.close_session(lease.generation) if event.name == TARGET_LOST else original(event, when))
                return self.hooks_factory(bindings, matcher=FocusedMatcher(bindings, valid=lambda: self._allowed(lease)), **kwargs)

            config = replace(HotkeyConfig.from_app_config(lease.config), save_hotkey='', paste_last_hotkey='')
            lease.owner = HotkeyController(config, native_factory=native, timer_factory=self.timer_factory,
                clock=self.clock, on_record_start=lambda: self.start_recording(lease.generation),
                on_record_start_guarded=lambda valid: self.start_recording(lease.generation, valid=valid),
                on_record_stop=lambda value: self.stop_recording(lease.generation, value.session_id),
                on_record_cancel=lambda: self.stop_recording(lease.generation, cancel=True),
                on_backend_failure=lambda reason: self._failed(lease))
            if not self._current(lease):
                return
            lease.owner.start()
            lease.hooks_ready = True
            self._ready(lease)
        except Exception:
            self._failed(lease)
        finally:
            if lease.closing.is_set():
                self._retire(lease)

    def _warm(self, lease):
        try:
            if not self._current(lease) or not lease.valid():
                self.close_session(lease.generation)
                return
            lease.asr = self.asr_factory(lease.config)
            contextual = getattr(lease.asr, 'set_context', None)
            if contextual is not None:
                contextual(TargetContext('practice', 'Saydraft practice', app_group=lease.group))
            prepare = getattr(lease.asr, 'prepare', None)
            if prepare is not None:
                prepare()
        except Exception:
            self.emit('practice_status', lease.generation, 0, 'model_unavailable')
            self.close_session(lease.generation)
        finally:
            with self._lock:
                lease.warming = False
            self._ready(lease)
            self._complete(lease)

    def _ready(self, lease):
        with self._lock:
            if self._current(lease) and not lease.warming and lease.hooks_ready and not lease.announced:
                if not self._allowed(lease):
                    self.close_session(lease.generation)
                    return
                lease.announced = True
                self.emit('practice_status', lease.generation, 0, 'ready')

    def start_recording(self, generation, *, valid=lambda: True):
        with self._lock:
            lease = self._lease
            if (lease is None or lease.generation != generation or not lease.announced
                    or lease.record is not None or not self._allowed(lease) or not valid()):
                return False
            self.capture_generation += 1
            record = lease.record = _Recording(self.capture_generation)
        self.emit('practice_status', generation, record.generation, 'arming')
        try:
            self.schedule(self._arm, lease, record)
        except Exception:
            record.cancelled.set()
            record.arm_done.set()
            with self._lock:
                if lease.record is record:
                    lease.record = None
            self.emit('practice_status', generation, record.generation, 'failed')
            self._complete(lease)
            return False
        return record.generation

    def _record_current(self, lease, record):
        return self._allowed(lease) and lease.record is record and not record.cancelled.is_set()

    def _arm(self, lease, record):
        try:
            if not self._record_current(lease, record) or record.stopping:
                self.stop_recording(lease.generation, record.generation, cancel=True)
                return
            record.recorder = self.recorder_factory(lease.config,
                lambda level: self._level(lease, record, level))
            record.recorder.start()
            record.started = True
            if not self._record_current(lease, record) or record.stopping:
                self.stop_recording(lease.generation, record.generation, cancel=True)
                return
            record.timer = self.timer_factory(MAX_SECONDS,
                lambda: self.stop_recording(lease.generation, record.generation))
            if hasattr(record.timer, 'daemon'):
                record.timer.daemon = True
            record.timer.start()
            self.emit('practice_status', lease.generation, record.generation, 'recording')
        except Exception:
            self.emit('practice_status', lease.generation, record.generation, 'microphone_unavailable')
            self.stop_recording(lease.generation, record.generation, cancel=True)
        finally:
            record.arm_done.set()

    def _level(self, lease, record, level):
        if self._record_current(lease, record) and not record.stopping:
            self.emit('practice_level', lease.generation, record.generation, float(level))

    def stop_recording(self, generation, capture=None, *, cancel=False):
        with self._lock:
            lease = self._lease
            if lease is None or lease.generation != generation or lease.record is None:
                return False
            record = lease.record
            if capture is not None and capture != record.generation:
                return False
            if cancel:
                record.cancelled.set()
            if record.stopping:
                return True
            record.stopping = True
            if record.timer is not None:
                record.timer.cancel()
        self.emit('practice_status', generation, record.generation, 'stopping' if cancel else 'processing')
        try:
            if lease.owner is not None:
                self.control.submit(lease.owner.discard_active_recording)
            self.schedule(self._finish_record, lease, record)
        except Exception:
            self._failed(lease)  # Retain the capture until an owned retirement can observe it.
            threading.Thread(target=self._finish_record, args=(lease, record), daemon=True,
                name='Saydraft-practice-retire-audio').start()
        return True

    def _finish_record(self, lease, record):
        if not record.arm_done.is_set():
            threading.Thread(target=self._finish_after_arm, args=(lease, record), daemon=True,
                name='Saydraft-practice-retire-arming').start()
            return  # Cancellation may queue before arming; never wait ahead of it on the serial queue.
        try:
            audio = record.recorder.stop() if record.recorder is not None else None
        except Exception:
            record.cancelled.set()
            self.emit('practice_status', lease.generation, record.generation, 'cleanup_failed')
            self.close_session(lease.generation)
            return  # Unknown device retirement retains both owner and reservation.
        try:
            if audio is None or not record.started or not self._record_current(lease, record):
                return
            duration = len(audio) / 16000
            if duration < .5:
                self.emit('practice_status', lease.generation, record.generation, 'too_short')
                return
            self.emit('practice_status', lease.generation, record.generation, 'processing')
            raw = lease.asr.transcribe(audio)
            if not self._record_current(lease, record):
                return
            if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_TEXT:
                self.emit('practice_status', lease.generation, record.generation, 'no_text')
                return
            context = select_context(lease.config, [], 'Saydraft practice', app_group=lease.group)
            language = getattr(lease.asr, 'last_language', None) or lease.config['stt'].get('language', 'auto')
            context = replace(context, cleanup_deadline=self.clock() + 2,
                language=language)
            cleaner = self.cleaner()
            warm = getattr(cleaner, 'warm_for_context', None)
            if warm is not None:
                warm(context)
            processor = TranscriptProcessor(cleaner=cleaner, formatter=IdentityFormatter(),
                history=SimpleNamespace(append=lambda entry: 1),
                inserter=SimpleNamespace(insert_text=lambda text, **kw:
                    InsertionResult('inserted', 'practice', enter_sent=kw.get('send_enter', False))),
                voice_enter_enabled=lease.config['dictation'].get('voice_enter_enabled', False),
                snippets=dict(self.snippets()), reporter=SimpleNamespace(report=lambda *a: None))
            result = processor.process(raw, target=TargetContext('practice', 'Saydraft practice', app_group=lease.group),
                context=context, model=getattr(lease.asr, 'model_id', 'practice'), duration_seconds=duration,
                language=language, cancelled=lambda: not self._record_current(lease, record))
            if len(result.cleaned_text) > MAX_TEXT * 4:
                self.emit('practice_status', lease.generation, record.generation, 'result_too_long')
                return
            if self._record_current(lease, record):
                self.emit('practice_result', PracticeResult(lease.generation, record.generation, lease.group,
                    raw, result.cleaned_text, getattr(cleaner, 'last_llm_decision', 'rules'), result.insertion.enter_sent))
        except Exception:
            if self._current(lease) and not record.cancelled.is_set():
                self.emit('practice_status', lease.generation, record.generation, 'failed')
        finally:
            if record.timer is not None:
                record.timer.cancel()
            with self._lock:
                if lease.record is record:
                    lease.record = None
            self.emit('practice_status', lease.generation, record.generation, 'idle')
            self._complete(lease)

    def _finish_after_arm(self, lease, record):
        record.arm_done.wait()
        self._finish_record(lease, record)

    def _failed(self, lease):
        self.emit('practice_status', lease.generation, 0, 'failed')
        self.close_session(lease.generation)

    def close_session(self, generation=None, *, external=False):
        with self._lock:
            lease = self._lease
            if lease is None or generation not in (None, lease.generation):
                return False
            already_closing = lease.closing.is_set()
            if external:
                lease.external_stop = True
            lease.closing.set()
        if external:
            self.emit('practice_status', lease.generation, 0, 'closing_external')
        if already_closing:
            return True
        self.stop_recording(lease.generation, cancel=True)
        self.emit('practice_status', lease.generation, 0, 'closing_external' if lease.external_stop else 'closing')
        try:
            self.control.submit(self._retire, lease)
        except Exception:
            threading.Thread(target=self._retire, args=(lease,), daemon=True,
                name='Saydraft-practice-retire-hooks').start()
        return True

    def _retire(self, lease):
        if lease.hooks_done:
            return
        try:
            owner = lease.owner
            if owner is not None and not owner.stop():
                thread = owner.completion_thread
                if thread is None:
                    raise RuntimeError('Native retirement is unobservable')
                thread.join()  # Dedicated control worker only.
            lease.hooks_done = True
        except Exception:
            self.emit('practice_status', lease.generation, 0, 'cleanup_failed')
            return
        self._complete(lease)

    def _complete(self, lease):
        with self._lock:
            if (self._lease is not lease or not lease.closing.is_set() or not lease.hooks_done
                    or lease.warming or lease.record is not None):
                return
            lease.asr = lease.owner = None
            self._lease = None
        if not self.closed:
            self.emit('practice_status', lease.generation, 0, 'stopped')
        self.finished()

    def close(self):
        self.closed = True
        self.close_session()
        self.control.shutdown(wait=False, cancel_futures=False)
