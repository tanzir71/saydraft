import threading
import time
from types import SimpleNamespace as NS

from PySide6 import QtCore, QtGui, QtWidgets
import pytest
from shiboken6 import isValid

from saydraft.config import load_config
from saydraft.models.downloader import DownloadPaused
from saydraft.ui.download_task import DownloadTask
from tests.test_settings_window import make_window, qt_modules


@pytest.fixture
def subject(tmp_path):
    qt = qt_modules()
    window, path, _ = make_window(tmp_path)
    controls = window.microphone_page.whisper_controls
    controls.ready_provider = lambda: False
    try:
        yield window, path, controls, qt.QtWidgets.QApplication.instance()
    finally:
        if isValid(window):
            window.close()
            window.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def settle(app, controls, timeout=3):
    deadline = time.monotonic() + timeout
    while controls.task is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.002)
    assert controls.task is None


def test_default_off_controls_stage_gain_and_agc_without_download_device_or_saved_changes(subject):
    window, path, controls, _app = subject
    calls = []
    controls.callback = lambda *args, **kwargs: calls.append('download')
    before = path.read_bytes()
    assert not controls.enabled.isChecked() and not controls.gain.isEnabled()
    controls.enabled.setChecked(True)
    controls.gain.setValue(18)
    controls.agc.setChecked(False)
    controls.enhancement.setChecked(False)
    assert path.read_bytes() == before and not calls
    assert window.apply_changes()
    recorded = load_config(config_path=path)['recording']
    assert recorded['whisper_mode'] and recorded['whisper_gain_db'] == 18
    assert not recorded['whisper_agc'] and not recorded['whisper_enhancement']
    assert recorded['input_device'] == '' and not recorded['retain_audio']
    assert not calls


def test_enhancement_requires_verified_files_before_any_shared_save(subject):
    window, path, controls, _app = subject
    before = path.read_bytes()
    glossary = window.glossary_path.read_bytes()
    controls.enabled.setChecked(True)
    controls.gain.setValue(15)
    assert controls.enhancement.isChecked()
    assert not window.apply_changes()
    assert 'Set up enhancement in Microphone' in window.status_label.text()
    assert path.read_bytes() == before and window.glossary_path.read_bytes() == glossary
    controls.ready_provider = lambda: True
    assert window.apply_changes()
    assert load_config(config_path=path)['recording']['whisper_mode']


def test_download_is_explicit_and_complete_callback_alone_cannot_claim_model_verification(subject):
    _window, path, controls, app = subject
    calls = []
    before = path.read_bytes()
    def callback(progress, *, pause_event):
        calls.append(threading.get_ident())
        assert not pause_event.is_set()
        progress(100)
        return 'unverified-model-directory'
    controls.callback = callback
    controls.enabled.setChecked(True)
    assert not calls
    gui = threading.get_ident()
    controls.download.click()
    settle(app, controls)
    assert len(calls) == 1 and calls[0] != gui
    assert 'incomplete or changed' in controls.status.text()
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='Set up enhancement in Microphone'):
        controls.validate()


def test_verified_download_never_saves_or_enables_mode(subject):
    _window, path, controls, app = subject
    state = {'ready': False}
    before = path.read_bytes()
    controls.ready_provider = lambda: state['ready']
    def callback(progress, *, pause_event):
        state['ready'] = True
        progress(100)
        return 'verified-model-directory'
    controls.callback = callback
    controls.start_download()
    settle(app, controls)
    assert 'files verified' in controls.status.text()
    assert not controls.enabled.isChecked() and path.read_bytes() == before


def test_pause_settles_the_worker_and_resume_reuses_explicit_setup(subject):
    _window, path, controls, app = subject
    entered = threading.Event()
    before = path.read_bytes()
    def callback(progress, *, pause_event):
        entered.set()
        assert pause_event.wait(2), 'Test failed to request pause'
        raise DownloadPaused('Enhancement download paused; resume to continue.')
    controls.callback = callback
    controls.start_download()
    assert entered.wait(1)
    controls.pause()
    settle(app, controls)
    assert 'paused' in controls.status.text() and path.read_bytes() == before
    assert controls.download.isEnabled() and not controls.pause_button.isEnabled()


def test_parent_destruction_pauses_download_and_late_results_do_not_touch_deleted_widgets(subject):
    window, _path, controls, app = subject
    entered = threading.Event()
    def callback(progress, *, pause_event):
        entered.set()
        assert pause_event.wait(2)
        raise DownloadPaused('paused')
    controls.callback = callback
    controls.start_download()
    task = controls.task
    assert entered.wait(1)
    window.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    deadline = time.monotonic() + 3
    while task in DownloadTask._active and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.002)
    assert task not in DownloadTask._active


def test_license_and_reviewed_size_are_visible_without_audio_or_model_loading(subject):
    _window, _path, controls, _app = subject
    labels = '\n'.join(label.text() for label in controls.findChildren(QtWidgets.QLabel))
    assert '0.54 MB' in labels and 'MIT license' in labels and 'Model source' in labels
    assert 'Accuracy for whispered speech still needs evaluation' in labels


def test_quiet_mode_keeps_saved_streaming_preference_but_makes_processed_primary_final(subject):
    from saydraft.core.preview import streaming_result_enabled
    window, _path, controls, _app = subject
    tier = window.tier_combo
    tier.setCurrentIndex(tier.findData('pro'))
    window.refresh_labs()
    window.labs_page.live.setChecked(True)
    window.labs_page.streaming.setChecked(True)
    controls.enabled.setChecked(True)
    controls.enhancement.setChecked(False)
    assert window.labs_page.streaming.isChecked() and not window.labs_page.streaming.isEnabled()
    assert 'off in Whisper mode' in window.labs_page.streaming.text()
    config = window._collect_config()
    assert config['labs']['use_streaming_result'] and not streaming_result_enabled(config)
    controls.enabled.setChecked(False)
    assert window.labs_page.streaming.isChecked() and window.labs_page.streaming.isEnabled()
    assert streaming_result_enabled(window._collect_config())


def test_long_setup_feedback_fits_the_real_hub_footer_at_minimum_size_with_large_text(subject):
    from saydraft.history import DictationHistoryStore
    from saydraft.ui.hub import HubWindow
    window, path, _controls, app = subject
    original = QtGui.QFont(app.font())
    large = QtGui.QFont(original)
    large.setPixelSize(22)
    app.setFont(large)
    store = DictationHistoryStore(path.parent / 'footer-history.db')
    hub = HubWindow(settings_options={}, settings_page_factory=lambda **kwargs: window,
        history_options={'store': store, 'clipboard': NS(setText=lambda text: None)})
    try:
        hub.resize(880, 600)
        hub.show_page('Settings', tab='Microphone')
        hub.show()
        window.status_label.setText('An enhancement file changed. Open Microphone to review setup, then download '
            'it again or turn enhancement off before saving.')
        for _ in range(3):
            app.processEvents()  # Nested layouts post their next layout request.
        label = window.status_label
        assert label.height() >= label.heightForWidth(label.width())
        bottom = label.mapTo(hub, QtCore.QPoint()).y() + label.height()
        assert bottom <= hub.height() - 10
        assert hub.size() == QtCore.QSize(880, 600)
    finally:
        hub.close()
        hub.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.setFont(original)
