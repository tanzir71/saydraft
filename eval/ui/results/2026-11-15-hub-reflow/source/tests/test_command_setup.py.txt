"""Owned offscreen Command setup, fake transfers and no device discovery."""

import copy
import threading

from saydraft.config import default_config, load_config
from saydraft.models.command import command_bundle
from saydraft.models.cleanup import transfer_bytes
from saydraft.models.downloader import DownloadPaused
from saydraft.ui.command_setup import CommandSetup
from tests.test_preview_ui import drain_until
from tests.test_settings_window import make_window, qt_modules


def fixture(*, tier='pro', callback=None):
    qt_modules()
    config = default_config()
    config['app']['tier'] = tier
    return CommandSetup(config, callback=callback), config


def test_ask_is_an_independent_default_off_shared_model_opt_in_without_transfer():
    calls = []
    page, config = fixture(callback=lambda *args, **options: calls.append(True))
    before = copy.deepcopy(config)
    assert not page.ask_check.isChecked() and page.ask_check.isEnabled()
    page.ask_check.setChecked(True)
    assert config == before and not calls and page.task is None
    page.apply_to(config)
    assert config['labs']['ask_mode'] is True
    assert not config['labs']['command_mode'] and not config['labs']['translate_mode']
    assert config['llm'] == before['llm'] and config['stt'] == before['stt']
    assert not config['command']['clipboard_fallback']
    page.update_eligibility({**config, 'app': {**config['app'], 'tier': 'standard'}})
    assert page.ask_check.isEnabled()  # A saved opt-in can always be turned off.
    page.ask_check.setChecked(False)
    assert not page.ask_check.isEnabled() and not calls


def test_review_size_licenses_and_default_off_without_transfer_or_regular_cleanup_changes():
    calls = []
    page, config = fixture(callback=lambda *a, **kw: calls.append(True))
    before = copy.deepcopy(config)
    assert not page.enabled_check.isChecked() and page.enabled_check.isEnabled()
    package = command_bundle('cpu')
    assert f'{sum(transfer_bytes(m) for m in package) / 1e6:,.1f} MB' in page.license.text()
    assert 'Qwen3.5 4B' in page.license.text() and 'Apache-2.0' in page.license.text()
    page.enabled_check.setChecked(True)
    page.backend.setCurrentIndex(page.backend.findData('vulkan'))
    assert not calls and config == before
    page.apply_to(config)
    assert config['labs']['command_mode'] is True and config['command']['backend'] == 'vulkan'
    assert config['llm'] == before['llm'] and config['stt'] == before['stt']


def test_standard_shows_needs_pro_before_transfer_and_preserves_a_preexisting_opt_in():
    calls = []
    page, config = fixture(tier='standard', callback=lambda *a, **kw: calls.append(True))
    assert 'Needs Pro tier' in page.eligibility.text()
    assert not page.enabled_check.isEnabled() and not page.download_button.isEnabled()
    page.start_download()
    assert not calls and page.task is None
    page.enabled_check.setChecked(True)  # A saved preference from an earlier Pro profile.
    page.apply_to(config)
    assert config['labs']['command_mode'] is True


def test_clipboard_fallback_is_a_separate_staged_opt_in_with_windows_policy_disclosure():
    page, config = fixture()
    assert not page.copy_check.isChecked() and not page.copy_check.isEnabled()
    assert 'history and sync' in page.copy_description.text() and 'Ctrl+C' in page.copy_description.text()
    page.enabled_check.setChecked(True)
    assert page.copy_check.isEnabled()
    page.copy_check.setChecked(True)
    assert config['command']['clipboard_fallback'] is False
    page.apply_to(config)
    assert config['command']['clipboard_fallback'] is True
    page.enabled_check.setChecked(False)
    assert page.copy_check.isEnabled() and page.copy_check.isChecked()
    page.copy_check.setChecked(False)
    assert not page.copy_check.isEnabled()


def test_standard_disables_clipboard_fallback_even_with_saved_command_opt_in():
    page, _ = fixture(tier='standard')
    page.enabled_check.setChecked(True)
    assert not page.copy_check.isEnabled()


def test_translate_is_independent_staged_default_off_and_standard_is_gated():
    page, config = fixture()
    assert not page.translate_check.isChecked() and page.translate_check.isEnabled()
    page.translate_check.setChecked(True)
    assert not config['labs']['translate_mode'] and not page.enabled_check.isChecked()
    page.apply_to(config)
    assert config['labs']['translate_mode'] and not config['labs']['command_mode']
    standard, _ = fixture(tier='standard')
    assert not standard.translate_check.isEnabled()


