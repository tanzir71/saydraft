import threading
import time

import pytest

from saydraft.config import default_config, load_config
from saydraft.ui.updates import UpdatePresenter, UpdatesCard
from saydraft.updates import UpdateResult
from tests.test_history_window import qt_modules
from tests.test_settings_window import FakeAutoStartManager, write_config


def settle(presenter):
    app = qt_modules().QtWidgets.QApplication.instance()
    until = time.monotonic() + 3
    while time.monotonic() < until:
        app.processEvents()
        if presenter.result.state != 'checking':
            app.processEvents()
            return
        time.sleep(.003)
    pytest.fail('Update fixture did not settle')


def test_saved_opt_in_controls_background_request_notice_and_explicit_release_action():
    qt_modules()
    calls, notices, opened = [], [], []
    presenter = UpdatePresenter(checker=lambda **options: calls.append(options) or UpdateResult('available', '0.2.0'),
        on_available=notices.append, opener=lambda url: opened.append(url.toString()) or True)
    card = UpdatesCard(default_config(), presenter=presenter)
    try:
        assert not presenter.timer.isActive() and not calls
        assert not card.enabled_checkbox.isChecked() and not card.check_button.isEnabled()
        card.enabled_checkbox.setChecked(True)
        assert not calls and not card.check_button.isEnabled() and not card.open_release()
        assert 'Save' in card.status.text()
        card.apply_policy(True)
        settle(presenter)
        assert len(calls) == len(notices) == 1 and not opened
        assert '0.2.0' in card.status.text() and card.release_button.isEnabled()
        assert presenter.timer.isActive() and presenter.timer.interval() == 86_400_000
        assert card.open_release() and opened == ['https://github.com/tanzir71/saydraft/releases/tag/v0.2.0']
        card.apply_policy(True)
        assert len(calls) == 1
        card.enabled_checkbox.setChecked(False)
        card.apply_policy(False)
        assert not presenter.timer.isActive() and not card.open_release()
    finally:
        presenter.close()
        card.close()


def test_background_check_keeps_event_loop_responsive_and_opt_out_drops_queued_success():
    qt = qt_modules()
    entered, release = threading.Event(), threading.Event()
    notices = []

    def blocked(**options):
        entered.set()
        assert release.wait(3)
        return UpdateResult('available', '0.2.0')

    presenter = UpdatePresenter(checker=blocked, on_available=notices.append)
    try:
        presenter.configure(True)
        assert entered.wait(1)
        ticks = []
        qt.QtCore.QTimer.singleShot(0, lambda: ticks.append(True))
        qt.QtWidgets.QApplication.processEvents()
        assert ticks
        presenter.configure(False)
        release.set()
        settle(presenter)
        assert presenter.result.state == 'disabled' and not notices
    finally:
        release.set()
        presenter.close()


def test_settings_save_persists_opt_in_and_drives_the_shared_presenter(tmp_path):
    from saydraft.ui.settings_page import SettingsPage

    qt_modules()
    calls = []
    presenter = UpdatePresenter(checker=lambda **_: calls.append(True) or UpdateResult('no_release'))
    path = write_config(tmp_path)
    page = SettingsPage(config_path=path, snippets_path=tmp_path / 'snippets.txt',
                        autostart_manager=FakeAutoStartManager(), update_presenter=presenter)
    try:
        card = page.privacy_page.updates_card
        card.enabled_checkbox.setChecked(True)
        assert not calls and not load_config(config_path=path)['updates']['enabled']
        assert page.apply_changes()
        settle(presenter)
        assert calls == [True] and load_config(config_path=path)['updates']['enabled']
        assert 'No published' in card.status.text()
        card.enabled_checkbox.setChecked(False)
        assert page.apply_changes()
        assert not load_config(config_path=path)['updates']['enabled'] and not presenter.controller.enabled
    finally:
        presenter.close()
        page.privacy_page.close()
        page.close()


def test_app_starts_saved_checks_and_shuts_the_service_down_without_owner_adapters():
    from saydraft.app import SaydraftApp
    from tests.test_qt_app_shell import FakeSignalChannel, fake_qt_modules
    from types import SimpleNamespace

    calls = []

    class Presenter:
        def __init__(self, *, parent, on_available):
            assert parent is app.qt_app
            self.on_available = on_available

        def configure(self, enabled):
            calls.append(enabled)

        def close(self):
            calls.append('closed')

    app = SaydraftApp(qt_modules=fake_qt_modules(), update_presenter_factory=Presenter)
    app.qt_app = SimpleNamespace(aboutToQuit=FakeSignalChannel())
    app.signals = SimpleNamespace(notification_requested=FakeSignalChannel())
    app._configure_updates(default_config())
    app._configure_updates({'updates': {'enabled': True}})
    app.update_presenter.on_available(UpdateResult('available', '0.2.0'))
    app.qt_app.aboutToQuit.emit()
    assert calls == [False, True, 'closed']
    assert '0.2.0' in app.signals.notification_requested.emitted[-1][0]


def test_destroying_owned_update_controls_retires_the_request(monkeypatch):
    qt = qt_modules()
    entered, release = threading.Event(), threading.Event()
    created = []

    def checker(**options):
        entered.set()
        assert release.wait(3)
        return UpdateResult('available', '0.2.0')

    def presenter(**kwargs):
        value = UpdatePresenter(checker=checker, **kwargs)
        created.append(value)
        return value

    monkeypatch.setattr('saydraft.ui.updates.UpdatePresenter', presenter)
    config = default_config()
    config['updates']['enabled'] = True
    card = UpdatesCard(config)
    try:
        assert entered.wait(1) and created[0].controller.enabled
        card.deleteLater()
        qt.QtCore.QCoreApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)
        assert not created[0].controller.enabled
    finally:
        release.set()
