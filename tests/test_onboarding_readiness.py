"""Real checksum fixtures, owned offscreen navigation, and cancellable Finish."""

import hashlib
import json
import threading
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtTest, QtWidgets

from saydraft.asr.model_ids import DEFAULT_MODEL, LANGUAGE_ID_MODEL
from saydraft.config import load_config, save_config
from saydraft.models.downloader import installation_ready
from saydraft.models.setup import inspect_speech_package
from saydraft.models.whisper_local import file_fingerprint
from saydraft.ui.onboarding import OnboardingWizard
from tests.test_onboarding_window import advance_to, finish_setup, qt_modules, write_config
from tests.test_setup_models import settle


@pytest.fixture
def subject(tmp_path, monkeypatch):
    import sounddevice
    from saydraft.hotkeys.llhook import LowLevelHooks

    qt_modules()

    def forbidden(*args, **kwargs):
        raise AssertionError('Readiness QA cannot access owner inputs, clipboard or real shortcuts')

    for name in ('InputStream', 'query_devices', 'query_hostapis'):
        monkeypatch.setattr(sounddevice, name, forbidden)
    monkeypatch.setattr(LowLevelHooks, 'start', forbidden)
    monkeypatch.setattr(QtWidgets.QApplication, 'clipboard', staticmethod(forbidden))
    payload = b'public checksum fixture, not native model weights'
    descriptors = {}

    def descriptor(name):
        return descriptors.setdefault(name, {'id': name, 'label': 'Public ' + name, 'revision': 'f' * 40,
            'files': [{'path': 'weights.bin', 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]})

    def bundle(name):
        return [descriptor(name), descriptor(LANGUAGE_ID_MODEL)] if name == DEFAULT_MODEL else [descriptor(name)]

    monkeypatch.setattr('saydraft.models.manifest.model_bundle', bundle)
    root = tmp_path / 'model-fixtures'

    def install(name):
        model = descriptor(name)
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'weights.bin').write_bytes(payload)
        (directory / '.verified.json').write_text(json.dumps({'revision': model['revision'], 'files': model['files']}), encoding='utf-8')
        return directory

    for name in (DEFAULT_MODEL, LANGUAGE_ID_MODEL):
        install(name)

    def finder(name, *, check_hashes):
        assert check_hashes is True
        directory = root / name
        return directory if installation_ready(descriptor(name), directory, check_hashes=True) else None

    checked, applied, downloads = [], [], []

    def inspect(name):
        checked.append((name, threading.get_ident()))
        return inspect_speech_package(name, finder=finder)

    path = write_config(tmp_path)
    wizard = OnboardingWizard(config_path=path, model_status_provider=inspect,
        model_download_callback=lambda name, progress: downloads.append(name),
        on_config_applied=lambda config: applied.append((config, threading.get_ident())))
    try:
        yield SimpleNamespace(wizard=wizard, page=wizard.models_page, path=path, root=root, payload=payload,
            install=install, inspect=inspect, checked=checked, applied=applied, downloads=downloads)
    finally:
        wizard.close()
        wizard.models_page.close()
        QtWidgets.QApplication.processEvents()


def show_model(s):
    s.wizard.show()
    advance_to(s.wizard, s.wizard.PAGE_MODEL)
    settle(s.page)


def test_next_requires_every_dependency_checksum_and_layout_updates_do_not_restart_checks(subject):
    s = subject
    assert not s.checked and not s.downloads
    (s.root / LANGUAGE_ID_MODEL / 'weights.bin').unlink()
    show_model(s)
    assert not s.page.isComplete() and not s.wizard.button(QtWidgets.QWizard.NextButton).isEnabled()
    s.wizard.next()
    assert s.wizard.currentId() == s.wizard.PAGE_MODEL and not s.downloads
    s.install(LANGUAGE_ID_MODEL)
    s.page.refresh_button.click()
    settle(s.page)
    assert s.page.isComplete() and s.wizard.button(QtWidgets.QWizard.NextButton).isEnabled()
    calls = len(s.checked)
    for _ in range(12):
        QtWidgets.QApplication.processEvents()
    assert len(s.checked) == calls and all(ident != threading.get_ident() for _, ident in s.checked)
    s.wizard.next()
    assert s.wizard.currentId() == s.wizard.PAGE_HOTKEY


