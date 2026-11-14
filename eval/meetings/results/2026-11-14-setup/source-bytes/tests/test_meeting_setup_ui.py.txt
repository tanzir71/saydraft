import copy
import threading
import time
from types import SimpleNamespace as NS

import pytest

from saydraft.audio.devices import InputSelection
from saydraft.meetings.devices import MeetingDevices, MeetingOutput
from saydraft.meetings.setup import MeetingSetupInspection, meeting_setup_plan
from tests.test_history_window import qt_modules
from tests.test_meeting_setup import pro_config


def settle(predicate, timeout=4):
    app = qt_modules().QtWidgets.QApplication.instance()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.002)
    assert predicate()


def inventory(channels=2):
    return MeetingDevices((InputSelection('Fixture microphone', 'WASAPI'),),
        (MeetingOutput('exact-fixture-endpoint', 'Fixture speakers', channels),))


def verified(config):
    plan = meeting_setup_plan(config)
    return MeetingSetupInspection(plan, (True,) * len(plan.model_ids))


@pytest.fixture
def make():
    qt_modules()
    windows = []
    def create(**options):
        from saydraft.ui.meeting_setup import MeetingSetupDialog
        config = pro_config()
        config['labs']['notetaker'] = True
        config = options.pop('config', config)
        calls = []
        def devices():
            calls.append('devices')
            return inventory()
        dialog = MeetingSetupDialog(config, start_callback=options.pop('start_callback',
            lambda request, **kwargs: calls.append(('start', request, kwargs)) or True),
            inspector=options.pop('inspector', verified), devices_provider=options.pop('devices_provider', devices),
            download_callback=options.pop('download_callback', lambda *args, **kwargs: calls.append('download')),
            **options)
        windows.append(dialog)
        dialog.show()
        return NS(dialog=dialog, calls=calls, config=config)
    yield create
    for dialog in windows:
        dialog.close()
        settle(lambda: not dialog._inflight and dialog.task is None)
        dialog.deleteLater()
    qt = qt_modules()
    qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def choose_devices(s):
    s.dialog.refresh.click()
    settle(lambda: not s.dialog._inflight)
    s.dialog.microphone.setCurrentIndex(1)
    s.dialog.output.setCurrentIndex(1)


def test_open_checks_cached_models_but_never_discovers_downloads_or_records(make):
    s = make()
    settle(lambda: not s.dialog._inflight)
    assert s.dialog.inspection.ready and not s.calls and not s.dialog.start_button.isEnabled()
    assert 'Source' in s.dialog.licenses.text() and 'GB' in s.dialog.size_note.text()
    choose_devices(s)
    assert s.calls == ['devices'] and not s.dialog.start_button.isEnabled()
    s.dialog.consent.setChecked(True)
    assert s.dialog.start_button.isEnabled()
    s.dialog.start_button.click()
    request, options = s.calls[-1][1:]
    assert request.desktop_endpoint == 'exact-fixture-endpoint' and request.microphone.name == 'Fixture microphone'
    assert request.max_seconds == 1800 and request.consent and options['expected_config'] == s.config
    assert not s.dialog.isVisible() and not s.dialog.consent.isChecked()
    assert len([call for call in s.calls if type(call) is tuple]) == 1


@pytest.mark.parametrize('blocker', ['labs', 'pro', 'models', 'unsupported', 'consent', 'microphone', 'output'])
def test_start_requires_every_review_and_consent_condition(make, blocker):
    config = pro_config()
    config['labs']['notetaker'] = blocker != 'labs'
    if blocker == 'pro':
        config['app']['tier'] = 'standard'
    def inspect(config):
        result = verified(config)
        return MeetingSetupInspection(result.plan, (False,) * len(result.installed)) if blocker == 'models' else result
    s = make(config=config, inspector=inspect, devices_provider=lambda: inventory(1 if blocker == 'unsupported' else 2))
    settle(lambda: not s.dialog._inflight)
    choose_devices(s)
    if blocker == 'microphone':
        s.dialog.microphone.setCurrentIndex(0)
    if blocker == 'output':
        s.dialog.output.setCurrentIndex(0)
    s.dialog.consent.setChecked(blocker != 'consent')
    assert not s.dialog.start_button.isEnabled() and s.dialog.start() is False and not s.calls


def test_controller_refusal_keeps_setup_open_and_requires_fresh_consent(make):
    calls = []
    s = make(start_callback=lambda *args, **kwargs: calls.append(args) or False)
    settle(lambda: not s.dialog._inflight)
    choose_devices(s)
    s.dialog.consent.setChecked(True)
    assert s.dialog.start() is False and s.dialog.isVisible() and not s.dialog.consent.isChecked()
    assert len(calls) == 1 and 'did not start' in s.dialog.status.text()


