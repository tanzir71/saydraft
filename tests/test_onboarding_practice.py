"""Only owned offscreen fields, private config, and fake practice callbacks."""

import copy
import os
import time
from types import SimpleNamespace

import pytest

from saydraft.config import load_config, save_config
from saydraft.core.practice import PracticeResult
from tests.test_onboarding_window import qt_modules, write_config, fixture_wizard, finish_setup, advance_to


def settle(predicate, timeout=3):
    app = qt_modules().QtWidgets.QApplication.instance()
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            return
        time.sleep(.002)
    raise AssertionError('Owned practice UI did not settle')


def show_practice(s):
    qt = qt_modules()
    assert qt.QtWidgets.QApplication.platformName() == 'offscreen'
    s.wizard.show()
    s.wizard.activateWindow()
    advance_to(s.wizard, s.wizard.PAGE_PRACTICE)
    settle(lambda: bool(s.opens) and bool(s.page._generation))


@pytest.fixture
def subject(tmp_path, monkeypatch):
    import sounddevice
    from saydraft.hotkeys.llhook import LowLevelHooks

    def forbidden(*args, **kwargs):
        raise AssertionError('UI QA must not install real hooks or touch microphones/clipboard')

    monkeypatch.setattr(LowLevelHooks, 'start', forbidden)
    for name in ('InputStream', 'query_devices', 'query_hostapis'):
        monkeypatch.setattr(sounddevice, name, forbidden)
    qt = qt_modules()
    opens, starts, stops, closes, applied = [], [], [], [], []

    def open_practice(config, window, valid, group):
        opens.append((copy.deepcopy(config), window, valid, group))
        return len(opens)

    path = write_config(tmp_path)
    wizard = fixture_wizard(config_path=path, practice_open_callback=open_practice,
        practice_start_callback=lambda gen: starts.append(gen) or len(starts),
        practice_stop_callback=lambda gen, cap=None, **kw: stops.append((gen, cap, kw)) or True,
        practice_close_callback=lambda gen: closes.append(gen) or True, on_config_applied=applied.append)
    try:
        yield SimpleNamespace(wizard=wizard, page=wizard.practice_page, path=path, opens=opens,
            starts=starts, stops=stops, closes=closes, applied=applied, qt=qt)
    finally:
        wizard.close()
        wizard.practice_page.close()
        qt.QtWidgets.QApplication.processEvents()


def start_fixture(s):
    show_practice(s)
    s.page.accept_status(1, 0, 'ready')
    assert s.page.toggle_recording()
    s.page.accept_status(1, 1, 'recording')


def test_six_step_setup_opens_only_a_private_target_until_record_is_requested(subject):
    s = subject
    before = s.path.read_bytes()
    assert not s.opens and not s.starts
    show_practice(s)
    assert s.opens[0][3] == 'messages' and s.opens[0][1] == int(s.wizard.winId())
    assert s.opens[0][2]() and not s.starts and not s.page.record_button.isEnabled()
    assert s.page.boxes['messages'].isReadOnly() and s.page.boxes['email'].isReadOnly()
    assert s.path.read_bytes() == before


def test_result_uses_only_the_owned_field_and_plain_text_changes(subject):
    s = subject
    start_fixture(s)
    s.page.accept_result(PracticeResult(1, 1, 'messages', 'um <hello> world', '<hello> world', 'disabled'))
    assert s.page.boxes['messages'].toPlainText() == '<hello> world'
    assert not s.page.boxes['email'].toPlainText()
    assert s.page.raw.toPlainText() == 'um <hello> world'
    assert s.page.cleaned.toPlainText() == '<hello> world'
    assert s.page.chip_layout.count() and 'Removed:' in s.page.chip_layout.itemAt(0).widget().text()
    s.page.accept_status(1, 1, 'idle')
    assert not s.page._capture and s.page.record_button.isEnabled()


def test_cancel_rejects_already_queued_results_and_levels(subject):
    s = subject
    start_fixture(s)
    assert s.page.cancel_recording()
    s.page.accept_result(PracticeResult(1, 1, 'messages', 'late private text', 'late text', 'disabled'))
    s.page.accept_level(1, 1, .8)
    assert not s.page.raw.toPlainText() and s.page.meter.value() == 0
    assert s.stops == [(1, 1, {'cancel': True})]


