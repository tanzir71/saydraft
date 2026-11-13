"""Practice uses private queues, injected audio/ASR, and synthetic hook identifiers."""

import copy
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.config import default_config
from saydraft.core.practice import PracticeController, PracticeResult
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.hotkeys.chords import Binding, Chord
from saydraft.hotkeys.focused import FocusedMatcher, TARGET_LOST
from tests.test_session_worker import Executor, Timer


@pytest.fixture
def subject():
    main, control = Executor(queued=True), Executor(queued=True)
    events, owners, recorders, prepared, retired = [], [], [], [], []
    valid = threading.Event()
    valid.set()
    config = default_config()
    pipeline = DictationPipeline(DictationConfig())
    asr = SimpleNamespace(prepare=lambda: prepared.append(True),
        transcribe=lambda audio: 'um hello world', model_id='public-practice-model')

    class Owner:
        def __init__(self, bindings, **kwargs):
            self.bindings, self.options = bindings, kwargs
            self.status = {'state': 'running', 'reason': None}
            self.closed = False
            self.completion_thread = None
            owners.append(self)

        def start(self):
            pass

        def close(self):
            self.closed = True
            return True

    class Recorder:
        def __init__(self, cfg, on_level):
            self.config, self.on_level = cfg, on_level
            self.started = self.stopped = False
            recorders.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True
            return np.ones(16000, dtype=np.float32)

    practice = PracticeController(schedule=main.submit, emit=lambda *args: events.append(args),
        asr_factory=lambda cfg: asr, cleaner=lambda: pipeline, recorder_factory=Recorder,
        hooks_factory=Owner, guard_factory=lambda window: lambda: window == 123,
        control=control, timer_factory=Timer, finished=lambda: retired.append(True))
    try:
        yield SimpleNamespace(practice=practice, main=main, control=control, events=events,
            owners=owners, recorders=recorders, prepared=prepared, valid=valid, config=config, retired=retired, asr=asr)
    finally:
        practice.close()
        control.drain()
        main.drain()


def ready(s, group='messages'):
    generation = s.practice.open(s.config, 123, s.valid.is_set, group)
    assert generation and s.practice.active and not s.recorders
    s.control.drain()
    assert not s.practice.start_recording(generation)  # Local weights have not prepared yet.
    s.main.drain()
    assert ('practice_status', generation, 0, 'ready') in s.events
    return generation


def test_focused_matcher_revokes_permanently_forwards_new_keys_and_balances_blocked_ups():
    valid = [True]
    matcher = FocusedMatcher([Binding('record', Chord.parse('ctrl+win'))], valid=lambda: valid[0])
    matcher.seed(())
    assert not matcher.feed('left_ctrl', True).suppress
    assert matcher.feed('left_win', True).suppress
    valid[0] = False
    decision = matcher.feed('a', True)
    assert decision.menu_mask and not decision.suppress and decision.transitions[0].name == TARGET_LOST
    assert matcher.feed('left_win', False).suppress
    assert not matcher.feed('left_ctrl', False).suppress
    valid[0] = True
    assert not matcher.feed('left_ctrl', True).suppress
    assert not matcher.feed('left_win', True).suppress and not matcher.blocked


def test_practice_prepares_only_installed_asr_and_records_only_after_explicit_start(subject):
    s = subject
    before = copy.deepcopy(s.config)
    generation = ready(s)
    assert s.prepared == [True] and s.config == before
    capture = s.practice.start_recording(generation)
    assert capture and not s.recorders
    s.main.drain()
    assert s.recorders[0].started
    s.recorders[0].on_level(.1)
    assert ('practice_level', generation, capture, .1) in s.events
    assert not s.practice.start_recording(generation)
    assert s.practice.stop_recording(generation, capture)
    s.main.drain()
    result = next(event[1] for event in s.events if event[0] == 'practice_result')
    assert isinstance(result, PracticeResult) and result.group == 'messages'
    assert result.raw == 'um hello world' and 'um' not in result.text.casefold()
    assert s.recorders[0].stopped and s.practice.active
    assert s.config == before