def test_download_callback_success_cannot_unlock_missing_package(subject):
    s = subject
    (s.root / DEFAULT_MODEL / 'weights.bin').unlink()
    show_model(s)
    s.page.picker.start_download()
    from tests.test_model_picker import wait_finished
    wait_finished(s.page.picker)
    settle(s.page)
    assert s.downloads == [DEFAULT_MODEL] and not s.page.isComplete()
    s.wizard.next()
    assert s.wizard.currentId() == s.wizard.PAGE_MODEL


def test_finish_freshly_rechecks_deleted_or_corrupt_files_without_saving(subject):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    before = s.path.read_bytes()
    (s.root / DEFAULT_MODEL / 'weights.bin').write_bytes(b'corrupt public fixture')
    assert not finish_setup(s.wizard)
    assert s.path.read_bytes() == before and not s.applied and 'not ready' in s.wizard.finish_status_label.text()
    s.install(DEFAULT_MODEL)
    assert finish_setup(s.wizard)
    assert s.applied and s.applied[0][1] == threading.get_ident()


def test_direct_finish_cannot_bypass_missing_model_step(subject):
    s = subject
    (s.root / DEFAULT_MODEL / 'weights.bin').unlink()
    before = s.path.read_bytes()
    assert not finish_setup(s.wizard)
    assert s.path.read_bytes() == before and not s.applied


def block_finish(s):
    entered, release, emitted = threading.Event(), threading.Event(), threading.Event()
    original = s.page.inspect

    def inspect(model):
        entered.set()
        assert release.wait(4)
        return original(model)

    s.page.inspect = inspect
    s.page.checked.connect(lambda job, result: emitted.set() if job[1] == 'finish' else None, QtCore.Qt.DirectConnection)
    assert not s.wizard.finish_onboarding()
    assert entered.wait(1) and s.wizard._finish_generation
    return release, emitted


@pytest.mark.parametrize('dismiss', ['reject', 'close', 'hide', 'back'])
@pytest.mark.parametrize('phase', ['blocked', 'queued'])
def test_cancel_hide_or_navigation_revokes_even_an_already_queued_finish(subject, dismiss, phase):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    before = s.path.read_bytes()
    release, emitted = block_finish(s)
    try:
        if phase == 'queued':
            release.set()
            assert emitted.wait(1)
        getattr(s.wizard, dismiss)()
        assert not s.wizard._finish_generation and s.path.read_bytes() == before
        release.set()
        for _ in range(25):
            QtWidgets.QApplication.processEvents()
            QtTest.QTest.qWait(2)
        assert not s.wizard._completed and not s.applied and s.path.read_bytes() == before
    finally:
        release.set()


def test_finish_stays_responsive_and_merges_newer_unrelated_preferences(subject):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    s.wizard.style_page.tones['messages'].setCurrentIndex(s.wizard.style_page.tones['messages'].findData('formal'))
    release, _ = block_finish(s)
    try:
        fired = []
        QtCore.QTimer.singleShot(0, lambda: fired.append(True))
        QtWidgets.QApplication.processEvents()
        assert fired and not s.wizard.style_page.isComplete()
        assert 'model files' in s.wizard.finish_status_label.text()
        assert not s.wizard.button(QtWidgets.QWizard.FinishButton).isEnabled()
        latest = load_config(config_path=s.path)
        latest['recording']['max_seconds'] = 900
        latest['dictation']['styles'].setdefault('messages', {})['intensity'] = 4
        save_config(latest, s.path)
        release.set()
        assert finish_setup(s.wizard)
        saved = load_config(config_path=s.path)
        assert saved['recording']['max_seconds'] == 900
        assert saved['dictation']['styles']['messages'] == {'tone': 'formal', 'intensity': 4}
    finally:
        release.set()


