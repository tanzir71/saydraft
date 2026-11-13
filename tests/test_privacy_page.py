import threading
import time

import pytest

from saydraft.config import default_config,load_config
from saydraft.core.audio_retention import AudioRetention,AudioRetentionUpdate
from saydraft.data.retention import AudioRetentionPolicy,AudioRetentionResult,expire_recordings
from saydraft.privacy.firewall import FirewallStatus
from saydraft.ui.privacy_page import PrivacyPage
from tests.test_history_window import qt_modules
from tests.test_settings_window import write_config,FakeAutoStartManager


@pytest.fixture
def subject():
    qt=qt_modules()
    saved={"policy":AudioRetentionPolicy()}
    calls=[]
    checkbox=qt.QtWidgets.QCheckBox("Save recordings locally for History retries")
    page=PrivacyPage(default_config(),checkbox,saved_policy=lambda:saved["policy"],
        cleanup_callback=lambda policy:calls.append(policy) or True,firewall_provider=lambda:FirewallStatus("found",1))
    try:
        yield page,qt,saved,calls
    finally:
        page.close()


def settle_firewall(page):
    app=qt_modules().QtWidgets.QApplication.instance()
    deadline=time.monotonic()+3
    while page._future is not None and time.monotonic()<deadline:
        app.processEvents()
        time.sleep(.003)
    assert page._future is None


def test_privacy_starts_off_without_background_or_os_inspection(subject,monkeypatch):
    page,_,_,calls=subject
    assert page.policy()==AudioRetentionPolicy() and page._pool is None and not calls
    assert not page.retention_combo.isEnabled() and not page.cleanup_button.isEnabled()
    monkeypatch.setattr("saydraft.privacy.netguard.NetworkGuard.is_installed",lambda:True)
    page.refresh_network()
    assert page.network_status.text()=="Offline mode active"
    monkeypatch.setattr("saydraft.privacy.netguard.NetworkGuard.is_installed",lambda:False)
    page.refresh_network()
    assert "unavailable" in page.network_status.text()
    assert page.firewall_status.text()=="Windows Firewall: not checked."


def test_expiry_is_staged_until_saved_and_cleanup_feedback_uses_only_counts(subject):
    page,_,saved,calls=subject
    page.checkbox.setChecked(True)
    page.retention_combo.setCurrentIndex(1)
    page.days_spin.setValue(7)
    assert page.policy()==AudioRetentionPolicy(True,7) and not page.cleanup()
    assert not calls and not page.cleanup_button.isEnabled()
    saved["policy"]=page.policy()
    page.policy_saved()
    assert page.cleanup_button.isEnabled() and page.cleanup()
    assert calls==[AudioRetentionPolicy(True,7)] and not page.cleanup_button.isEnabled()
    page.accept_retention(AudioRetentionUpdate(saved["policy"],"ready",AudioRetentionResult(removed=2,unavailable=1,skipped=3)))
    assert "Removed 2" in page.retention_status.text() and "Left 3" in page.retention_status.text()
    assert page.cleanup_button.isEnabled()


def test_off_preserves_the_staged_time_limit_without_running_cleanup(subject):
    page,_,_,calls=subject
    page.set_policy(AudioRetentionPolicy(True,17))
    page.checkbox.setChecked(False)
    assert page.policy()==AudioRetentionPolicy(False,17) and not page.days_spin.isEnabled()
    assert not page.cleanup() and not calls


def test_old_policy_feedback_cannot_overwrite_current_work(subject):
    page,_,saved,_=subject
    saved["policy"]=AudioRetentionPolicy(True,30)
    page.set_policy(saved["policy"])
    page.accept_retention(AudioRetentionUpdate(saved["policy"],"working"))
    old=AudioRetentionUpdate(AudioRetentionPolicy(True,7),"ready",AudioRetentionResult(removed=99))
    page.accept_retention(old)
    assert page._working and "99" not in page.retention_status.text()
    page.accept_retention(AudioRetentionUpdate(saved["policy"],"working",generation=3))
    page.accept_retention(AudioRetentionUpdate(saved["policy"],"ready",AudioRetentionResult(removed=99),generation=2))
    assert page._working and "99" not in page.retention_status.text()


@pytest.mark.parametrize("status",[FirewallStatus("found",2),FirewallStatus("absent"),FirewallStatus(),FirewallStatus("unsupported")],
    ids=["found","absent","unknown","unsupported"])