def test_downgraded_profile_can_revoke_saved_opt_ins_without_enabling_or_downloading():
    page, config = fixture()
    for check in (page.enabled_check, page.translate_check, page.copy_check):
        check.setChecked(True)
    page.apply_to(config)
    config['app']['tier'] = 'standard'
    page.update_eligibility(config)
    assert not page.download_button.isEnabled()
    for check in (page.enabled_check, page.translate_check, page.copy_check):
        assert check.isChecked() and check.isEnabled()
        check.click()
        assert not check.isChecked() and not check.isEnabled()
        check.click()
        assert not check.isChecked()
    page.apply_to(config)
    assert not config['labs']['translate_mode'] and not config['labs']['command_mode']
    assert not config['command']['clipboard_fallback'] and page.task is None


def test_explicit_download_uses_captured_backend_off_gui_and_does_not_enable_or_apply(tmp_path):
    started, release = threading.Event(), threading.Event()
    calls = []
    output = tmp_path / 'fixture.gguf'
    output.write_bytes(b'authored fake verified weight')
    def download(backend, progress, *, pause_event):
        calls.append((backend, threading.get_ident(), pause_event))
        started.set()
        assert release.wait(3)
        progress(100)
        return output
    page, config = fixture(callback=download)
    page.backend.setCurrentIndex(page.backend.findData('vulkan'))
    page.start_download()
    assert started.wait(2) and not page.download_button.isEnabled() and not page.backend.isEnabled()
    page.start_download()
    release.set()
    drain_until(qt_modules(), lambda: page.task is None)
    assert len(calls) == 1 and calls[0][0] == 'vulkan' and calls[0][1] != threading.get_ident()
    assert page.progress.value() == 100 and 'verified' in page.status.text()
    assert not page.enabled_check.isChecked() and config['command']['backend'] == 'auto'


def test_explicit_pause_resume_keeps_choice_and_pause_is_available_during_transfer(tmp_path):
    started, calls = threading.Event(), []
    output = tmp_path / 'fixture.gguf'
    output.write_bytes(b'authored fixture')
    def download(backend, progress, *, pause_event):
        calls.append(backend)
        if len(calls) == 1:
            started.set()
            assert pause_event.wait(3)
            raise DownloadPaused('Paused; verified bytes stay available.')
        return output
    page, _ = fixture(callback=download)
    page.start_download()
    assert started.wait(2) and page.pause_button.isEnabled()
    page.pause()
    drain_until(qt_modules(), lambda: page.task is None)
    assert 'Paused' in page.status.text()
    page.start_download()
    drain_until(qt_modules(), lambda: page.task is None)
    assert calls == ['cpu', 'cpu'] and 'verified' in page.status.text() and not page.enabled_check.isChecked()


def test_settings_stages_the_new_opt_in_and_backend_only_on_save_and_validates_reserved_chord(tmp_path):
    window, path, _ = make_window(tmp_path, overrides={'app': {'tier': 'pro'}})
    try:
        page = window.labs_page.command
        assert page.enabled_check.isEnabled()
        page.enabled_check.setChecked(True)
        page.copy_check.setChecked(True)
        page.backend.setCurrentIndex(page.backend.findData('cpu'))
        assert load_config(config_path=path)['labs']['command_mode'] is False
        assert window.apply_changes()
        saved = load_config(config_path=path)
        assert saved['labs']['command_mode'] is True and saved['command']['backend'] == 'cpu'
        assert saved['command']['clipboard_fallback'] is True
        assert saved['llm']['enabled'] is False
        window.speech_hotkey_edit.setText('ctrl+win+alt')
        assert not window.apply_changes() and 'conflict' in window.status_label.text().lower()
        assert load_config(config_path=path)['hotkeys']['speech'] == 'ctrl+win'
    finally:
        window.close()


def test_settings_close_pauses_command_transfer_without_joining_download_thread(tmp_path):
    started = threading.Event()
    window, _, _ = make_window(tmp_path, overrides={'app': {'tier': 'pro'}})
    page = window.labs_page.command
    def download(backend, progress, *, pause_event):
        started.set()
        assert pause_event.wait(3)
        raise DownloadPaused('Paused')
    page.callback = download
    page.start_download()
    assert started.wait(2)
    window.close()
    assert page.task.pause_event.is_set()
    drain_until(qt_modules(), lambda: page.task is None)