@pytest.mark.parametrize('phase', ['before_warm', 'before_arm', 'recording'])
def test_cancellation_never_publishes_or_opens_a_late_device(subject, phase):
    s = subject
    generation = s.practice.open(s.config, 123, s.valid.is_set, 'email')
    s.control.drain()
    if phase != 'before_warm':
        s.main.drain()
        s.practice.start_recording(generation)
        if phase == 'recording':
            s.main.drain()
    s.valid.clear()
    assert s.practice.close_session(generation)
    s.control.drain()
    s.main.drain()
    assert not s.practice.active and s.owners[0].closed and s.retired == [True]
    assert not any(event[0] == 'practice_result' for event in s.events)
    assert not s.recorders if phase != 'recording' else s.recorders[0].stopped


def test_expiry_stops_capture_and_stale_stop_cannot_affect_the_next_capture(subject):
    s = subject
    generation = ready(s)
    first = s.practice.start_recording(generation)
    s.main.drain()
    timer = s.practice._lease.record.timer
    assert timer.seconds == 60
    timer.callback()
    s.main.drain()
    second = s.practice.start_recording(generation)
    assert second > first and not s.practice.stop_recording(generation, first)
    s.main.drain()
    assert not s.recorders[1].stopped


def test_failed_device_retirement_keeps_reservation_and_requires_restart(subject):
    s = subject
    generation = ready(s)
    capture = s.practice.start_recording(generation)
    s.main.drain()

    def failed():
        raise RuntimeError('private device information')

    s.recorders[0].stop = failed
    s.practice.stop_recording(generation, capture)
    s.main.drain()
    s.control.drain()
    assert s.practice.active and not s.retired
    assert ('practice_status', generation, capture, 'cleanup_failed') in s.events
    assert 'private' not in str(s.events)
    assert not s.practice.open(s.config, 123, s.valid.is_set, 'email')


def test_model_preparation_failure_opens_no_input_and_retires_the_hook(subject):
    s = subject
    s.asr.prepare = lambda: (_ for _ in ()).throw(OSError('private model path'))
    generation = s.practice.open(s.config, 123, s.valid.is_set, 'messages')
    s.control.drain()
    s.main.drain()
    s.control.drain()
    assert not s.practice.active and not s.recorders and s.owners[0].closed
    assert ('practice_status', generation, 0, 'model_unavailable') in s.events
    assert 'private' not in str(s.events)


def test_practice_bindings_do_not_install_history_or_clipboard_actions_and_own_cancel(subject):
    s = subject
    ready(s)
    bindings = {item.name: item for item in s.owners[0].bindings}
    assert 'save' not in bindings and 'paste_last' not in bindings
    assert bindings['cancel'].suppress


def test_real_worker_admits_practice_before_foreground_capture_and_preserves_live_history():
    from tests.test_session_worker import make_worker
    worker, _, executor, events, _, _ = make_worker(queued=True)
    worker.practice.control.shutdown(wait=False)
    worker.practice.control = Executor(queued=True)
    worker.practice.guard_factory = lambda window: lambda: True
    worker.practice.hooks_factory = lambda *args, **kwargs: SimpleNamespace(
        start=lambda: None, close=lambda: True, status={'state': 'running'}, completion_thread=None)
    try:
        generation = worker.open_practice(worker.services.config, 123, lambda: True, 'email')
        assert generation and worker.busy and not worker.start_recording() and not worker.paste_last()
        worker.practice.control.drain()
        executor.drain()
        assert not worker.services.recorder.started and not events
        worker.close_practice(generation)
        worker.practice.control.drain()
        assert not worker.busy
    finally:
        worker.shutdown()