def test_changed_model_during_finish_requires_a_new_explicit_check(subject):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    release, _ = block_finish(s)
    try:
        latest = load_config(config_path=s.path)
        latest['stt'].update(engine='whisper', model_size='small', routing_enabled=False)
        save_config(latest, s.path)
        before = s.path.read_bytes()
        release.set()
        assert not finish_setup(s.wizard)
        assert not s.applied and s.path.read_bytes() == before
        assert 'Speech settings changed' in s.wizard.finish_status_label.text()
    finally:
        release.set()


def test_finish_checks_latest_unchanged_saved_model_instead_of_old_picker(subject):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    latest = load_config(config_path=s.path)
    latest['stt'].update(engine='whisper', model_size='small', routing_enabled=False)
    save_config(latest, s.path)
    before = s.path.read_bytes()
    assert not finish_setup(s.wizard) and s.path.read_bytes() == before
    assert s.checked[-1][0] == 'whisper-small'
    s.install('whisper-small')
    assert finish_setup(s.wizard)
    assert load_config(config_path=s.path)['stt'] == latest['stt']


def test_local_file_receipt_requires_successful_loading_and_unchanged_files(subject):
    s = subject
    local = s.path.parent / 'public-custom-model'
    local.mkdir()
    (local / 'model.bin').write_bytes(b'public metadata fixture')
    (local / 'tokenizer.json').write_text('{}', encoding='utf-8')
    s.page.inspect = lambda model: {'state': 'local', 'missing': [], 'fingerprint': file_fingerprint(local, tokenizers=())}
    s.page.benchmark_callback = lambda *args, **kw: 7
    s.page.benchmark_cancel_callback = lambda gen: True
    s.page.picker.combo.setCurrentIndex(s.page.picker.combo.findData('whisper-base'))
    show_model(s)
    assert s.page.readiness_state == 'local' and not s.page.isComplete()
    original = file_fingerprint(local, tokenizers=())
    assert s.page.start_benchmark()
    report = {'assessment': {'tier': 'pending'}, 'measurements': {'asr_status': 'ok', 'asr_model': s.page.picker.model_id,
        'asr_seconds': .7, 'cleanup_status': 'not_available', 'local_model_fingerprint': original}}
    s.page.accept_benchmark_finished(7, {'state': 'complete', 'report': report})
    settle(s.page)
    assert s.page.readiness_state == 'compatible' and s.page.isComplete()
    assert 'not claimed' in s.page.readiness.text()
    (local / 'model.bin').write_bytes(b'changed public model fixture')
    s.page.refresh_button.click()
    settle(s.page)
    assert s.page.readiness_state == 'local' and not s.page.isComplete()
    assert not finish_setup(s.wizard) and not s.applied


def test_failed_finish_check_exposes_no_provider_details(subject):
    def fail(model):
        raise OSError('private fixture path')

    subject.page.inspect = fail
    before = subject.path.read_bytes()
    assert not finish_setup(subject.wizard)
    assert subject.path.read_bytes() == before and 'private fixture path' not in subject.wizard.finish_status_label.text()


def test_rejected_queue_is_fail_closed_and_a_fresh_check_can_retry(subject):
    s = subject
    show_model(s)
    advance_to(s.wizard, s.wizard.PAGE_STYLE)
    s.page._pool.shutdown(wait=False)

    class Rejected:
        def submit(self, callback):
            raise RuntimeError('private executor detail')

        def shutdown(self, **options):
            pass

    s.page._pool = Rejected()
    before = s.path.read_bytes()
    assert not finish_setup(s.wizard)
    assert s.path.read_bytes() == before and not s.applied
    assert 'private executor' not in s.wizard.finish_status_label.text()
    assert finish_setup(s.wizard)


def test_local_receipts_cannot_substitute_for_missing_parakeet_dependencies(subject):
    s = subject
    s.page.inspect = lambda model: {'state': 'local', 'missing': [], 'fingerprint': 'a' * 64}
    s.page._local_receipts[DEFAULT_MODEL] = 'a' * 64
    show_model(s)
    assert s.page.readiness_state == 'failed' and not s.page.isComplete()
    assert not finish_setup(s.wizard) and not s.applied


