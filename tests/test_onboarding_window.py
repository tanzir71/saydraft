import json
import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def qt_modules():
    from PySide6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


def write_config(tmp_path, overrides=None):
    from saydraft.config import default_config, save_config

    cfg = default_config()
    if overrides:
        for section, values in overrides.items():
            cfg[section].update(values)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    return path


def test_onboarding_wizard_has_required_steps_and_explicit_microphone_controls(tmp_path):
    from saydraft.ui.onboarding import OnboardingWizard

    config_path = write_config(tmp_path)
    wizard = OnboardingWizard(qt_modules=qt_modules(), config_path=config_path, hotkey_hint="F9")

    titles = [wizard.page(page_id).title() for page_id in wizard.pageIds()]

    assert titles == ["Welcome", "Microphone", "Model", "Hotkey", "Done"]
    assert wizard.hotkey_hint_label.text() == "F9"

    assert wizard.microphone_page._future is None
    assert wizard.level_bar.value() == 0
    assert not wizard.microphone_page.test_button.isEnabled()
    assert not hasattr(wizard, "update_audio_level")


def test_onboarding_model_download_updates_progress_and_selected_model(tmp_path):
    from saydraft.ui.onboarding import OnboardingWizard

    calls = []

    def fake_download(model_size, progress):
        calls.append(model_size)
        progress(37)

    config_path = write_config(tmp_path)
    wizard = OnboardingWizard(
        qt_modules=qt_modules(),
        config_path=config_path,
        model_download_callback=fake_download,
    )
    wizard.model_combo.setCurrentText("small")

    wizard.download_selected_model()

    from PySide6 import QtTest, QtWidgets

    for _ in range(100):
        QtWidgets.QApplication.processEvents()
        if wizard.model_picker.task is None:
            break
        QtTest.QTest.qWait(10)

    assert calls == ["small"]
    assert wizard.model_progress.value() == 100
    assert "ready" in wizard.model_status_label.text().lower()


def test_onboarding_hotkey_page_marks_tutorial_text_received(tmp_path):
    from saydraft.ui.onboarding import OnboardingWizard

    config_path = write_config(tmp_path)
    wizard = OnboardingWizard(qt_modules=qt_modules(), config_path=config_path)

    wizard.hotkey_test_field.setPlainText("hello from dictation")

    assert "received" in wizard.hotkey_status_label.text().lower()


def test_onboarding_finish_sets_onboarded_and_applies_config(tmp_path):
    from saydraft.ui.onboarding import OnboardingWizard

    applied = []
    config_path = write_config(tmp_path, {"app": {"onboarded": False}})
    wizard = OnboardingWizard(
        qt_modules=qt_modules(),
        config_path=config_path,
        on_config_applied=applied.append,
    )
    wizard.model_combo.setCurrentText("small")

    assert wizard.finish_onboarding() is True

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["app"]["onboarded"] is True
    assert saved["stt"]["model_size"] == "small"
    assert saved["stt"]["engine"] == "whisper"
    assert applied[-1] == saved


@pytest.fixture
def input_setup(tmp_path, monkeypatch):
    import sys

    from saydraft.audio.devices import InputDevice, InputSelection
    from saydraft.ui.onboarding import OnboardingWizard

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Setup QA must not open or enumerate a real microphone")

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(
        InputStream=forbidden, query_devices=forbidden, query_hostapis=forbidden))
    qt = qt_modules()
    path = write_config(tmp_path)
    selection = InputSelection("Public USB microphone", "Windows WASAPI")
    devices = (InputDevice(4, selection),)
    scans, starts, stops, applied = [], [], [], []

    def discover():
        scans.append(True)
        return devices

    wizard = OnboardingWizard(config_path=path, microphone_devices_provider=discover,
        microphone_start_callback=lambda value: starts.append(value) or len(starts),
        microphone_stop_callback=lambda generation: stops.append(generation) or True,
        on_config_applied=applied.append)
    try:
        yield types.SimpleNamespace(wizard=wizard, page=wizard.microphone_page, path=path,
            selection=selection, scans=scans, starts=starts, stops=stops, applied=applied, qt=qt)
    finally:
        wizard.close()
        wizard.microphone_page.close()
        qt.QtWidgets.QApplication.processEvents()


