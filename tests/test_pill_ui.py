import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def qt_modules():
    from PySide6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


def test_pill_recording_state_shows_smoothed_level_and_compact_geometry():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    ticks = [100.0]
    pill = SaydraftPill(
        qt_modules=qt,
        hotkey_hint="F9",
        clock=lambda: ticks[0],
        screen_geometry_provider=lambda: qt.QtCore.QRect(100, 200, 800, 600),
    )

    pill.show_recording()
    ticks[0] = 165.0
    pill.refresh_elapsed()
    pill.update_level(0.125)
    ticks[0] += .030
    pill.advance_frame()

    assert pill.state == PillState.RECORDING
    assert pill.isVisible()
    assert pill.status_label.text() == "Recording"
    assert pill.elapsed_label.text() == "1:05"
    assert pill.hotkey_label.text() == "F9"
    assert pill.level_meter.level == pytest.approx(1 - 2.718281828 ** -1)
    assert len(pill.level_meter.heights) == 14
    assert pill.size() == qt.QtCore.QSize(164, 36)
    assert pill.geometry().left() == 418
    assert pill.geometry().top() == 740  # Work area ends at 800; bottom gap is 24.
    assert not pill.target.isVisible()  # Push-to-talk has no red stop dot.
    pill.hide()


def test_pill_processing_freezes_bars_and_completion_collapses_immediately():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    ticks = [0.]
    pill = SaydraftPill(
        qt_modules=qt,
        clock=lambda: ticks[0],
    )
    pill.show_recording()
    pill.update_level(.1)
    ticks[0] = .1
    pill.show_processing()
    heights = pill.level_meter.heights
    pill.update_level(1.)
    ticks[0] = 2.
    pill.advance_frame()

    assert pill.state == PillState.PROCESSING
    assert pill.isVisible()
    assert pill.status_label.text() == "Cleaning up"
    assert pill.level_meter.heights == heights
    assert pill.level_meter.shimmer_seconds == 1.9
    assert not pill.spinner_label.isVisible() and not pill.spinner_label.text()

    pill.finish_success()
    assert pill.state == PillState.IDLE
    assert pill.size() == qt.QtCore.QSize(36, 8)
    assert not pill.animation_timer.isActive()
    pill.set_idle_enabled(False)
    assert not pill.isVisible()


def test_pill_error_stays_available_until_fixed_or_next_session():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    scheduled = []
    pill = SaydraftPill(
        qt_modules=qt,
        timer_single_shot=lambda ms, callback: scheduled.append((ms, callback)),
    )

    pill.show_error("No microphone")

    assert pill.state == PillState.ERROR
    assert pill.isVisible()
    assert pill.status_label.text() == "No microphone"
    assert pill.colors["barError"] == "#B42318"
    assert pill.target.isVisible() and pill.target.kind == "fix"
    assert pill.fix_page == "microphone"
    assert not scheduled
    fixes = []
    pill.fix_requested.connect(fixes.append)
    pill.target.click()
    assert fixes == ["microphone"]
    pill.hide()


def test_pill_is_frameless_topmost_tool_window():
    from saydraft.ui.pill import SaydraftPill

    qt = qt_modules()
    pill = SaydraftPill(qt_modules=qt)
    flags = pill.windowFlags()

    assert flags & qt.QtCore.Qt.FramelessWindowHint
    assert flags & qt.QtCore.Qt.WindowStaysOnTopHint
    assert flags & qt.QtCore.Qt.Tool
    assert flags & qt.QtCore.Qt.WindowDoesNotAcceptFocus
    assert flags & qt.QtCore.Qt.WindowTransparentForInput
    assert flags & qt.QtCore.Qt.NoDropShadowWindowHint
    assert pill.testAttribute(qt.QtCore.Qt.WA_TranslucentBackground)
    assert not pill.target.windowFlags() & qt.QtCore.Qt.WindowTransparentForInput
    assert pill.target.windowFlags() & qt.QtCore.Qt.WindowDoesNotAcceptFocus


def test_offscreen_bar_placement_does_not_query_the_active_desktop(monkeypatch):
    from saydraft.ui import pill as module
    qt = qt_modules()
    app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication([])
    assert app.platformName() == "offscreen"
    def forbidden(*_args):
        raise AssertionError("Active desktop lookup during an offscreen test")
    monkeypatch.setattr(module.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetForegroundWindow=forbidden)), raising=False)
    monkeypatch.setattr(module.QtGui.QCursor, "pos", forbidden)
    assert module.focused_window_center() is None


def test_idle_hover_and_hands_free_have_only_their_small_action_targets():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    pill = SaydraftPill(screen_geometry_provider=lambda: qt.QtCore.QRect(-1200, 100, 1200, 900))
    calls = []
    pill.start_requested.connect(lambda: calls.append("start"))
    pill.stop_requested.connect(lambda: calls.append("stop"))
    pill.show_idle()
    assert pill.size() == qt.QtCore.QSize(36, 8)
    assert pill.target.size() == qt.QtCore.QSize(48, 24)
    assert pill.geometry().center().x() == -600
    bottom = pill.geometry().bottom()
    pill.set_hovered(True)
    assert pill.state == PillState.HOVER and pill.size() == qt.QtCore.QSize(160, 32)
    assert pill.geometry().bottom() == bottom
    assert pill.target.accessibleDescription() == "Hold Ctrl+Win to dictate"
    pill.target.click()
    pill.show_recording(hands_free=True)
    assert pill.target.kind == "stop" and pill.target.size() == qt.QtCore.QSize(24, 24)
    assert pill.rect().contains(pill.mapFromGlobal(pill.target.geometry().center()))
    pill.target.click()
    assert calls == ["start", "stop"]
    pill.set_hands_free(False)
    assert not pill.target.isVisible()
    pill.hide()
    assert not pill.target.isVisible() and not pill.animation_timer.isActive()


@pytest.mark.parametrize("saved", [True, False])
def test_warning_uses_actual_save_outcome_and_cannot_collapse_a_new_session(saved):
    from saydraft.ui.pill import PillState, SaydraftPill

    qt_modules()
    scheduled = []
    pill = SaydraftPill(timer_single_shot=lambda ms, cb: scheduled.append((ms, cb)))
    pill.show_not_inserted("password_field", saved=saved)
    assert pill.state == PillState.WARNING
    assert pill.status_label.text() == "Password field"
    assert pill.elapsed_label.text().startswith("Saved," if saved else "Not saved")
    assert scheduled[-1][0] == 2500 and not pill.target.isVisible()
    old_callback = scheduled[-1][1]
    pill.show_recording()
    old_callback()
    assert pill.state == PillState.RECORDING and pill.isVisible()
    pill.hide()


def test_warning_returns_to_idle_at_deadline_and_hiding_clears_preview():
    from saydraft.ui.pill import PillState, SaydraftPill

    qt_modules()
    scheduled = []
    pill = SaydraftPill(timer_single_shot=lambda ms, cb: scheduled.append(cb))
    pill.show_not_inserted("focus_changed", saved=True)
    scheduled[-1]()
    assert pill.state == PillState.IDLE
    pill.show_recording()
    pill.update_preview("private partial words")
    pill.hide()
    assert not pill.preview_label.text() and not pill.preview_label.isVisible()
    assert not pill.target.isVisible() and not pill.elapsed_timer.isActive()