def test_switching_chat_email_retires_the_old_target_before_rearming_latest_choice(subject):
    s = subject
    start_fixture(s)
    first_permission = s.opens[0][2]
    s.page.tabs.setCurrentIndex(1)
    s.page.tabs.setCurrentIndex(0)
    s.page.tabs.setCurrentIndex(1)
    assert s.closes == [1] and not first_permission()
    s.page.accept_result(PracticeResult(1, 1, 'messages', 'old', 'old', 'disabled'))
    assert not s.page.results
    s.page.accept_status(1, 0, 'stopped')
    settle(lambda: len(s.opens) == 2)
    assert s.opens[1][3] == 'email' and s.opens[1][2]() and not first_permission()
    s.page.accept_status(1, 0, 'ready')
    assert not s.page._ready  # No stale generation may arm the replacement.


@pytest.mark.parametrize('action', ['hide', 'back', 'deactivate', 'cancel'])
def test_leaving_practice_revokes_before_a_late_result_and_preserves_config(subject, action):
    s = subject
    before = s.path.read_bytes()
    start_fixture(s)
    if action == 'hide':
        s.wizard.hide()
    elif action == 'back':
        s.wizard.back()
    elif action == 'deactivate':
        s.qt.QtWidgets.QApplication.sendEvent(s.wizard, s.qt.QtCore.QEvent(s.qt.QtCore.QEvent.WindowDeactivate))
    else:
        s.wizard.reject()
    assert not s.opens[0][2]() and s.closes == [1]
    s.page.accept_result(PracticeResult(1, 1, 'messages', 'late', 'late', 'disabled'))
    assert not s.page.results and s.path.read_bytes() == before


def test_finish_waits_for_observed_practice_retirement_and_style_save_merges_latest(subject):
    s = subject
    show_practice(s)
    before = s.path.read_bytes()
    s.wizard.next()
    assert s.wizard.currentPage() is s.wizard.style_page
    assert not s.wizard.style_page.isComplete() and not finish_setup(s.wizard)
    assert s.path.read_bytes() == before and s.closes == [1]
    s.page.accept_status(1, 0, 'stopped')
    assert s.wizard.style_page.isComplete()
    s.wizard.style_page.tones['messages'].setCurrentIndex(1)
    latest = load_config(config_path=s.path)
    latest['dictation']['styles'] = {'messages': {'tone': 'casual', 'intensity': 4},
        'email': {'tone': 'casual', 'intensity': 2}, 'docs': {'tone': 'formal', 'intensity': 1}}
    save_config(latest, s.path)
    assert finish_setup(s.wizard)
    saved = load_config(config_path=s.path)
    assert saved['dictation']['styles']['messages'] == {'tone': 'formal', 'intensity': 4}
    assert saved['dictation']['styles']['email'] == latest['dictation']['styles']['email']
    assert saved['dictation']['styles']['docs'] == latest['dictation']['styles']['docs']
    assert saved['llm'] == latest['llm'] and s.applied[-1] == saved


def test_unknown_cleanup_blocks_finish_and_requests_restart(subject):
    s = subject
    show_practice(s)
    s.page.accept_status(1, 0, 'cleanup_failed')
    before = s.path.read_bytes()
    assert not s.page.isComplete() and not finish_setup(s.wizard)
    assert 'restart' in s.page.status.text().lower() and s.path.read_bytes() == before
    s.page.accept_status(1, 0, 'closing_external')
    s.page.accept_status(1, 0, 'stopped')
    assert 'restart' in s.page.status.text().lower() and not s.page.isComplete()


def test_failed_preparation_never_enters_an_automatic_retry_loop(subject):
    s = subject
    show_practice(s)
    s.page.accept_status(1, 0, 'model_unavailable')
    s.page.accept_status(1, 0, 'closing')
    s.page.accept_status(1, 0, 'stopped')
    for _ in range(5):
        s.qt.QtWidgets.QApplication.processEvents()
    assert len(s.opens) == 1 and s.page.prepare_button.isEnabled()
    assert 'unavailable' in s.page.status.text()


def test_external_stop_or_settings_replacement_does_not_automatically_restart_practice(subject):
    s = subject
    show_practice(s)
    s.page.accept_status(1, 0, 'ready')
    s.page.accept_status(1, 0, 'closing')
    s.page.accept_status(1, 0, 'stopped')
    for _ in range(5):
        s.qt.QtWidgets.QApplication.processEvents()
    assert len(s.opens) == 1 and not s.opens[0][2]() and s.page.prepare_button.isEnabled()
    assert 'Prepare practice' in s.page.status.text()