def select_fixture_input(subject):
    from tests.test_microphone_ui import settle

    assert subject.page.refresh_devices()
    settle(subject.page)
    subject.page.device_combo.setCurrentIndex(1)
    assert subject.page.selection == subject.selection


def test_setup_input_is_explicit_and_staged_until_finish(input_setup):
    subject = input_setup
    before = subject.path.read_bytes()
    assert not subject.scans and not subject.starts and not subject.stops
    select_fixture_input(subject)
    assert subject.path.read_bytes() == before
    assert subject.page.toggle_test()
    assert subject.starts == [subject.selection]
    subject.page.accept_status(1, "listening")
    subject.page.accept_level(1, .15)
    assert subject.wizard.level_bar.value() == 60
    assert subject.wizard.finish_onboarding()
    assert subject.stops == [1]
    saved = json.loads(subject.path.read_text(encoding="utf-8"))
    assert saved["recording"]["input_device"] == subject.selection.name
    assert saved["recording"]["input_hostapi"] == subject.selection.hostapi
    assert not saved["recording"]["retain_audio"]
    assert subject.applied == [saved]
    subject.page.accept_level(1, .9)
    assert subject.wizard.level_bar.value() == 60  # A stopping test ignores late levels.
    subject.page.accept_status(1, "stopped")
    assert subject.wizard.level_bar.value() == 0


def test_cancel_stops_setup_input_and_preserves_configuration_bytes(input_setup):
    subject = input_setup
    before = subject.path.read_bytes()
    select_fixture_input(subject)
    subject.page.toggle_test()
    subject.wizard.reject()
    assert subject.stops == [1]
    assert subject.path.read_bytes() == before
    assert not subject.applied
    subject.page.accept_status(1, "stopped")
    subject.page.accept_status(1, "listening")
    subject.page.accept_level(1, .9)
    assert subject.wizard.level_bar.value() == 0


def test_leaving_microphone_step_stops_the_test_and_keeps_staged_choice(input_setup):
    subject = input_setup
    subject.wizard.show()
    subject.wizard.next()
    subject.qt.QtWidgets.QApplication.processEvents()
    assert subject.wizard.currentId() == subject.wizard.PAGE_MIC
    select_fixture_input(subject)
    subject.page.toggle_test()
    subject.wizard.next()
    subject.qt.QtWidgets.QApplication.processEvents()
    assert subject.stops == [1]
    subject.page.accept_status(1, "stopped")
    subject.wizard.back()
    subject.qt.QtWidgets.QApplication.processEvents()
    assert subject.page.selection == subject.selection
    assert not subject.page._test_generation
    assert len(subject.starts) == 1


def test_unchanged_setup_choices_preserve_newer_saved_model_and_microphone(input_setup):
    from saydraft.config import load_config, save_config
    from saydraft.asr.selection import select_model

    subject = input_setup
    latest = load_config(config_path=subject.path)
    select_model(latest, "whisper-small", manual=True)
    latest["recording"].update(input_device="Another public input", input_hostapi="MME",
        max_seconds=900, warning_seconds=840, retain_audio=True, audio_retention_days=14)
    latest["hotkeys"]["speech"] = "f8"
    latest["llm"]["timeout_ms"] = 500
    saved = save_config(latest, subject.path)
    assert subject.wizard.finish_onboarding()
    saved["app"]["onboarded"] = True
    assert load_config(config_path=subject.path) == saved


def test_setup_edits_merge_without_replacing_unrelated_saved_preferences(input_setup):
    from saydraft.config import load_config, save_config

    subject = input_setup
    select_fixture_input(subject)
    subject.wizard.model_combo.setCurrentText("small")
    latest = load_config(config_path=subject.path)
    latest["hotkeys"]["speech"] = "f8"
    latest["recording"].update(max_seconds=900, warning_seconds=840, audio_retention_days=7)
    save_config(latest, subject.path)
    assert subject.wizard.finish_onboarding()
    saved = load_config(config_path=subject.path)
    assert saved["hotkeys"]["speech"] == "f8"
    assert saved["recording"]["max_seconds"] == 900
    assert saved["recording"]["warning_seconds"] == 840
    assert saved["recording"]["audio_retention_days"] == 7
    assert saved["recording"]["input_device"] == subject.selection.name
    assert saved["stt"]["engine"] == "whisper" and saved["stt"]["model_size"] == "small"


