"""Owned offscreen setup; fake hooks/devices only, never owner input or clipboard."""

import copy
import json
import threading
import time
from types import SimpleNamespace

import pytest

from saydraft.config import load_config, save_config
from saydraft.ui.onboarding import OnboardingWizard
from tests.test_onboarding_window import qt_modules, write_config


def settle(predicate, timeout=3):
    qt = qt_modules()
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        qt.QtWidgets.QApplication.processEvents()
        if predicate():
            return
        time.sleep(.002)
    raise AssertionError("Owned shortcut UI did not settle")


def show_shortcuts(wizard):
    qt = qt_modules()
    assert qt.QtWidgets.QApplication.platformName() == "offscreen"
    wizard.setStartId(wizard.PAGE_WELCOME)
    wizard.restart()
    wizard.show()
    wizard.activateWindow()
    while wizard.currentId() < wizard.PAGE_HOTKEY:
        wizard.next()
        qt.QtWidgets.QApplication.processEvents()
    assert wizard.currentId() == wizard.PAGE_HOTKEY
    wizard.shortcuts_page.learn_button.setFocus()
    settle(lambda: wizard.shortcuts_page.learn_button.hasFocus() and wizard.isActiveWindow())


@pytest.fixture
def subject(tmp_path, monkeypatch):
    import sounddevice
    from saydraft.hotkeys.llhook import LowLevelHooks

    def forbidden(*args, **kwargs):
        raise AssertionError("Shortcut UI QA must not access native hooks or real microphones")

    monkeypatch.setattr(LowLevelHooks, "start", forbidden)
    for name in ("InputStream", "query_devices", "query_hostapis"):
        monkeypatch.setattr(sounddevice, name, forbidden)
    qt_modules()
    starts, stops, checks = [], [], []

    def start(window, valid):
        starts.append((window, valid))
        return len(starts)

    def check():
        checks.append(threading.get_ident())
        return True

    path = write_config(tmp_path)
    wizard = OnboardingWizard(config_path=path, shortcut_start_callback=start,
        shortcut_cancel_callback=lambda generation: stops.append(generation) or True,
        shortcut_conflict_detector=check)
    try:
        yield SimpleNamespace(wizard=wizard, page=wizard.shortcuts_page, starts=starts,
            stops=stops, checks=checks, path=path)
    finally:
        wizard.close()
        wizard.shortcuts_page.close()
        qt_modules().QtWidgets.QApplication.processEvents()


def test_fresh_preset_is_selected_without_capture_or_process_discovery(subject):
    s = subject
    assert s.page.primary.text() == "ctrl+win"
    assert "Wispr-compatible" in s.page.preset_label.text()
    assert s.page.isComplete() and not s.starts and not s.checks
    assert not s.page.start_learning() and not s.starts  # Hidden windows cannot arm.


def test_captured_chord_is_staged_until_finish_and_persists_only_after_cleanup_status(subject):
    s = subject
    before = s.path.read_bytes()
    show_shortcuts(s.wizard)
    assert s.page.start_learning() and not s.page.isComplete()
    assert s.starts[0][0] == int(s.wizard.winId()) and s.starts[0][1]()
    s.page.accept_status(1, "capturing", "")
    assert not s.page.primary.isEnabled()
    s.page.accept_status(1, "captured", "ctrl+alt+f8")
    assert s.page.primary.text() == "ctrl+alt+f8" and s.page.isComplete()
    assert not s.starts[0][1]() and s.path.read_bytes() == before
    assert s.wizard.finish_onboarding()
    assert load_config(config_path=s.path)["hotkeys"]["speech"] == "ctrl+alt+f8"


@pytest.mark.parametrize("action", ["hide", "reject", "back", "focus", "deactivate", "finish", "close"])
def test_leaving_learning_revokes_permission_and_rejects_a_late_result(subject, action):
    s = subject
    show_shortcuts(s.wizard)
    assert s.page.start_learning()
    before = s.path.read_bytes()
    qt = qt_modules()
    if action == "hide":
        s.wizard.hide()
    elif action == "reject":
        s.wizard.reject()
    elif action == "back":
        s.wizard.back()
        assert s.wizard.currentId() == s.wizard.PAGE_MODEL
    elif action == "focus":
        s.wizard.button(qt.QtWidgets.QWizard.CancelButton).setFocus()
    elif action == "deactivate":
        qt.QtWidgets.QApplication.sendEvent(s.wizard, qt.QtCore.QEvent(qt.QtCore.QEvent.WindowDeactivate))
    elif action == "close":
        s.page.close()
    else:
        assert not s.wizard.finish_onboarding()
    qt.QtWidgets.QApplication.processEvents()
    assert s.stops == [1] and not s.starts[0][1]()
    s.page.accept_status(1, "captured", "f8")
    assert s.page.primary.text() == "ctrl+win" and s.path.read_bytes() == before