def test_firewall_read_reports_its_scope_without_claiming_complete_native_coverage(subject,status):
    page,_,_,_=subject
    page.firewall_provider=lambda:status
    assert page.check_firewall()
    settle_firewall(page)
    assert "not verified" in page.firewall_status.text() and page.firewall_button.isEnabled()
    if status.state=="found":
        assert "2 matching" in page.firewall_status.text()


def test_blocked_firewall_read_keeps_gui_responsive_and_close_drops_the_result(subject):
    page,qt,_,_=subject
    entered,release=threading.Event(),threading.Event()
    def blocked():
        entered.set()
        assert release.wait(3)
        return FirewallStatus("found",2)
    page.firewall_provider=blocked
    try:
        assert page.check_firewall() and entered.wait(1)
        ticks=[]
        qt.QtCore.QTimer.singleShot(0,lambda:ticks.append(True))
        qt.QtWidgets.QApplication.processEvents()
        assert ticks
        future=page._future
        page.close()
        release.set()
        future.result(timeout=2)
        qt.QtWidgets.QApplication.processEvents()
        assert "2 matching" not in page.firewall_status.text()
    finally:
        release.set()


def test_a_queued_old_firewall_result_cannot_finish_a_new_check(subject):
    page,qt,_,_=subject
    assert page.check_firewall()
    page._future.result(timeout=2)  # Leave the first Qt result queued.
    entered,release=threading.Event(),threading.Event()
    def blocked():
        entered.set()
        assert release.wait(3)
        return FirewallStatus("absent")
    page.firewall_provider=blocked
    try:
        assert page.check_firewall() and entered.wait(1)
        qt.QtWidgets.QApplication.processEvents()
        assert not page.firewall_button.isEnabled() and "Checking" in page.firewall_status.text()
        release.set()
        settle_firewall(page)
        assert "no matching" in page.firewall_status.text()
    finally:
        release.set()


def test_shared_settings_save_applies_the_exact_policy_without_running_a_staged_cleanup(tmp_path):
    from saydraft.ui.settings_page import SettingsPage
    qt_modules()
    calls=[]
    path=write_config(tmp_path)
    page=SettingsPage(config_path=path,snippets_path=tmp_path/"snippets.txt",autostart_manager=FakeAutoStartManager(),
        audio_cleanup_callback=lambda policy:calls.append(policy) or True,firewall_status_provider=lambda:FirewallStatus())
    try:
        page.privacy_page.set_policy(AudioRetentionPolicy(True,11))
        assert not page.privacy_page.cleanup()
        assert page.apply_changes()
        assert AudioRetentionPolicy.from_config(load_config(config_path=path))==AudioRetentionPolicy(True,11)
        assert page.privacy_page.cleanup_button.isEnabled() and not calls
    finally:
        page.privacy_page.close()
        page.close()


def test_applied_cleanup_composes_real_sqlite_expiry_controller_and_queued_qt_feedback(subject,tmp_path):
    from saydraft.app import WorkerController,create_worker_signals
    from tests.test_session_worker import make_worker,Timer
    from tests.test_audio_retention import recording,NOW
    page,qt,saved,_=subject
    store,audio,path=recording(tmp_path)
    original=store.get_row(1)
    worker,_,_,_,_,_=make_worker()
    signals=create_worker_signals(qt.QtCore)
    controller=WorkerController(signals)
    controller.core=worker
    worker.emit_callback=controller._emit
    worker._retention_generation=1
    policy=saved["policy"]=AudioRetentionPolicy(True,30)
    page.set_policy(policy)
    page.cleanup_callback=controller.cleanup_audio
    signals.audio_retention_updated.connect(page.accept_retention,qt.QtCore.Qt.QueuedConnection)
    owner=AudioRetention(store,audio,policy,timer_factory=Timer,
        sweep=lambda *args,**kwargs:expire_recordings(*args,now=NOW,**kwargs),
        changed=lambda update:worker._audio_retention_changed(1,update))
    worker.audio_retention=owner
    try:
        assert page.cleanup()
        deadline=time.monotonic()+3
        while page._working and time.monotonic()<deadline:
            qt.QtWidgets.QApplication.processEvents()
            time.sleep(.003)
        assert not page._working and "Removed 1" in page.retention_status.text()
        assert not path.exists() and store.get_row(1).raw_text==original.raw_text
        assert worker.services.recorder.started==0
    finally:
        worker.shutdown()
