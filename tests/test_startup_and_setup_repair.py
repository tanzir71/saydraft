from saydraft.config import default_config
from tests.test_session_worker import make_worker
from tests.test_settings_window import qt_modules


def test_startup_model_preparation_opens_no_microphone_and_rejects_early_speech():
    worker, _clock, executor, _events, signals, _keyboard = make_worker(queued=True)
    prepared = []
    worker.services.asr.prepare = lambda: prepared.append(True)
    assert worker.warm_recognition()
    assert worker.services.recorder.started == 0 and worker._speech_warming
    assert not worker.start_recording()
    executor.drain()
    assert prepared == [True] and worker.services.recorder.started == 0
    assert ("speech_model_status", "warming") in signals and (
        "speech_model_status",
        "ready",
    ) in signals
    assert worker.start_recording()
    executor.drain()
    assert worker.services.recorder.started == 1
    worker.cancel()
    executor.drain()
    worker.shutdown()


def test_ai_setup_is_optional_staged_and_cannot_finish_with_missing_enabled_files(
    tmp_path,
):
    qt_modules()
    from saydraft.ui.setup_cleanup import SetupCleanup

    config = default_config()
    widget = SetupCleanup(
        config, status_provider=lambda cfg, _model: not cfg["llm"]["enabled"]
    )
    assert widget.can_finish() and config["llm"]["enabled"] is False
    widget.enabled.setChecked(True)
    assert not widget.can_finish() and config["llm"]["enabled"] is False
    staged = default_config()
    widget.apply_to(staged)
    assert staged["llm"]["enabled"]
    widget.enabled.setChecked(False)
    assert widget.can_finish()
    widget.close()
    widget.deleteLater()


def test_tray_menu_has_legible_rows_without_a_checked_action_column(tmp_path):
    qt = qt_modules()
    from saydraft.ui.fonts import install_bundled_fonts
    from saydraft.ui.theme import install_theme
    from saydraft.ui.tray_menu import TrayMenu

    install_bundled_fonts(qt.QtWidgets.QApplication.instance())
    theme = install_theme(qt.QtWidgets.QApplication.instance(), mode="dark")
    menu = TrayMenu()
    actions = [
        menu.addAction(text)
        for text in (
            "Ready for shortcut",
            "Open Saydraft",
            "Pause listening",
            "History",
            "Settings",
        )
    ]
    actions[0].setEnabled(False)
    menu.show()
    qt.QtWidgets.QApplication.processEvents()
    assert menu.width() >= 240
    for action in actions:
        assert menu.actionGeometry(action).height() >= 32
        assert not action.isCheckable()
    assert menu.grab().save(str(tmp_path / "tray.png"))
    menu.close()
    menu.deleteLater()
    theme.close()


def test_onboarding_ai_choice_reaches_practice_and_finish_without_early_save(tmp_path):
    from pathlib import Path
    from tests.test_onboarding_window import fixture_wizard, write_config, finish_setup
    from saydraft.config import load_config

    qt_modules()
    path = write_config(tmp_path)
    before = path.read_bytes()
    model = tmp_path / "fixture.gguf"
    model.write_bytes(b"Public metadata fixture; not a real model")
    wizard = fixture_wizard(
        config_path=path,
        cleanup_status_provider=lambda cfg, _model: (
            not cfg["llm"]["enabled"] or Path(cfg["llm"]["model_path"]).is_file()
        ),
    )
    setup = wizard.models_page.cleanup_setup
    assert not setup.isHidden(), "The models step must expose optional AI setup"
    setup.enabled.setChecked(True)
    setup.path.setText(str(model))
    assert setup.can_finish() and wizard.practice_config()["llm"]["enabled"]
    assert wizard.practice_config()["llm"]["model_path"] == str(model)
    assert path.read_bytes() == before
    assert finish_setup(wizard)
    saved = load_config(config_path=path)
    assert saved["llm"]["enabled"] and saved["llm"]["model_path"] == str(model)
    wizard.close()
    wizard.deleteLater()


def test_expanding_onboarding_ai_setup_keeps_controls_and_speech_section_apart():
    qt = qt_modules()
    from saydraft.ui.gallery_catalog import Fixtures, Scene, capture

    fixtures = Fixtures()
    try:
        scene = Scene("setup", "models")
        wizard = fixtures.scene(scene)
        setup = wizard.models_page.cleanup_setup
        setup.enabled.setChecked(True)
        capture(wizard, scene)
        label = next(
            w
            for w in wizard.models_page.findChildren(qt.QtWidgets.QLabel)
            if w.text() == "Speech recognition"
        )
        assert setup.enabled.height() >= setup.enabled.minimumSizeHint().height()
        assert label.geometry().top() > setup.geometry().bottom()
        button = setup.picker.download_button
        assert button.height() >= button.minimumSizeHint().height()
        setup.enabled.setChecked(False)
        capture(wizard, scene)
        assert label.geometry().top() > setup.geometry().bottom()
        assert not setup.details.isVisible()
    finally:
        fixtures.close()
