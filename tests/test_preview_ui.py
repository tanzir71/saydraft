import threading
import time
from types import SimpleNamespace

from saydraft.config import default_config
from tests.test_pill_ui import qt_modules


def drain_until(qt, predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        qt.QtWidgets.QApplication.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_labs_shows_size_and_license_and_toggles_never_download():
    from saydraft.ui.labs_page import LabsPage

    qt_modules()
    config = default_config()
    calls = []
    page = LabsPage(config, callback=lambda *args: calls.append(True),
                    report_loader=lambda: {"assessment": {"tier": "pro"}})
    assert "463.9 MB" in page.license.text() and "NVIDIA Open Model License" in page.license.text()
    assert not page.live.isChecked() and not page.streaming.isChecked()
    page.live.setChecked(True)
    page.streaming.setChecked(True)
    page.apply_to(config)
    assert config["labs"] == {"live_preview": True, "use_streaming_result": True, "command_mode": False, "translate_mode": False} and not calls
    config["stt"]["pinned_languages"] = ["bn"]
    page.update_eligibility(config)
    assert not page.live.isEnabled() and not page.live.isChecked() and not page.download.isEnabled()
    assert not page.streaming.isChecked() and not calls


def test_missing_pro_measurement_disables_preview():
    from saydraft.ui.labs_page import LabsPage

    qt_modules()
    page = LabsPage(default_config(), report_loader=lambda: None)
    assert not page.live.isEnabled() and not page.download.isEnabled()
    assert "Performance" in page.eligibility.text()


def test_saving_other_settings_preserves_command_opt_in_and_its_independent_backend(tmp_path):
    from saydraft.config import load_config
    from tests.test_settings_window import make_window

    window, config_path, _ = make_window(tmp_path, overrides={
        'labs': {'command_mode': True}, 'command': {'backend': 'cpu'}})
    try:
        window.speech_hotkey_edit.setText('f8')
        assert window.apply_changes()
        saved = load_config(config_path=config_path)
        assert saved['labs']['command_mode'] is True
        assert saved['command']['backend'] == 'cpu'
        assert not saved['labs']['live_preview'] and not saved['labs']['use_streaming_result']
    finally:
        window.close()


def test_settings_persists_explicit_labs_choices_and_language_changes_disable_them(tmp_path):
    from saydraft.models.hardware import save_report
    from tests.test_settings_window import make_window

    qt_modules()
    window, config_path, _autostart = make_window(tmp_path)
    save_report({"schema_version": 1, "assessment": {"tier": "pro"}}, tmp_path / "hardware-benchmarks")
    window.refresh_labs()
    window.labs_page.live.setChecked(True)
    window.labs_page.streaming.setChecked(True)
    assert window.apply_changes() and window.config["labs"]["use_streaming_result"]
    window.language_combo.setCurrentIndex(window.language_combo.findData("bn"))
    assert not window.labs_page.live.isEnabled() and not window.labs_page.streaming.isChecked()
    assert window.apply_changes() and not window.config["labs"]["live_preview"]


def test_explicit_preview_download_runs_outside_gui_and_can_pause_resume():
    from saydraft.models.downloader import DownloadPaused
    from saydraft.ui.labs_page import LabsPage

    qt = qt_modules()
    started = threading.Event()
    threads = []

    def download(progress, *, pause_event):
        threads.append(threading.get_ident())
        progress(25)
        started.set()
        if len(threads) == 1:
            assert pause_event.wait(2)
            raise DownloadPaused("Paused; verified archive bytes are kept.")
        progress(100)
        return "verified-model"

    page = LabsPage(default_config(), callback=download, report_loader=lambda: {"assessment": {"tier": "pro"}})
    assert not threads
    page.start_download()
    assert started.wait(1) and not page.download.isEnabled()
    page.pause()
    drain_until(qt, lambda: page.task is None)
    assert "Paused" in page.status.text() and page.download.isEnabled()
    page.start_download()
    drain_until(qt, lambda: page.task is None)
    assert page.progress.value() == 100 and "ready" in page.status.text()
    assert len(threads) == 2 and all(ident != threading.get_ident() for ident in threads)
    assert not page.live.isChecked()  # A download never enables an experiment.


def test_preview_strip_keeps_last_sixty_characters_and_never_reopens_dismissed_bar():
    from saydraft.ui.pill import SaydraftPill

    qt_modules()
    pill = SaydraftPill()
    pill.show_recording()
    words = "<b>literal preview</b> " * 5
    pill.update_preview(words)
    assert pill.preview_label.text() == words[-60:] and pill.preview_label.isVisible()
    assert pill.preview_label.property("truncated") and pill.height() == 68
    pill.show_processing()
    pill.update_preview("late words")
    assert not pill.preview_label.isVisible() and pill.height() == 36
    pill.show_recording()
    assert not pill.preview_label.text()
    pill.hide()
    pill.update_preview("hidden words")
    assert not pill.isVisible() and not pill.preview_label.text()


def test_old_completion_timer_cannot_hide_a_new_recording_with_preview():
    from saydraft.ui.pill import SaydraftPill

    qt_modules()
    scheduled = []
    pill = SaydraftPill(timer_single_shot=lambda delay, callback: scheduled.append(callback))
    pill.show_not_inserted("focus_changed", saved=True)
    pill.show_recording()
    pill.update_preview("current recording")
    scheduled[0]()
    assert pill.isVisible() and pill.preview_label.text() == "current recording"
    pill.hide()


def test_queued_qt_partials_validate_generation_on_gui_delivery():
    from saydraft.app import SaydraftApp, create_worker_signals

    qt = qt_modules()
    app = SaydraftApp(qt_modules=qt)
    current = [5]
    calls = []
    app.controller = SimpleNamespace(is_current_preview=lambda generation, **kwargs: generation == current[0])
    app.pill = SimpleNamespace(update_preview=lambda text: calls.append((text, threading.get_ident())),
                               clear_preview=lambda: calls.append(("cleared", threading.get_ident())))
    app.tray = SimpleNamespace(show_notification=lambda text: None)
    signals = create_worker_signals(qt.QtCore)
    signals.preview_text_changed.connect(app._show_preview)
    signals.preview_unavailable.connect(app._preview_unavailable)
    thread = threading.Thread(target=lambda: signals.preview_text_changed.emit(5, "old words"))
    thread.start()
    thread.join()
    current[0] = 6
    qt.QtWidgets.QApplication.processEvents()
    assert not calls
    thread = threading.Thread(target=lambda: signals.preview_text_changed.emit(6, "current words"))
    thread.start()
    thread.join()
    assert not calls
    qt.QtWidgets.QApplication.processEvents()
    assert calls == [("current words", threading.get_ident())]
    signals.preview_unavailable.emit(5)
    assert len(calls) == 1
    signals.preview_unavailable.emit(6)
    assert calls[-1] == ("cleared", threading.get_ident())