def test_external_stop_wins_a_race_with_window_deactivation_and_requires_explicit_prepare(subject):
    s = subject
    show_practice(s)
    s.page.stop_session(reopen=True)
    s.page.accept_status(1, 0, 'closing_external')
    s.page.stop_session(reopen=True)  # A delayed GUI deactivation cannot undo external revocation.
    s.page.accept_status(1, 0, 'stopped')
    for _ in range(5):
        s.qt.QtWidgets.QApplication.processEvents()
    assert len(s.opens) == 1 and not s.page.prepare()
    assert 'Prepare practice' in s.page.status.text()
    s.wizard.hide()
    s.wizard.show()
    s.wizard.activateWindow()
    advance_to(s.wizard, s.wizard.PAGE_PRACTICE)
    # The offscreen platform can ignore a second activateWindow request.
    # Deliver the owned Qt activation explicitly; no native desktop is involved.
    with pytest.warns(DeprecationWarning, match='setActiveWindow'):
        s.qt.QtWidgets.QApplication.setActiveWindow(s.wizard)
    settle(lambda: s.page.isVisible() and s.wizard.isActiveWindow())
    for _ in range(5):
        s.qt.QtWidgets.QApplication.processEvents()
    assert len(s.opens) == 1
    assert s.page.prepare(explicit=True) and len(s.opens) == 2


def test_practice_uses_explicit_staged_choices_and_newer_untouched_preferences(subject):
    from saydraft.audio.devices import InputSelection
    s = subject
    latest = load_config(config_path=s.path)
    latest['recording'].update(input_device='New public mic', input_hostapi='MME')
    latest['dictation']['styles'] = {'messages': {'tone': 'formal', 'intensity': 2}}
    save_config(latest, s.path)
    s.wizard.shortcuts_page.primary.setText('ctrl+alt+f8')
    index = s.wizard.model_picker.combo.findData('whisper-small')
    assert index >= 0
    s.wizard.model_picker.combo.setCurrentIndex(index)
    draft = s.wizard.practice_config()
    assert draft['hotkeys']['speech'] == 'ctrl+alt+f8'
    assert draft['stt']['engine'] == 'whisper' and draft['stt']['model_size'] == 'small'
    assert draft['recording']['input_device'] == 'New public mic'
    assert draft['dictation']['styles'] == latest['dictation']['styles']
    s.wizard.microphone_page.set_selection(InputSelection('Staged public mic', 'MME'))
    assert s.wizard.practice_config()['recording']['input_device'] == 'Staged public mic'


def test_style_quick_pick_preserves_third_tone_and_uses_real_rules_preview(tmp_path):
    qt_modules()
    path = write_config(tmp_path, {'dictation': {'styles': {'messages': {'tone': 'very_casual', 'intensity': 4}}}})
    wizard = fixture_wizard(config_path=path)
    try:
        page = wizard.style_page
        assert page.tones['messages'].currentData() == 'very_casual'
        assert 'um' in page.before.toPlainText().casefold() and 'um' not in page.after.toPlainText().casefold()
        assert finish_setup(wizard)
        assert load_config(config_path=path)['dictation']['styles']['messages'] == {'tone': 'very_casual', 'intensity': 4}
    finally:
        wizard.close()


