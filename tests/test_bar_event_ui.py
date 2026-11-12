import threading
from types import SimpleNamespace

import pytest

from saydraft.core.bar_status import BarPhase, BarUpdate
from saydraft.insert.inserter import InsertionResult
from tests.test_pill_ui import qt_modules
from tests.test_session_worker import make_worker


@pytest.mark.parametrize("outcome", ["inserted", "refused", "history_failure"])
def test_real_app_signal_wiring_uses_delivery_outcomes_and_rejects_late_events(monkeypatch, outcome):
    from saydraft.app import SaydraftApp
    from saydraft.config import default_config
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    application = qt.QtWidgets.QApplication.instance()
    monkeypatch.setattr(qt.QtWidgets.QApplication, "exec", lambda self: 0)
    monkeypatch.setattr("saydraft.ui.fonts.install_bundled_fonts", lambda *args, **kwargs: None)
    monkeypatch.setattr("saydraft.ui.theme.install_theme", lambda *args, **kwargs: None)
    monkeypatch.setattr(qt.QtWidgets.QApplication, "clipboard", staticmethod(lambda: pytest.fail("Owner clipboard access")))
    worker, clock, _, _, _, _ = make_worker()
    if outcome != "inserted":
        worker.services.inserter.insert_text = lambda *args, **kwargs: InsertionResult("not_inserted", "none", "focus_changed")
    if outcome == "history_failure":
        def fail(_entry):
            raise OSError("fixture history unavailable")
        worker.services.history.append = fail
    updates, delivery_threads, timers = [], [], []

    class Controller:
        supports_bar_updates = True

        def __init__(self, signals):
            self.signals = signals
            worker.emit_callback = lambda name, *args: getattr(signals, name).emit(*args)

            def publish(update):
                updates.append(update)
                signals.bar_updated.emit(update)

            worker.bar_status.callback = publish

        def start(self):
            pass

        def stop(self):
            pass

        def model_label(self):
            return "Public fixture"

        def hotkey_hint(self):
            return "Ctrl+Win"

        def is_current_bar(self, generation):
            return worker.bar_status.is_current(generation)

        def is_hands_free(self):
            return False

    tray = SimpleNamespace(set_listening=lambda *_: None, set_state=lambda *_: None,
        show_notification=lambda *_: None, set_model_label=lambda *_: None)
    config = default_config()
    config["app"]["onboarded"] = True
    app = SaydraftApp(qt_modules=qt, controller_factory=Controller, tray_factory=lambda **kwargs: tray,
        pill_factory=lambda **kwargs: SaydraftPill(**kwargs,
            screen_geometry_provider=lambda: qt.QtCore.QRect(0, 0, 1000, 800),
            timer_single_shot=lambda ms, callback: timers.append(callback)),
        config_loader=lambda **kwargs: config, crash_guard_installer=lambda **kwargs: None)
    original = app._apply_bar_update

    def observe(update):
        delivery_threads.append(threading.get_ident())
        original(update)

    app._apply_bar_update = observe
    assert app.run() == 0
    try:
        start = threading.Thread(target=worker.start_recording)
        start.start()
        start.join(2)
        assert not start.is_alive() and app.pill.state == PillState.IDLE
        application.processEvents()
        assert app.pill.state == PillState.RECORDING
        clock.now = 1
        stop = threading.Thread(target=worker.stop_recording)
        stop.start()
        stop.join(2)
        assert not stop.is_alive()
        application.processEvents()
        expected = PillState.IDLE if outcome == "inserted" else PillState.WARNING
        assert app.pill.state == expected
        if outcome != "inserted":
            assert app.pill.elapsed_label.text().startswith("Not saved" if outcome == "history_failure" else "Saved,")
        old_generation = updates[-1].generation
        app.signals.processing_finished.emit("legacy completion")
        app.signals.error.emit("No microphone")
        application.processEvents()
        assert app.pill.state == expected
        worker.start_recording()
        application.processEvents()
        assert app.pill.state == PillState.RECORDING
        app.signals.bar_updated.emit(BarUpdate(old_generation, BarPhase.IDLE))
        app.signals.bar_updated.emit(BarUpdate(old_generation, BarPhase.ERROR, "microphone_unavailable"))
        app.signals.bar_updated.emit(BarUpdate(old_generation, BarPhase.NOT_INSERTED, "focus_changed", True))
        if timers:
            timers[0]()  # The old warning's collapse callback is stale too.
        application.processEvents()
        assert app.pill.state == PillState.RECORDING
        assert delivery_threads and set(delivery_threads) == {threading.get_ident()}
    finally:
        app.signals.blockSignals(True)
        worker.shutdown()
        app.pill.hide()
        application.aboutToQuit.disconnect(app.controller.stop)
        application.aboutToQuit.disconnect(app.pill.hide)
        app.pill.deleteLater()
        app.signals.deleteLater()
        application.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_preparing_is_honest_static_and_still_allows_hands_free_cancellation():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    bar = SaydraftPill(screen_geometry_provider=lambda: qt.QtCore.QRect(0, 0, 1000, 800))
    bar.show_preparing()
    try:
        assert bar.state == PillState.PREPARING and bar.status_label.text() == "Getting ready"
        assert bar.size() == qt.QtCore.QSize(164, 36)
        assert "microphone has not started" in bar.accessibleName()
        heights = bar.level_meter.heights
        bar.update_level(1.)
        bar.update_preview("Must never appear before capture starts")
        bar.advance_frame()
        assert bar.level_meter.heights == heights and not bar.preview_label.text()
        assert not bar.elapsed_timer.isActive()
        bar.set_hands_free(True)
        assert bar.target.kind == "stop" and bar.target.isVisible()
        assert not bar.level_meter.isVisible()  # Leaves the stop target unobscured.
    finally:
        bar.hide()