@pytest.mark.integration
@pytest.mark.offline
def test_real_hf_cached_whisper_benchmark_unlocks_next_and_rechecked_finish(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import sounddevice
    from saydraft.app import WorkerController, create_worker_signals
    from saydraft.asr.selection import create_asr
    from saydraft.models.benchmark import run_benchmark
    from saydraft.models.whisper_local import inspect_local
    from saydraft.privacy.netguard import NetworkGuard
    from tests.test_onboarding_practice import settle as wait_for
    from tests.test_session_worker import make_worker
    from tests.test_whisper_local import bind_native_cache, create_native_cache

    cache = create_native_cache(tmp_path, monkeypatch)
    bind_native_cache(monkeypatch, cache)
    qt_modules()
    from saydraft.hotkeys.llhook import LowLevelHooks

    def forbidden(*args, **kwargs):
        raise AssertionError('Native readiness smoke must use only bundled speech, never owner devices or clipboard')

    for name in ('InputStream', 'query_devices', 'query_hostapis'):
        monkeypatch.setattr(sounddevice, name, forbidden)
    monkeypatch.setattr(LowLevelHooks, 'start', forbidden)
    monkeypatch.setattr(QtWidgets.QApplication, 'clipboard', staticmethod(forbidden))
    monkeypatch.setattr('saydraft.models.benchmark.run_benchmark', lambda asr, **options:
        run_benchmark(asr, hardware_probe=lambda: {'schema_version': 1, 'ram_bytes': 16 * 1024**3,
            'cpu_features': {'avx2': True}, 'vulkan': [], 'cuda': []}, **options))
    path = write_config(tmp_path, {'stt': {'engine': 'whisper', 'model_size': cache.alias,
        'routing_enabled': False, 'local_files_only': True, 'language': 'en', 'silence_trim': False}})
    config = load_config(config_path=path)
    worker, _, executor, events, _, _ = make_worker()
    executor.shutdown()
    pool = ThreadPoolExecutor(max_workers=1)
    worker.executor = pool
    worker.services.config = config
    worker.services.asr = create_asr(config)
    signals = create_worker_signals(QtCore)
    controller = WorkerController(signals)
    controller.core = worker
    worker.emit_callback = controller._emit
    native_threads = []
    prepare = worker.services.asr.prepare
    worker.services.asr.prepare = lambda: (native_threads.append(threading.get_ident()), prepare())[1]
    wizard = OnboardingWizard(config_path=path, model_status_provider=lambda model:
        inspect_speech_package(model, finder=lambda *_a, **_k: None, local_resolver=inspect_local),
        model_benchmark_callback=controller.start_setup_benchmark,
        model_benchmark_cancel_callback=controller.cancel_setup_benchmark)
    page = wizard.models_page
    signals.setup_benchmark_progress.connect(page.accept_benchmark_progress, QtCore.Qt.QueuedConnection)
    signals.setup_benchmark_finished.connect(page.accept_benchmark_finished, QtCore.Qt.QueuedConnection)
    NetworkGuard.install()
    try:
        wizard.show()
        advance_to(wizard, wizard.PAGE_MODEL)
        wait_for(lambda: page._future is None and not page._pending, timeout=30)
        assert page.readiness_state == 'local' and not page.isComplete()
        wizard.next()
        assert wizard.currentId() == wizard.PAGE_MODEL
        assert page.start_benchmark()
        wait_for(lambda: not page.benchmark_active and page.readiness_state == 'compatible', timeout=120)
        assert page.isComplete() and page.benchmark_report['measurements']['local_model_fingerprint']
        assert native_threads and all(thread != threading.get_ident() for thread in native_threads)
        assert not events and worker.services.recorder.started == 0
        advance_to(wizard, wizard.PAGE_STYLE)
        assert finish_setup(wizard)
        saved = load_config(config_path=path)
        assert saved['app']['onboarded'] and saved['stt'] == config['stt']
    finally:
        worker.shutdown()
        pool.shutdown(wait=True)
        wizard.close()
        page.close()
        QtWidgets.QApplication.processEvents()