def test_cancellation_waits_for_retirement_and_stale_status_cannot_change_successor(subject):
    s = subject
    show_shortcuts(s.wizard)
    assert s.page.start_learning()
    s.page.cancel_learning()
    assert s.page.learning and not s.page.isComplete() and not s.page.learn_button.isEnabled()
    s.page.accept_status(1, "capturing", "")
    assert "Stopping" in s.page.learn_status.text()
    s.page.accept_status(1, "cancelled", "")
    assert s.page.isComplete() and s.page.start_learning()
    assert s.starts[1][1]() and not s.starts[0][1]()
    s.page.accept_status(1, "captured", "f8")
    assert s.page.learning and s.page.primary.text() == "ctrl+win"
    s.page.accept_status(2, "captured", "ctrl+alt+f8")
    assert s.page.primary.text() == "ctrl+alt+f8"


@pytest.mark.parametrize("state,chord", [("expired", ""), ("invalid", ""), ("failed", ""), ("captured", "private <invalid>")])
def test_failed_learning_keeps_the_previous_shortcut_without_rendering_backend_data(subject, state, chord):
    s = subject
    show_shortcuts(s.wizard)
    assert s.page.start_learning()
    s.page.accept_status(1, state, chord)
    assert s.page.primary.text() == "ctrl+win" and s.page.isComplete()
    assert "private" not in s.page.learn_status.text()


def test_busy_capture_refusal_keeps_manual_entry_available_and_configuration_unchanged(subject):
    s = subject
    before = s.path.read_bytes()
    show_shortcuts(s.wizard)
    s.page.start_callback = lambda *args: 0
    assert not s.page.start_learning() and s.page.isComplete()
    assert not s.page._permit.is_set() and s.page.primary.isEnabled()
    assert s.path.read_bytes() == before


def test_unobserved_cleanup_keeps_setup_incomplete_and_requires_restart(subject):
    s = subject
    show_shortcuts(s.wizard)
    assert s.page.start_learning()
    s.page.accept_status(1, "cleanup_failed", "")
    assert s.page.learning and not s.page.isComplete() and not s.page._permit.is_set()
    assert not s.page.learn_button.isEnabled() and not s.page.primary.isEnabled()
    assert "restart Saydraft" in s.page.learn_status.text()
    before = s.path.read_bytes()
    assert not s.wizard.finish_onboarding() and s.path.read_bytes() == before


def test_duplicate_alternate_moves_to_primary_with_an_explanation(subject):
    s = subject
    s.page.primary.setText("F9")
    assert s.page.isComplete() and "disabled" in s.page.validation.text()
    assert s.wizard.finish_onboarding()
    hotkeys = load_config(config_path=s.path)["hotkeys"]
    assert hotkeys["speech"] == "F9" and not hotkeys["speech_alternative"]


def test_latest_conflict_refuses_finish_and_preserves_every_configuration_byte(subject):
    s = subject
    s.page.primary.setText("f8")
    latest = load_config(config_path=s.path)
    latest["hotkeys"]["speech_alternative"] = "f8"
    save_config(latest, s.path)
    before = s.path.read_bytes()
    assert not s.wizard.finish_onboarding()
    assert "Shortcut" in s.wizard.finish_status_label.text()
    assert s.path.read_bytes() == before


def test_unchanged_setup_preserves_newer_shortcuts_and_other_preferences(subject):
    s = subject
    latest = load_config(config_path=s.path)
    latest["hotkeys"].update(speech="f8", hands_free="f7")
    latest["recording"]["max_seconds"] = 90
    save_config(latest, s.path)
    assert s.wizard.finish_onboarding()
    saved = load_config(config_path=s.path)
    assert saved["hotkeys"] == latest["hotkeys"]
    assert saved["recording"] == latest["recording"]


def test_explicit_preset_stages_only_its_three_bindings_and_preserves_other_choices(tmp_path):
    qt_modules()
    path = write_config(tmp_path, {"hotkeys": {"speech": "f8", "hands_free": "f7", "paste_last": "f6"}})
    wizard = OnboardingWizard(config_path=path)
    try:
        before = path.read_bytes()
        assert "Custom" in wizard.shortcuts_page.preset_label.text()
        wizard.shortcuts_page.use_preset()
        assert path.read_bytes() == before and wizard.finish_onboarding()
        saved = load_config(config_path=path)["hotkeys"]
        assert (saved["speech"], saved["hands_free"], saved["paste_last"]) == (
            "ctrl+win", "ctrl+win+space", "shift+alt+z")
        assert saved["save"] == "f10" and saved["speech_alternative"] == "f9"
    finally:
        wizard.close()


def test_other_app_check_is_explicit_off_thread_and_advisory(subject):
    s = subject
    main = threading.get_ident()
    assert not s.checks and s.page.check_other_apps()
    settle(lambda: s.page._probe_future is None)
    assert s.checks and s.checks[0] != main
    assert "Wispr Flow is running" in s.page.other_warning.text() and s.page.isComplete()


def test_checked_advisory_tracks_the_staged_chord_without_another_process_scan(subject):
    s = subject
    s.page.original["hands_free"] = "f7"
    assert s.page.check_other_apps()
    settle(lambda: s.page._probe_future is None)
    assert "Wispr Flow is running" in s.page.other_warning.text()
    s.page.primary.setText("f8")
    assert "Wispr Flow is running" not in s.page.other_warning.text()
    s.page.primary.setText("ctrl+win")
    assert "Wispr Flow is running" in s.page.other_warning.text() and len(s.checks) == 1