@pytest.mark.parametrize('engine_kind', ['fixture', pytest.param('parakeet', marks=[pytest.mark.integration, pytest.mark.offline])])
def test_synthetic_native_shortcut_runs_real_practice_cleanup_through_queued_ui(tmp_path, monkeypatch, engine_kind):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import numpy as np
    from saydraft.app import WorkerController, create_worker_signals
    from saydraft.dictation import DictationConfig, DictationPipeline
    from saydraft.hotkeys._win32_hooks import KeyboardPacket
    from saydraft.hotkeys.llhook import LowLevelHooks
    from tests.test_native_hooks import API
    from tests.test_session_worker import make_worker
    from saydraft.privacy.netguard import NetworkGuard

    audio = np.ones(16000, dtype=np.float32)
    engine = SimpleNamespace(prepare=lambda: None, transcribe=lambda audio: 'um hello world',
                             model_id='public-fixture', last_language='en')
    if engine_kind == 'parakeet':
        directory = os.environ.get('SAYDRAFT_TEST_PARAKEET_V3_MODEL')
        if not directory:
            pytest.skip('set the explicit verified Parakeet v3 directory for the bundled-audio practice smoke')
        import soundfile as sf
        from saydraft.asr.sherpa_parakeet import ParakeetConfig, ParakeetEngine
        audio, rate = sf.read('tests/fixtures/hello.wav', dtype='float32')
        assert rate == 16000
        engine = ParakeetEngine(ParakeetConfig(silence_trim=False), model_dir=directory)
        NetworkGuard.install()

    qt = qt_modules()
    api, owners, accessed, recorders = API(), [], [], []
    worker, clock, _, events, _, _ = make_worker()
    worker.executor.shutdown(wait=False)
    worker.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Owned-practice-integration')
    gui_thread = threading.get_ident()
    prepared_on, recognized_on = [], []
    original_prepare, original_transcribe = engine.prepare, engine.transcribe
    engine.prepare = lambda: (prepared_on.append(threading.get_ident()), original_prepare())[1]
    engine.transcribe = lambda audio: (recognized_on.append(threading.get_ident()), original_transcribe(audio))[1]
    signals = create_worker_signals(qt.QtCore)
    controller = WorkerController(signals)
    controller.core = worker
    observed = []

    def emit(name, *args):
        observed.append((name, args if name != 'practice_result' else ('result',)))
        controller._emit(name, *args)

    worker.emit_callback = emit
    worker.services.cleaner = DictationPipeline(DictationConfig())
    worker.services.context.capture = lambda: accessed.append('foreground')
    worker.practice.asr_factory = lambda cfg: engine
    worker.practice.clock = lambda: clock.now

    class Recorder:
        def __init__(self, config, on_level):
            self.stopped = False
            recorders.append(self)

        def start(self):
            pass

        def stop(self):
            self.stopped = True
            return audio.copy()

    def hooks(*args, **kwargs):
        owner = LowLevelHooks(*args, api_factory=lambda: api, clock=lambda: clock.now, **kwargs)
        owners.append(owner)
        return owner

    def forbidden(*args, **kwargs):
        raise AssertionError('Practice must not use the owner clipboard')

    monkeypatch.setattr(qt.QtWidgets.QApplication, 'clipboard', staticmethod(forbidden))
    worker.practice.recorder_factory = Recorder
    worker.practice.hooks_factory = hooks
    path = write_config(tmp_path)
    downloads, installed = [], [False]

    def download(model, progress, **kwargs):
        downloads.append(model)
        progress(40)
        installed[0] = True
        progress(100)

    wizard = fixture_wizard(config_path=path, practice_open_callback=controller.open_practice,
        practice_start_callback=controller.start_practice_recording,
        practice_stop_callback=controller.stop_practice_recording, practice_close_callback=controller.close_practice,
        model_download_callback=download,
        model_status_provider=lambda model: {'state': 'verified' if installed[0] else 'missing', 'missing': []})
    owned_window = int(wizard.winId())
    worker.practice.guard_factory = lambda window: lambda: window == owned_window
    page = wizard.practice_page
    for name, slot in (('practice_status', page.accept_status), ('practice_level', page.accept_level),
                       ('practice_result', page.accept_result)):
        getattr(signals, name).connect(slot, qt.QtCore.Qt.QueuedConnection)
    try:
        before = path.read_bytes()
        wizard.show()
        wizard.activateWindow()
        wizard.next()
        assert wizard.currentId() == wizard.PAGE_MIC
        wizard.next()
        assert wizard.currentId() == wizard.PAGE_MODEL and not downloads
        wizard.download_selected_model()
        settle(lambda: wizard.model_picker.task is None and wizard.models_page.readiness_state == 'verified')
        assert len(downloads) == 1 and wizard.model_picker.progress.value() == 100
        wizard.next()
        assert wizard.currentId() == wizard.PAGE_HOTKEY
        wizard.next()
        settle(lambda: bool(owners) and bool(page._generation))
        settle(lambda: page._ready, timeout=15 if engine_kind == 'parakeet' else 3)
        assert not worker.start_recording()
        clock.now = 1
        assert api.emit('keyboard', 0x100, KeyboardPacket(0xA2)) == 17
        assert api.emit('keyboard', 0x100, KeyboardPacket(0x5B)) == 1
        settle(lambda: bool(recorders) and page._capture > 0 and
            ('practice_status', (page._generation, page._capture, 'recording')) in observed)
        clock.now = 2
        assert api.emit('keyboard', 0x101, KeyboardPacket(0x5B)) == 1
        assert api.emit('keyboard', 0x101, KeyboardPacket(0xA2)) == 17
        try:
            settle(lambda: bool(page.results))
        except AssertionError:
            raise AssertionError((observed.copy(), page._generation, page._capture, page._closing, page._permit.is_set())) from None
        if engine_kind == 'parakeet':
            assert 'hello' in page.raw.toPlainText().casefold() and engine._recognizer is not None
        else:
            assert page.raw.toPlainText() == 'um hello world'
            assert 'um' not in page.boxes['messages'].toPlainText().casefold()
        assert recorders[0].stopped and not accessed and not events and path.read_bytes() == before
        assert prepared_on and recognized_on
        assert all(value not in (gui_thread, api.thread_id) for value in prepared_on + recognized_on)
        wizard.next()
        settle(lambda: wizard.style_page.isComplete() and not worker.busy)
        assert api.closed and not worker.busy
        assert wizard.style_page.before.toPlainText() == page.raw.toPlainText()
        assert finish_setup(wizard)
    finally:
        wizard.close()
        worker.shutdown()
        if engine_kind == 'parakeet':
            NetworkGuard.uninstall()