@pytest.mark.parametrize('blocked', ['model', 'input', 'recognition'])
def test_window_exit_retires_hooks_without_joining_blocked_model_input_or_recognition(blocked):
    from concurrent.futures import ThreadPoolExecutor
    entered, release, hooks_closed, retired = (threading.Event() for _ in range(4))
    valid = threading.Event()
    valid.set()
    events, owners, recorders, recognized = [], [], [], []
    main = ThreadPoolExecutor(max_workers=1)

    def block(stage):
        if blocked == stage:
            entered.set()
            assert release.wait(5)

    class Owner:
        def __init__(self, *args, **kwargs):
            self.status = {'state': 'running'}
            owners.append(self)

        def start(self):
            pass

        def close(self):
            hooks_closed.set()
            return True

    class Recorder:
        def __init__(self, *args):
            self.stopped = False
            recorders.append(self)

        def start(self):
            block('input')

        def stop(self):
            self.stopped = True
            return np.ones(16000, dtype=np.float32)

    def transcribe(audio):
        recognized.append(True)
        block('recognition')
        return 'um public fixture words'

    pipeline = DictationPipeline(DictationConfig())
    practice = PracticeController(schedule=main.submit, emit=lambda *args: events.append(args),
        asr_factory=lambda cfg: SimpleNamespace(prepare=lambda: block('model'), transcribe=transcribe),
        cleaner=lambda: pipeline, recorder_factory=Recorder, hooks_factory=Owner,
        guard_factory=lambda window: lambda: True, finished=retired.set)

    def wait(predicate):
        until = time.monotonic() + 3
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(.002)
        raise AssertionError('Owned practice work did not reach its checkpoint')

    try:
        generation = practice.open(default_config(), 123, valid.is_set, 'messages')
        if blocked != 'model':
            wait(lambda: any(event[-1] == 'ready' for event in events))
            capture = practice.start_recording(generation)
            if blocked == 'recognition':
                wait(lambda: any(event[-1] == 'recording' for event in events))
                practice.stop_recording(generation, capture)
        assert entered.wait(2)
        wait(lambda: bool(owners))
        valid.clear()
        started = time.monotonic()
        assert practice.close_session(generation) and time.monotonic() - started < .2
        assert hooks_closed.wait(2) and practice.active and not retired.is_set()
        release.set()
        assert retired.wait(2) and not practice.active
        assert not any(event[0] == 'practice_result' for event in events)
        assert not recognized if blocked != 'recognition' else recognized == [True]
        assert all(recorder.stopped for recorder in recorders)
    finally:
        release.set()
        practice.close()
        main.shutdown()


def test_unobserved_native_teardown_preserves_practice_reservation(subject):
    s = subject
    generation = ready(s)
    s.owners[0].close = lambda: False
    s.practice.close_session(generation)
    s.control.drain()
    assert s.practice.active and not s.retired
    assert ('practice_status', generation, 0, 'cleanup_failed') in s.events


def test_recognized_language_and_owned_group_reach_the_actual_cleanup_context(subject):
    s = subject
    contexts, asr_targets = [], []
    s.asr.set_context = asr_targets.append
    s.asr.last_language = 'ar'
    s.practice.cleaner = lambda: SimpleNamespace(
        process_transcript=lambda text, context: contexts.append(context) or text)
    generation = ready(s, 'email')
    capture = s.practice.start_recording(generation)
    s.main.drain()
    s.practice.stop_recording(generation, capture)
    s.main.drain()
    assert asr_targets[0].app_group == 'email' and asr_targets[0].focus == 'practice'
    assert contexts[0].language == 'ar' and contexts[0].app_group == 'email'