def test_hidden_or_closed_conflict_probe_cannot_publish_late_and_never_joins_the_gui(subject):
    s = subject
    entered, release = threading.Event(), threading.Event()

    def detector():
        entered.set()
        assert release.wait(3)
        return True

    s.page.detector = detector
    show_shortcuts(s.wizard)
    assert s.page.check_other_apps() and entered.wait(1)
    try:
        assert not s.page.check_other_apps()
        began = time.monotonic()
        s.wizard.hide()
        assert time.monotonic() - began < .2
        release.set()
        settle(lambda: s.page._probe_future is None)
        assert "Wispr Flow is running" not in s.page.other_warning.text()
        assert s.page.conflict_button.isEnabled()
    finally:
        release.set()


def test_real_worker_reserves_learning_until_teardown_and_applies_pending_settings():
    from dataclasses import replace
    from saydraft.audio.devices import InputSelection
    from tests.test_session_worker import Executor, make_worker

    worker, _, _, events, signals, _ = make_worker(queued=True)
    controls, owners = Executor(queued=True), []
    worker.shortcut_capture.executor.shutdown(wait=False)
    worker.shortcut_capture.executor = controls

    class Owner:
        status = {"reason": None}

        def __init__(self, *args, **kwargs):
            self.closed = False
            owners.append(self)

        def start(self):
            pass

        def close(self):
            self.closed = True
            return True

    worker.shortcut_capture.hooks_factory = Owner
    worker.shortcut_capture.guard_factory = lambda window: lambda: window == 123
    try:
        generation = worker.start_shortcut_capture(123, lambda: True)
        assert generation and worker.busy
        assert not worker.start_recording() and not worker.paste_last() and not worker.benchmark_hardware()
        assert not worker.start_microphone_test(InputSelection())
        controls.drain()
        services = worker.services
        worker.services_factory = lambda config, **kwargs: replace(services, config=config)
        config = copy.deepcopy(services.config)
        config["hotkeys"]["speech"] = "f8"
        worker.configure(config)
        assert worker.busy and not owners[0].closed
        controls.drain()
        assert owners[0].closed and not worker.busy and worker.services.config == config
        assert not events and not worker.services.recorder.started
        assert ("shortcut_capture_status", generation, "cancelled", "") in signals
    finally:
        worker.shutdown()
        controls.drain()


def test_owned_setup_to_native_matcher_to_queued_ui_saves_a_learned_chord(tmp_path):
    from saydraft.app import WorkerController, create_worker_signals
    from saydraft.hotkeys._win32_hooks import KeyboardPacket
    from saydraft.hotkeys.llhook import LowLevelHooks
    from tests.test_native_hooks import API
    from tests.test_session_worker import make_worker

    qt = qt_modules()
    signals = create_worker_signals(qt.QtCore)
    controller = WorkerController(signals)
    worker, _, _, events, _, _ = make_worker()
    controller.core = worker
    worker.emit_callback = controller._emit
    api, owners, forbidden = API(), [], []

    def hooks(*args, **kwargs):
        owner = LowLevelHooks(*args, api_factory=lambda: api, **kwargs)
        owners.append(owner)
        return owner

    worker.shortcut_capture.hooks_factory = hooks
    worker.shortcut_capture.guard_factory = lambda window: lambda: window == int(wizard.winId())
    worker.services.context.capture = lambda: forbidden.append("foreground capture")
    worker.services.recorder.start = lambda: forbidden.append("microphone")
    path = write_config(tmp_path)
    wizard = OnboardingWizard(config_path=path, shortcut_start_callback=controller.start_shortcut_capture,
        shortcut_cancel_callback=controller.cancel_shortcut_capture, shortcut_conflict_detector=lambda: False)
    signals.shortcut_capture_status.connect(wizard.shortcuts_page.accept_status, qt.QtCore.Qt.QueuedConnection)
    try:
        before = path.read_bytes()
        show_shortcuts(wizard)
        assert wizard.shortcuts_page.start_learning()
        settle(lambda: bool(owners) and owners[0].status["state"] == "running")
        for message, code in ((0x100, 0xA2), (0x100, 0x5B), (0x100, 0x77),
                              (0x101, 0x77), (0x101, 0xA2), (0x101, 0x5B)):
            assert api.emit("keyboard", message, KeyboardPacket(code)) == 1
        settle(lambda: not wizard.shortcuts_page.learning)
        assert api.closed and api.trace.count("mask") == 1 and not worker.busy
        assert not forbidden and not events and path.read_bytes() == before
        assert wizard.shortcuts_page.primary.text() == "ctrl+win+f8"
        assert wizard.finish_onboarding()
        assert json.loads(path.read_text(encoding="utf-8"))["hotkeys"]["speech"] == "ctrl+win+f8"
    finally:
        wizard.close()
        worker.shutdown()