def test_stale_model_check_after_settings_change_is_replaced_before_start(make):
    entered, release = threading.Event(), threading.Event()
    snapshots = []
    def inspect(config):
        snapshots.append(copy.deepcopy(config))
        if len(snapshots) == 1:
            entered.set()
            assert release.wait(3)
        return verified(config)
    s = make(inspector=inspect)
    assert entered.wait(2)
    changed = copy.deepcopy(s.config)
    changed['stt']['pinned_languages'] = ['bn']
    try:
        s.dialog.set_config(changed)
        assert not s.dialog.start_button.isEnabled() and s.dialog.inspection is None
    finally:
        release.set()
    settle(lambda: len(snapshots) == 2 and not s.dialog._inflight)
    assert snapshots[-1] == changed and s.dialog.inspection.plan == meeting_setup_plan(changed)
    assert not s.calls


def test_hidden_device_results_cannot_admit_start_after_reopening(make):
    entered, release = threading.Event(), threading.Event()
    def devices():
        entered.set()
        assert release.wait(3)
        return inventory()
    s = make(devices_provider=devices)
    settle(lambda: not s.dialog._inflight)
    s.dialog.refresh.click()
    assert entered.wait(2)
    try:
        s.dialog.close()
        s.dialog.show()
    finally:
        release.set()
    settle(lambda: not s.dialog._inflight)
    assert s.dialog.devices is None and not s.dialog.start_button.isEnabled() and s.dialog.refresh.isEnabled()
    s.dialog.refresh.click()
    settle(lambda: not s.dialog._inflight)
    assert s.dialog.devices == inventory()


def test_download_completion_rechecks_hashes_and_never_starts_or_discovers(make):
    checks = []
    def inspect(config):
        checks.append(True)
        result = verified(config)
        return MeetingSetupInspection(result.plan, (len(checks) > 1,) * len(result.installed))
    s = make(inspector=inspect)
    settle(lambda: not s.dialog._inflight)
    assert not s.dialog.inspection.ready
    s.dialog.download_button.click()
    settle(lambda: s.dialog.task is None and not s.dialog._inflight)
    assert len(checks) == 2 and s.dialog.inspection.ready and s.calls == ['download']
    assert not s.dialog.start_button.isEnabled()


def test_pause_settles_worker_and_preserves_resume_explanation(make):
    entered = threading.Event()
    def download(plan, progress, *, pause_event):
        entered.set()
        assert pause_event.wait(3)
        from saydraft.models.downloader import DownloadPaused
        raise DownloadPaused('fixture paused')
    s = make(download_callback=download)
    settle(lambda: not s.dialog._inflight)
    s.dialog.download_button.click()
    assert entered.wait(2)
    s.dialog.pause_button.click()
    settle(lambda: s.dialog.task is None and not s.dialog._inflight)
    assert 'paused' in s.dialog.model_status.text() and s.dialog.download_button.isEnabled()
    assert not s.dialog.start_button.isEnabled() and not s.calls


def test_bad_ports_do_not_enable_start_or_download(make):
    s = make(inspector=lambda _: None, devices_provider=lambda: None)
    settle(lambda: not s.dialog._inflight)
    assert not s.dialog.download_button.isEnabled() and 'Could not verify' in s.dialog.model_status.text()
    s.dialog.refresh.click()
    settle(lambda: not s.dialog._inflight)
    assert s.dialog.devices is None and 'Could not list' in s.dialog.device_status.text()


def test_download_failure_stays_visible_after_reinspection_and_does_not_certify_models(make):
    def inspect(config):
        result = verified(config)
        return MeetingSetupInspection(result.plan, (False,) * len(result.installed))
    def download(*args, **kwargs):
        raise OSError('Fixture transfer interrupted')
    s = make(inspector=inspect, download_callback=download)
    settle(lambda: not s.dialog._inflight)
    s.dialog.download_button.click()
    settle(lambda: s.dialog.task is None and not s.dialog._inflight)
    assert s.dialog.model_status.text() and 'Review the complete' not in s.dialog.model_status.text()
    assert not s.dialog.inspection.ready and not s.dialog.start_button.isEnabled()


def test_settings_link_emits_labs_without_starting_anything(make):
    s = make()
    calls = []
    s.dialog.settings_requested.connect(calls.append)
    s.dialog.settings.click()
    assert calls == ['Labs'] and not s.calls
