from types import SimpleNamespace
from dataclasses import replace
import threading

import pytest

from saydraft.hotkeys import HotkeyController
from saydraft.core.bar_actions import BarActions
from saydraft.core.bar_status import BarPhase
from saydraft.core.session import SessionState
from tests.test_native_recording import Owner
from tests.test_session_worker import Executor, make_worker


class QueuedOwner(Owner):
    """Owned callback queue only: never install native hooks or send input."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = []

    def post_action(self, callback):
        if not self.running:
            return False
        self.actions.append(callback)
        return True

    def drain(self):
        while self.actions:
            self.actions.pop(0)()


@pytest.fixture
def paused_bar():
    worker, clock, _, events, signals, _ = make_worker()
    owners, updates, changes = [], [], []

    def factory(*args, **kwargs):
        owner = QueuedOwner(*args, **kwargs)
        owners.append(owner)
        return owner

    worker.hotkeys.keyboard = None
    worker.hotkeys.native_factory = factory
    worker.hotkeys._controller = worker.hotkeys._make_controller()
    worker.hotkeys._controller.clock = lambda: clock.now
    worker.bar_status.callback = updates.append
    worker.services.config["app"]["auto_start_listening"] = False
    worker.services_factory = lambda config, **kwargs: replace(worker.services, config=config)
    executor = Executor(queued=True)
    actions = BarActions(worker, changed=lambda: changes.append(worker.hotkeys.enabled), executor=executor)
    try:
        yield SimpleNamespace(worker=worker, clock=clock, owners=owners, updates=updates, changes=changes,
            signals=signals, events=events, executor=executor, actions=actions)
    finally:
        actions.close()
        executor.drain()


def test_paused_click_prepares_immediately_then_resumes_listening_and_records(paused_bar):
    bar = paused_bar
    assert bar.actions.request_start()
    assert bar.actions.pending and not bar.actions.request_start()
    assert bar.updates[-1].phase == BarPhase.PREPARING
    assert not bar.owners and not bar.worker.hotkeys.enabled
    bar.executor.drain()
    assert bar.worker.hotkeys.enabled and bar.changes == [True]
    assert bar.worker.services.recorder.started == 0
    bar.owners[0].drain()
    assert not bar.actions.pending and bar.worker.hotkeys._controller.is_locked
    assert bar.worker.services.recorder.started == 1
    assert bar.updates[-1].phase == BarPhase.LISTENING
    assert not bar.worker.services.config["app"]["auto_start_listening"]
    bar.clock.now = 1
    assert bar.worker.hotkeys._controller.request_hands_free(stop=True)
    bar.owners[0].drain()
    assert [event[0] for event in bar.events] == ["history", "insert"]
    assert bar.worker.hotkeys.enabled and not bar.worker.hotkeys._controller.is_recording
    assert bar.updates[-1].phase == BarPhase.INSERTED


@pytest.mark.parametrize("boundary", ["before_start", "before_native_action"])
@pytest.mark.parametrize("change", ["cancel_pending", "stop_listening", "configure", "close"])
def test_control_changes_revoke_a_pending_click_at_both_queues(paused_bar, boundary, change):
    bar = paused_bar
    assert bar.actions.request_start()
    if boundary == "before_native_action":
        bar.executor.drain()
    if change == "configure":
        config = dict(bar.worker.services.config)
        config["hotkeys"] = dict(config["hotkeys"], speech="f8")
        bar.actions.configure(config)
    else:
        getattr(bar.actions, change)()
    assert not bar.actions.pending
    # Even a callback already removed from the native queue cannot cross Stop.
    for owner in bar.owners:
        owner.drain()
    bar.executor.drain()
    assert not bar.worker.hotkeys.enabled
    assert bar.worker.services.recorder.started == 0
    assert not bar.events and ("recording_started",) not in bar.signals
    assert bar.updates[-1].phase == BarPhase.IDLE
    if change == "configure":
        assert bar.worker.hotkeys.config["hotkeys"]["speech"] == "f8"


def test_an_explicit_resume_after_cancel_accepts_only_the_new_click(paused_bar):
    bar = paused_bar
    assert bar.actions.request_start()
    bar.executor.drain()
    old_owner = bar.owners[0]
    bar.actions.cancel_pending()
    assert bar.actions.request_start()
    old_owner.drain()
    bar.executor.drain()
    assert len(bar.owners) == 2
    bar.owners[1].drain()
    assert bar.worker.services.recorder.started == 1
    assert bar.worker.hotkeys._controller.is_locked and bar.updates[-1].phase == BarPhase.LISTENING


@pytest.mark.parametrize("failure", ["start", "queue"])
def test_listener_startup_failures_restore_paused_state_and_explain_recovery(paused_bar, failure):
    bar = paused_bar
    if failure == "start":
        def unavailable():
            raise OSError("fixture listener unavailable")
        bar.worker.hotkeys._controller.start = unavailable
    else:
        bar.worker.hotkeys._controller.request_hands_free = lambda **kwargs: False
    assert bar.actions.request_start()
    bar.executor.drain()
    assert not bar.actions.pending and not bar.worker.hotkeys.enabled
    assert bar.worker.services.recorder.started == 0
    assert bar.updates[-1].phase == BarPhase.IDLE
    assert any(name == "notification_requested" and "Settings" in message for name, *rest in bar.signals
               for message in rest if isinstance(message, str))


def test_busy_and_closed_workers_do_not_publish_spurious_preparing_events(paused_bar):
    bar = paused_bar
    bar.worker._capturing_context = True
    assert not bar.actions.request_start()
    bar.worker._capturing_context = False
    bar.actions.close()
    assert not bar.actions.request_start()
    assert not bar.updates and not bar.owners


def test_paused_native_startup_never_blocks_the_gui_and_stop_wins(paused_bar):
    bar = paused_bar
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
    original_factory = bar.worker.hotkeys.native_factory

    def factory(*args, **kwargs):
        owner = original_factory(*args, **kwargs)
        start = owner.start

        def blocked_start():
            entered.set()
            assert release.wait(3)
            start()
        owner.start = blocked_start
        return owner

    bar.worker.hotkeys.native_factory = factory
    bar.worker.hotkeys._controller = bar.worker.hotkeys._make_controller()
    actions = BarActions(bar.worker, changed=lambda: stopped.set() if not bar.worker.hotkeys.enabled else None)
    try:
        assert actions.request_start()
        assert entered.wait(3)
        actions.stop_listening()  # Returns while the native owner's startup is blocked.
        assert not actions.pending and not stopped.is_set()
        release.set()
        assert stopped.wait(3)
        assert not bar.worker.hotkeys.enabled and bar.worker.services.recorder.started == 0
    finally:
        release.set()
        actions.close()
        actions.executor.shutdown(wait=True)


def test_stop_during_target_capture_prevents_the_queued_click_opening_a_microphone(paused_bar):
    bar = paused_bar
    entered, release = threading.Event(), threading.Event()
    target = bar.worker.services.context.capture()

    def capture():
        entered.set()
        assert release.wait(3)
        return target

    bar.worker.services.context.capture = capture
    assert bar.actions.request_start()
    bar.executor.drain()
    thread = threading.Thread(target=bar.owners[0].drain)
    thread.start()
    try:
        assert entered.wait(3)
        bar.actions.stop_listening()
        bar.executor.drain()
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and not bar.worker.busy
    assert bar.worker.services.recorder.started == 0
    assert not bar.worker.hotkeys.enabled and not bar.actions.pending
    assert bar.updates[-1].phase == BarPhase.IDLE


@pytest.mark.parametrize("boundary", ["before_context", "during_context", "before_prepare", "during_prepare", "during_device_open"])
def test_recording_admission_guard_is_rechecked_at_each_startup_boundary(boundary):
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    allowed = [True]

    def expire():
        allowed[0] = False

    if boundary == "before_context":
        expire()
    elif boundary == "during_context":
        capture = worker.services.context.capture
        worker.services.context.capture = lambda: (expire(), capture())[1]
    elif boundary == "during_prepare":
        worker.services.asr.prepare = expire
    elif boundary == "during_device_open":
        start = worker.services.recorder.start
        worker.services.recorder.start = lambda: (start(), expire())[0]
    try:
        assert worker.start_recording(request_current=lambda: allowed[0]) == (boundary not in ("before_context", "during_context"))
        if boundary == "before_prepare":
            expire()
        executor.drain()
        assert not worker.busy and not events and ("recording_started",) not in signals
        assert worker.services.recorder.started == int(boundary == "during_device_open")
        assert worker.services.recorder.stopped == int(boundary == "during_device_open")
        assert worker.session.state in (SessionState.IDLE, SessionState.CANCELLED)
    finally:
        worker.shutdown()


def test_app_resumes_from_paused_click_and_reports_background_listening_changes(paused_bar, monkeypatch):
    from saydraft.app import WorkerController, create_worker_signals
    from tests.test_qt_app_shell import fake_qt_modules

    bar = paused_bar
    monkeypatch.setattr("saydraft.core.bar_actions.ThreadPoolExecutor", lambda **kwargs: bar.executor)
    signals = create_worker_signals(fake_qt_modules().QtCore)
    controller = WorkerController(signals)
    controller.core = bar.worker
    assert controller.request_bar_action() and controller.is_hands_free()
    assert not controller.request_bar_action()
    bar.executor.drain()
    assert signals.listening_changed.emitted == [(True,)]
    bar.owners[0].drain()
    assert controller.is_listening() and controller.is_hands_free()
    controller.stop_listening()
    bar.executor.drain()
    assert signals.listening_changed.emitted[-1] == (False,)
    assert not controller.is_listening()
    controller.stop()
    bar.executor.drain()
    assert not controller.request_bar_action() and controller.core is None


def test_native_failure_retires_a_dropped_click_and_allows_an_explicit_retry(paused_bar, monkeypatch):
    from saydraft.app import WorkerController, create_worker_signals
    from tests.test_qt_app_shell import fake_qt_modules

    bar = paused_bar
    monkeypatch.setattr("saydraft.core.bar_actions.ThreadPoolExecutor", lambda **kwargs: bar.executor)
    controller = WorkerController(create_worker_signals(fake_qt_modules().QtCore))
    controller.core = bar.worker
    bar.worker.bar_status.callback = controller._bar_updated
    try:
        assert controller.request_bar_action()
        bar.executor.drain()
        old_owner = bar.owners[0]
        bar.worker.hotkeys._controller._native_failed("message_loop_stopped")
        assert not controller._bar_actions.pending
        bar.executor.drain()
        assert not controller.is_listening()
        assert controller.request_bar_action()
        old_owner.drain()
        bar.executor.drain()
        bar.owners[1].drain()
        assert controller.is_hands_free() and bar.worker.services.recorder.started == 1
    finally:
        controller.stop()
        bar.executor.drain()


def test_background_control_failures_are_visible_and_do_not_leave_tray_listening(paused_bar):
    bar = paused_bar

    def fail():
        raise OSError("fixture start failure")

    bar.worker.hotkeys.start = fail
    bar.actions.start_listening()
    bar.executor.drain()
    assert bar.changes == [False]
    assert any("Could not update listening" in str(event) for event in bar.signals)


def test_request_revocation_blocks_record_save_and_paste_even_before_native_teardown():
    from saydraft.config import default_config
    from saydraft.core.hotkey_service import HotkeyService
    from tests.test_session_worker import Keyboard

    calls = []
    keyboard = Keyboard()
    service = HotkeyService(default_config(), start=lambda: calls.append("record"), stop=lambda: None,
        cancel=lambda: None, save=lambda: calls.append("save"), paste=lambda: calls.append("paste"),
        notify=lambda *_: None, keyboard_module=keyboard)
    try:
        service.start()
        service.revoke_requests()
        service._controller._on_record_press("f9")
        service._controller.on_paste()
        keyboard.added[-1][1]()  # Registered save callback.
        assert not calls and service.enabled
        service._controller.restart_if_dead = lambda: True
        service._controller.is_backend_alive = lambda: False
        assert service.restart_if_dead()
        keyboard.added[-1][1]()  # Recovery keeps the same admission gate.
        assert not calls
    finally:
        service.stop()


def controller_with_owned_queue():
    queued, starts, stops = [], [], []
    ticks = [0.]
    controller = HotkeyController(on_record_start=lambda: starts.append(True) or 1,
        on_record_stop=stops.append, clock=lambda: ticks[0])
    controller._listening = True
    controller._native = SimpleNamespace(defer=lambda callback: queued.append(callback) or True)
    return controller, queued, starts, stops, ticks


def test_clicks_use_the_native_action_queue_and_stop_the_locked_session():
    controller, queued, starts, stops, ticks = controller_with_owned_queue()
    assert controller.request_hands_free()
    assert not starts and not controller.is_recording
    queued.pop(0)()
    assert starts == [True] and controller.is_locked
    assert not controller.request_hands_free()
    ticks[0] = .6
    assert controller.request_hands_free(stop=True)
    assert not stops
    queued.pop(0)()
    assert len(stops) == 1 and stops[0].locked
    assert stops[0].duration_seconds == .6 and not controller.is_recording


@pytest.mark.parametrize("stop", [False, True])
def test_cancelled_clicks_cannot_start_or_stop_a_newer_recording(stop):
    controller, queued, starts, stops, _ = controller_with_owned_queue()
    if stop:
        controller._on_hands_free_press()
    assert controller.request_hands_free(stop=stop)
    callback = queued.pop(0)
    controller.discard_active_recording()
    if stop:
        controller._on_hands_free_press()
    previous = len(starts), len(stops), controller.is_recording
    callback()
    assert (len(starts), len(stops), controller.is_recording) == previous


def test_a_queued_click_does_not_cross_native_backend_replacement():
    controller, queued, starts, _, _ = controller_with_owned_queue()
    assert controller.request_hands_free()
    controller._native = SimpleNamespace()
    queued.pop(0)()
    assert not starts


def test_app_routes_the_error_fix_to_the_correct_settings_page():
    from saydraft.app import SaydraftApp

    app = SaydraftApp()
    opened, indices = [], []
    app._show_settings = lambda: opened.append(True)
    labels = ["General", "Languages", "Models", "Microphone"]
    app.settings_window = SimpleNamespace(tabs=SimpleNamespace(count=lambda: len(labels),
        tabText=lambda index: labels[index], setCurrentIndex=indices.append))
    app._fix_bar_error("microphone")
    app._fix_bar_error("models")
    assert indices == [3, 2] and len(opened) == 2
