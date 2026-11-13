from pathlib import Path
import threading
import time

import pytest

from saydraft.privacy.firewall_control import FirewallChange
from tests.test_history_window import qt_modules


@pytest.fixture
def card():
    qt_modules()
    from saydraft.ui.firewall_card import FirewallCard
    value = FirewallCard(target_provider=lambda: Path("C:/Owned/Saydraft.exe"),
                         changer=lambda action: FirewallChange("applied"), confirm=lambda *args: True)
    try:
        yield value
    finally:
        if not value._closed:
            value.close()


def settle(card):
    app = qt_modules().QtWidgets.QApplication.instance()
    until = time.monotonic() + 3
    while card._busy and time.monotonic() < until:
        app.processEvents()
        time.sleep(.003)
    assert not card._busy


def test_no_background_query_or_change_and_confirmation_cancels(card):
    calls = []
    card.changer = lambda action: calls.append(action)
    assert card._thread is None and card.block_button.isEnabled()
    card.confirm = lambda action, target: False
    assert not card.request("block") and not calls
    card.target_provider = lambda: None
    card._actions()
    assert not card.block_button.isEnabled() and not card.remove_button.isEnabled()
    assert not card.request("remove") and not calls


@pytest.mark.parametrize("state,fragment", [("cancelled", "cancelled"), ("conflict", "unchanged"),
    ("failed", "could not"), ("unknown", "unknown"), ("unsupported", "packaged"), ("busy", "still running")])
def test_results_use_plain_bounded_feedback(card, state, fragment):
    card.changer = lambda action: FirewallChange(state)
    assert card.request("block")
    settle(card)
    assert fragment in card.status.text() and card.block_button.isEnabled()


@pytest.mark.parametrize("action,fragment", [("block", "Remove it before"), ("remove", "Other firewall policies")])
def test_success_explains_download_recovery_and_effective_policy(card, action, fragment):
    assert card.request(action)
    settle(card)
    assert fragment in card.status.text() and "confirm the effective policy" in card.status.text()


def test_pending_uac_keeps_qt_responsive_and_close_retires_late_result(card):
    qt = qt_modules()
    entered, release = threading.Event(), threading.Event()
    def blocked(action):
        entered.set()
        assert release.wait(3)
        return FirewallChange("applied")
    card.changer = blocked
    try:
        assert card.request("block") and entered.wait(1)
        assert not card.request("remove") and not card.remove_button.isEnabled()
        ticks = []
        qt.QtCore.QTimer.singleShot(0, lambda: ticks.append(True))
        qt.QtWidgets.QApplication.processEvents()
        assert ticks
        old = card.status.text()
        card.close()
        release.set()
        card._thread.join(2)
        qt.QtWidgets.QApplication.processEvents()
        assert card.status.text() == old
    finally:
        release.set()


def test_stale_result_cannot_finish_another_generation(card):
    card._generation = 2
    card._busy = True
    card._accept(1, "block", FirewallChange("applied"))
    assert card._busy and "configured" not in card.status.text()


def test_owned_destruction_retires_pending_work(card):
    qt = qt_modules()
    card.deleteLater()
    qt.QtCore.QCoreApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)
    assert card._closed