def test_enabled_voice_enter_is_simulated_without_a_real_enter_or_clipboard(subject):
    s = subject
    s.config['dictation']['voice_enter_enabled'] = True
    s.asr.transcribe = lambda audio: 'hello press enter'
    generation = ready(s)
    capture = s.practice.start_recording(generation)
    s.main.drain()
    s.practice.stop_recording(generation, capture)
    s.main.drain()
    result = next(event[1] for event in s.events if event[0] == 'practice_result')
    assert result.enter_requested and 'press enter' not in result.text.casefold()


def test_failed_input_with_inline_scheduler_does_not_wait_on_its_own_arming_frame(subject):
    s = subject
    generation = ready(s)
    s.practice.schedule = lambda action, *args: action(*args)

    def fail(*args):
        raise OSError('private input failure')

    s.practice.recorder_factory = fail
    started = time.monotonic()
    assert s.practice.start_recording(generation)
    assert time.monotonic() - started < .2
    until = time.monotonic() + 2
    while time.monotonic() < until and s.practice._lease.record is not None:
        time.sleep(.002)
    assert s.practice._lease.record is None
    assert ('practice_status', generation, 1, 'microphone_unavailable') in s.events


def test_native_foreground_revocation_cancels_without_waiting_for_a_gui_focus_event(subject):
    s = subject
    foreground = [True]
    s.practice.guard_factory = lambda window: lambda: foreground[0]
    generation = ready(s)
    s.practice.start_recording(generation)
    s.main.drain()
    foreground[0] = False
    decision = s.owners[0].options['matcher'].feed('a', True)
    assert not decision.suppress
    assert decision.transitions[0].name == TARGET_LOST
    for event in decision.transitions:
        s.owners[0].options['on_action'](event, 0)
    s.control.drain()
    s.main.drain()
    assert not s.practice.active and s.recorders[0].stopped
    assert not any(event[0] == 'practice_result' for event in s.events)


def test_external_stop_upgrades_an_already_retiring_practice_lease(subject):
    s = subject
    generation = ready(s)
    assert s.practice.close_session(generation)
    assert s.practice.close_session(generation, external=True)
    assert ('practice_status', generation, 0, 'closing_external') in s.events
    s.control.drain()
    assert not s.practice.active


@pytest.mark.parametrize('action', ['start', 'stop'])
def test_session_lock_and_practice_lock_cannot_invert_during_cancellation(action):
    from tests.test_session_worker import make_worker
    worker, _, main, events, _, _ = make_worker(queued=True)
    worker.practice.control.shutdown(wait=False)
    worker.practice.control = Executor(queued=True)
    worker.practice.guard_factory = lambda window: lambda: True
    worker.practice.hooks_factory = lambda *args, **kwargs: SimpleNamespace(
        start=lambda: None, close=lambda: True, status={'state': 'running'}, completion_thread=None)
    recorder = SimpleNamespace(start=lambda: None, stop=lambda: np.ones(16000, dtype=np.float32))
    worker.practice.recorder_factory = lambda *args: recorder
    entered, returned = threading.Event(), threading.Event()
    try:
        generation = worker.open_practice(worker.services.config, 123, lambda: True, 'messages')
        worker.practice.control.drain()
        main.drain()
        if action == 'stop':
            worker.start_practice_recording(generation)
            main.drain()

        def observe(name, *args):
            if name == 'practice_status' and args[-1] == ('arming' if action == 'start' else 'processing'):
                entered.set()

        worker.emit_callback = observe

        def request():
            if action == 'start':
                worker.start_practice_recording(generation)
            else:
                worker.stop_practice_recording(generation)
            returned.set()

        with worker._lock:
            thread = threading.Thread(target=request, daemon=True)
            thread.start()
            assert entered.wait(1)
            assert worker.close_practice(generation)  # Must not wait for the blocked scheduler's practice lock.
        assert returned.wait(2)
        thread.join()
        main.drain()
        worker.practice.control.drain()
        until = time.monotonic() + 2
        while worker.busy and time.monotonic() < until:
            time.sleep(.002)
        assert not worker.busy and not events
    finally:
        worker.shutdown()