def test_save_failure_keeps_setup_open_without_marking_onboarded(input_setup, monkeypatch):
    subject = input_setup
    before = subject.path.read_bytes()

    def fail(*_args):
        raise OSError("private fixture path")

    monkeypatch.setattr("saydraft.ui.onboarding.save_config", fail)
    subject.wizard.accept()
    assert subject.wizard.result() != subject.qt.QtWidgets.QDialog.Accepted
    assert subject.path.read_bytes() == before
    assert not subject.applied
    assert "Could not save" in subject.wizard.finish_status_label.text()
    assert "private fixture path" not in subject.wizard.finish_status_label.text()


@pytest.mark.parametrize("dismiss", ["reject", "close", "hide"])
def test_dismissing_setup_stops_input_without_waiting_or_saving(input_setup, dismiss):
    subject = input_setup
    before = subject.path.read_bytes()
    subject.wizard.show()
    subject.wizard.next()
    subject.qt.QtWidgets.QApplication.processEvents()
    subject.page.toggle_test()
    getattr(subject.wizard, dismiss)()
    subject.qt.QtWidgets.QApplication.processEvents()
    assert subject.stops == [1]
    assert subject.page._stopping
    assert subject.path.read_bytes() == before


def test_completed_setup_does_not_save_or_apply_twice(input_setup):
    from saydraft.config import load_config, save_config

    subject = input_setup
    select_fixture_input(subject)
    assert subject.wizard.finish_onboarding()
    latest = load_config(config_path=subject.path)
    latest["recording"].update(input_device="New public microphone", input_hostapi="MME")
    save_config(latest, subject.path)
    before = subject.path.read_bytes()
    assert subject.wizard.finish_onboarding()
    assert subject.path.read_bytes() == before
    assert len(subject.applied) == 1


def test_minimum_setup_keeps_navigation_visible_outside_the_scrolling_input_step(input_setup):
    subject = input_setup
    wizard, qt = subject.wizard, subject.qt
    wizard.resize(640, 440)
    wizard.show()
    wizard.next()
    qt.QtWidgets.QApplication.processEvents()
    for role in (qt.QtWidgets.QWizard.BackButton, qt.QtWidgets.QWizard.NextButton,
                 qt.QtWidgets.QWizard.CancelButton):
        button = wizard.button(role)
        rect = qt.QtCore.QRect(button.mapTo(wizard, qt.QtCore.QPoint()), button.size())
        assert button.isVisible() and wizard.rect().contains(rect)
        scroll = wizard.microphone_scroll
        assert not rect.intersects(qt.QtCore.QRect(scroll.mapTo(wizard, qt.QtCore.QPoint()), scroll.size()))


def test_setup_heading_remains_readable_with_pixel_sized_and_changed_app_fonts(input_setup):
    subject = input_setup
    wizard, qt = subject.wizard, subject.qt
    app = qt.QtWidgets.QApplication.instance()
    original = app.font()
    try:
        wizard.show()
        wizard.next()
        assert subject.page.toggle_test()
        for pixels in (16, 22):
            font = qt.QtGui.QFont(original)
            font.setPixelSize(pixels)
            app.setFont(font)
            for _ in range(5):
                app.processEvents()
            assert not wizard.title_timer.isActive()
            assert app.font().pixelSize() == pixels
            assert wizard.font().pixelSize() == pixels
            title = next(label for label in wizard.findChildren(qt.QtWidgets.QLabel)
                if label.isVisible() and label.text() == "Microphone")
            assert title.fontMetrics().height() >= wizard.fontMetrics().height()
            assert not subject.stops
    finally:
        app.setFont(original)
