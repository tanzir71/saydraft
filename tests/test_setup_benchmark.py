"""Selected-model measurements with public audio, fake input and private profiles."""

import copy
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
import threading
import os
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtWidgets

from saydraft.asr.model_ids import DEFAULT_MODEL
from saydraft.config import default_config, load_config, save_config
from saydraft.models.benchmark import run_benchmark
from saydraft.models.hardware import latest_report, save_report
from saydraft.models.setup import setup_model_id
from saydraft.ui.onboarding import OnboardingWizard
from tests.test_hardware_benchmark import make_asr
from tests.test_onboarding_window import qt_modules, write_config, finish_setup
from tests.test_setup_models import settle
from tests.test_session_worker import make_worker


HARDWARE = {'schema_version': 1, 'ram_bytes': 16 * 1024**3,
    'cpu_features': {'avx2': True}, 'vulkan': [], 'cuda': []}


def isolate_measurement(monkeypatch, *, clock=None):
    def measure(asr, **options):
        if clock is not None:
            options['clock'] = clock
        return run_benchmark(asr, hardware_probe=lambda: copy.deepcopy(HARDWARE), **options)

    monkeypatch.setattr('saydraft.models.benchmark.run_benchmark', measure)


@pytest.mark.parametrize('phase', ['hardware', 'preparing', 'warmup', 'speech_1', 'speech_3', 'cleanup', 'saving'])
def test_cancellation_at_every_phase_keeps_previous_reports_and_no_partial_result(tmp_path, phase):
    old = {'schema_version': 1, 'assessment': {'tier': 'standard'}}
    save_report(old, tmp_path)
    asr, clock, seen = make_asr()
    stopped = threading.Event()
    phases = []

    def progress(current):
        phases.append(current)
        if current == phase:
            stopped.set()

    with pytest.raises(CancelledError):
        run_benchmark(asr, directory=tmp_path, clock=lambda: clock.now,
            hardware_probe=lambda: copy.deepcopy(HARDWARE), cleanup_benchmark=lambda: [],
            cancelled=stopped.is_set, progress=progress)
    assert phases[-1] == phase and latest_report(tmp_path) == old
    assert len(list(tmp_path.glob('*.json'))) == 1
    if phase in ('hardware', 'preparing', 'warmup'):
        assert not seen


@pytest.mark.parametrize('elapsed', [0, -1, float('inf'), float('nan')])
def test_invalid_speech_measurements_do_not_qualify_a_tier(tmp_path, elapsed):
    asr, _, _ = make_asr()
    readings = iter([0, 0, 0, elapsed])
    report = run_benchmark(asr, directory=tmp_path, clock=lambda: next(readings),
        hardware_probe=lambda: copy.deepcopy(HARDWARE))
    assert report['measurements']['asr_status'] == 'failed'
    assert report['measurements']['asr_seconds'] is None
    assert report['assessment']['tier'] == 'pending'


@pytest.mark.parametrize('pins,english,override,expected', [
    ([], False, [], DEFAULT_MODEL),
    (['bn'], False, [], 'whisper-large-v3-turbo'),
    (['ar'], False, [], 'whisper-large-v3-turbo'),
    (['en'], True, [], 'parakeet-tdt-0-6b-v2-int8'),
    ([], False, [{'app_group': 'general', 'model_id': 'whisper-small'}], 'whisper-small'),
])
def test_setup_model_matches_the_actual_general_route_without_changing_pins(pins, english, override, expected):
    config = default_config()
    config['stt'].update(routing_enabled=True, pinned_languages=pins, english_max=english, app_model_overrides=override)
    before = copy.deepcopy(config)
    assert setup_model_id(config) == expected and config == before


def test_serial_worker_measures_staged_model_offline_without_recording_or_saving_preferences(tmp_path, monkeypatch):
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    asr, clock, seen = make_asr()
    asr.model_id = 'whisper-small'
    configs = []
    worker._practice_asr = lambda config: configs.append(copy.deepcopy(config)) or asr
    isolate_measurement(monkeypatch, clock=lambda: clock.now)
    config = copy.deepcopy(worker.services.config)
    config['stt'].update(engine='whisper', model_size='small', local_files_only=False, routing_enabled=False)
    before = copy.deepcopy(config)
    generation = worker.start_setup_benchmark(config, directory=tmp_path)
    assert generation == 1 and worker.busy and not worker.start_recording()
    assert not worker.start_setup_benchmark(config, directory=tmp_path)
    config['stt']['model_size'] = 'medium'
    executor.drain()
    assert configs[0]['stt'] == dict(before['stt'], local_files_only=True)
    report = latest_report(tmp_path)
    assert report['source'] == 'onboarding' and report['measurements']['asr_model'] == 'whisper-small'
    assert report['measurements']['asr_seconds'] == .5 and report['assessment']['tier'] == 'pending'
    assert report['measurements']['cleanup_status'] == 'not_available' and len(seen) == 4
    assert not worker.busy and not events and worker.services.config != config
    assert worker.services.recorder.started == worker.services.recorder.stopped == 0
    assert ('setup_benchmark_finished', 1, {'state': 'complete', 'report': report}) in signals


def test_cancel_before_queue_runs_does_not_create_an_engine_or_report(tmp_path, monkeypatch):
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    worker._practice_asr = lambda config: pytest.fail('cancelled queued work must not load a model')
    generation = worker.start_setup_benchmark(worker.services.config, directory=tmp_path)
    assert not worker.cancel_setup_benchmark(generation + 1)
    assert worker.cancel_setup_benchmark(generation) and worker.busy
    executor.drain()
    assert not worker.busy and not list(tmp_path.iterdir()) and not events
    assert ('setup_benchmark_finished', generation, {'state': 'cancelled', 'report': None}) in signals


@pytest.mark.parametrize('cancel_with', ['cancel', 'settings', 'shutdown'])
def test_blocked_native_work_retires_before_the_worker_reservation_is_released(tmp_path, monkeypatch, cancel_with):
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    executor.shutdown()
    pool = ThreadPoolExecutor(max_workers=1)
    worker.executor = pool
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    asr, clock, seen = make_asr()

    def prepare():
        started.set()
        assert release.wait(4)
        clock.now += 3

    asr.prepare = prepare
    worker._practice_asr = lambda cfg: asr
    isolate_measurement(monkeypatch, clock=lambda: clock.now)
    worker.services_factory = lambda cfg, **opts: replace(worker.services, config=cfg)
    worker.emit_callback = lambda *args: (signals.append(args), finished.set() if args[0] == 'setup_benchmark_finished' else None)
    try:
        generation = worker.start_setup_benchmark(worker.services.config, directory=tmp_path)
        assert generation and started.wait(2)
        if cancel_with == 'cancel':
            worker.cancel()
        elif cancel_with == 'settings':
            new_config = copy.deepcopy(worker.services.config)
            new_config['app']['tier'] = 'lite'
            worker.configure(new_config)
            assert worker._pending_config is new_config
        else:
            worker.shutdown()
        assert worker.busy and not finished.is_set() and not seen
        assert not worker.start_microphone_test(None) and not worker.start_recording()
        release.set()
        assert finished.wait(2)
    finally:
        release.set()
        pool.shutdown(wait=True)
    assert not worker.busy and not seen and not events and not list(tmp_path.iterdir())
    assert ('setup_benchmark_finished', generation, {'state': 'cancelled', 'report': None}) in signals
    if cancel_with == 'settings':
        assert worker.services.config == new_config and worker._pending_config is None


def test_missing_staged_model_preserves_previous_successful_tier_report(tmp_path, monkeypatch):
    worker, _, executor, _, signals, _ = make_worker(queued=True)
    old = {'schema_version': 1, 'assessment': {'tier': 'standard'}}
    save_report(old, tmp_path)
    worker._practice_asr = lambda cfg: SimpleNamespace(model_id='whisper-small',
        prepare=lambda: (_ for _ in ()).throw(FileNotFoundError('fixture missing')))
    isolate_measurement(monkeypatch)
    worker.start_setup_benchmark(worker.services.config, directory=tmp_path)
    executor.drain()
    assert latest_report(tmp_path) == old and len(list(tmp_path.glob('*.json'))) == 1
    assert [row for row in signals if row[0] == 'setup_benchmark_finished'][0][2]['state'] == 'model_missing'


def test_queue_rejection_releases_setup_owner(tmp_path):
    worker, _, executor, _, _, _ = make_worker()
    executor.submit = lambda *args: (_ for _ in ()).throw(RuntimeError('queue closed'))
    assert not worker.start_setup_benchmark(worker.services.config, directory=tmp_path)
    assert not worker.busy and worker._setup_benchmark is None and not worker._benchmarking


@pytest.mark.parametrize('current', [None, True, False])
def test_changed_cached_files_require_a_fresh_engine_before_benchmark_validation(tmp_path, monkeypatch, current):
    worker, _, executor, _, _, _ = make_worker(queued=True)
    asr, clock, seen = make_asr()
    asr.local_model_files_current = lambda: current
    worker._practice_asr = lambda cfg: asr
    replacements = []
    fresh = SimpleNamespace(model_id=asr.model_id, prepare=asr.prepare, transcribe=asr.transcribe)
    monkeypatch.setattr('saydraft.asr.selection.create_asr', lambda cfg: replacements.append(cfg) or fresh)
    isolate_measurement(monkeypatch, clock=lambda: clock.now)
    assert worker.start_setup_benchmark(worker.services.config, directory=tmp_path)
    executor.drain()
    assert len(replacements) == (1 if current is False else 0)
    assert len(seen) == 4 and latest_report(tmp_path)['measurements']['asr_status'] == 'ok'
    if replacements:
        assert replacements[0]['stt']['local_files_only'] is True


@pytest.fixture
def ui(tmp_path, monkeypatch):
    import sounddevice
    from saydraft.hotkeys.llhook import LowLevelHooks

    qt = qt_modules()

    def forbidden(*args, **kwargs):
        raise AssertionError('Setup speed QA must not touch devices, clipboard or real hooks')

    for name in ('InputStream', 'query_devices', 'query_hostapis'):
        monkeypatch.setattr(sounddevice, name, forbidden)
    monkeypatch.setattr(LowLevelHooks, 'start', forbidden)
    monkeypatch.setattr(QtWidgets.QApplication, 'clipboard', staticmethod(forbidden))
    starts, stops = [], []
    path = write_config(tmp_path)
    wizard = OnboardingWizard(config_path=path,
        model_status_provider=lambda model: {'state': 'verified', 'missing': []},
        model_benchmark_callback=lambda config, **kw: starts.append((copy.deepcopy(config), kw)) or len(starts),
        model_benchmark_cancel_callback=lambda gen: stops.append(gen) or True)
    try:
        wizard.show()
        wizard.next()
        wizard.next()
        settle(wizard.models_page)
        yield SimpleNamespace(wizard=wizard, page=wizard.models_page, path=path, starts=starts, stops=stops, qt=qt)
    finally:
        wizard.close()
        wizard.models_page.close()
        QtWidgets.QApplication.processEvents()


def result_for(page):
    return {'state': 'complete', 'report': {'schema_version': 1, 'assessment': {'tier': 'pending'},
        'measurements': {'asr_status': 'ok', 'asr_seconds': .6, 'asr_model': page.picker.model_id,
            'cleanup_status': 'not_available', 'llm_08_tps': None, 'llm_2_tps': None}}}


def test_setup_check_is_explicit_staged_and_keeps_preferences_unchanged(ui):
    s = ui
    before = s.path.read_bytes()
    assert not s.starts
    s.page.picker.combo.setCurrentIndex(s.page.picker.combo.findData('whisper-small'))
    settle(s.page)
    assert s.page.start_benchmark()
    assert s.starts[0][0]['stt']['model_size'] == 'small' and not s.starts[0][0]['stt']['routing_enabled']
    assert s.starts[0][1]['directory'] == s.path.parent / 'hardware-benchmarks'
    assert not s.page.picker.isEnabled() and not s.page.benchmark_button.isEnabled()
    initial_status = s.page.benchmark_status.text()
    s.page.accept_benchmark_progress(99, 'speech_1')
    assert s.page.benchmark_status.text() == initial_status
    s.page.accept_benchmark_progress(1, 'speech_2')
    assert 'sample 2 of 3' in s.page.benchmark_status.text()
    s.page.accept_benchmark_finished(1, result_for(s.page))
    assert not s.page.benchmark_active and s.page.benchmark_button.isEnabled()
    assert 'unmeasured' in s.page.benchmark_details.text() and 'pending' in s.page.benchmark_status.text()
    assert s.path.read_bytes() == before and not load_config(config_path=s.path)['app']['onboarded']


@pytest.mark.parametrize('stop_with', ['button', 'hide', 'selection', 'finish'])
def test_stopped_or_stale_ui_results_cannot_publish_and_finish_waits(ui, stop_with):
    s = ui
    before = s.path.read_bytes()
    assert s.page.start_benchmark()
    result = result_for(s.page)
    if stop_with == 'button':
        s.page.stop_benchmark_button.click()
    elif stop_with == 'hide':
        s.page.hide()
    elif stop_with == 'selection':
        s.page.picker.combo.setCurrentIndex(s.page.picker.combo.findData('whisper-small'))
    else:
        assert not s.wizard.finish_onboarding()
    assert s.stops and s.page.benchmark_active
    s.page.accept_benchmark_progress(1, 'speech_3')
    s.page.accept_benchmark_finished(999, result)
    assert s.page.benchmark_active
    s.page.accept_benchmark_finished(1, result)
    assert not s.page.benchmark_active and s.page.benchmark_report is None
    assert not s.page.benchmark_details.text() and s.path.read_bytes() == before


def test_queued_worker_signals_deliver_only_to_the_current_setup_check(ui):
    from saydraft.app import create_worker_signals

    signals = create_worker_signals(QtCore)
    page = ui.page
    signals.setup_benchmark_progress.connect(page.accept_benchmark_progress, QtCore.Qt.QueuedConnection)
    signals.setup_benchmark_finished.connect(page.accept_benchmark_finished, QtCore.Qt.QueuedConnection)
    assert page.start_benchmark()
    signals.setup_benchmark_progress.emit(1, 'speech_1')
    assert 'sample 1' not in page.benchmark_status.text()
    QtWidgets.QApplication.processEvents()
    assert 'sample 1' in page.benchmark_status.text()
    signals.setup_benchmark_finished.emit(1, result_for(page))
    assert page.benchmark_active
    QtWidgets.QApplication.processEvents()
    assert not page.benchmark_active and page.benchmark_report


def test_pinned_bengali_setup_displays_the_shared_model_and_preserves_automatic_routing(tmp_path):
    qt_modules()
    path = write_config(tmp_path, {'stt': {'routing_enabled': True, 'pinned_languages': ['bn']}})
    before = path.read_bytes()
    wizard = OnboardingWizard(config_path=path, model_status_provider=lambda model: {'state': 'verified', 'missing': []})
    try:
        assert wizard.model_picker.model_id == 'whisper-large-v3-turbo'
        assert wizard.models_page.initial_model_id == 'whisper-large-v3-turbo'
        staged = wizard.practice_config()
        assert staged['stt']['routing_enabled'] and staged['stt']['pinned_languages'] == ['bn']
        assert finish_setup(wizard)
        assert load_config(config_path=path)['stt'] == staged['stt']
        assert path.read_bytes() != before
    finally:
        wizard.close()


def test_global_stop_result_is_shown_as_cancelled_without_a_measurement(ui):
    assert ui.page.start_benchmark()
    ui.page.accept_benchmark_finished(1, {'state': 'cancelled', 'report': None})
    assert 'stopped' in ui.page.benchmark_status.text()
    assert not ui.page.benchmark_report


def test_measured_tier_speech_recommendation_is_staged_only_after_explicit_action(ui):
    assert ui.page.start_benchmark()
    result = result_for(ui.page)
    result['report']['assessment']['tier'] = 'lite'
    result['report']['measurements']['asr_seconds'] = 2.2
    before = ui.path.read_bytes()
    ui.page.accept_benchmark_finished(1, result)
    assert ui.page._candidate['provisional'] is False
    assert 'Measured Lite recommendation' in ui.page.recommendation.text()
    assert ui.page.picker.model_id == DEFAULT_MODEL and ui.page.use_button.isEnabled()
    ui.page.use_button.click()
    assert ui.page.picker.model_id == 'whisper-base' and ui.page.picker.task is None
    assert ui.path.read_bytes() == before


def test_newer_unchanged_model_is_reviewed_before_measurement_and_keeps_routing_on_finish(ui):
    config = load_config(config_path=ui.path)
    config['stt'].update(routing_enabled=True, pinned_languages=['bn'])
    save_config(config, ui.path)
    before = ui.path.read_bytes()
    assert not ui.page.start_benchmark() and not ui.starts
    assert ui.page.picker.model_id == ui.page.initial_model_id == 'whisper-large-v3-turbo'
    assert 'Speech settings changed' in ui.page.benchmark_status.text()
    settle(ui.page)
    assert ui.page.start_benchmark()
    assert ui.starts[0][0]['stt'] == config['stt'] and ui.path.read_bytes() == before
    ui.page.accept_benchmark_finished(1, result_for(ui.page))
    assert finish_setup(ui.wizard)
    assert load_config(config_path=ui.path)['stt'] == config['stt']


@pytest.mark.parametrize('engine_kind', ['fixture', pytest.param('parakeet', marks=[pytest.mark.integration, pytest.mark.offline])])
def test_selected_model_benchmark_through_worker_and_queued_setup_ui(ui, monkeypatch, engine_kind):
    from saydraft.app import WorkerController, create_worker_signals
    from tests.test_onboarding_practice import settle as wait_for

    asr, clock, seen = make_asr()
    asr.model_id = DEFAULT_MODEL
    if engine_kind == 'parakeet':
        directory = os.environ.get('SAYDRAFT_TEST_PARAKEET_V3_MODEL')
        if not directory:
            pytest.skip('set the explicit verified Parakeet v3 fixture root for the setup performance smoke')
        from saydraft.asr.sherpa_parakeet import ParakeetConfig, ParakeetEngine
        from saydraft.privacy.netguard import NetworkGuard
        NetworkGuard.install()
        asr = ParakeetEngine(ParakeetConfig(silence_trim=False), model_dir=directory)
    isolate_measurement(monkeypatch, clock=(lambda: clock.now) if engine_kind == 'fixture' else None)
    gui_thread = threading.get_ident()
    native_threads = []
    prepare, transcribe = asr.prepare, asr.transcribe
    asr.prepare = lambda: (native_threads.append(threading.get_ident()), prepare())[1]
    asr.transcribe = lambda audio: (native_threads.append(threading.get_ident()), transcribe(audio))[1]
    worker, _, executor, events, _, _ = make_worker()
    executor.shutdown()
    pool = ThreadPoolExecutor(max_workers=1)
    worker.executor = pool
    worker._practice_asr = lambda cfg: asr
    worker.services.cleaner.benchmark = lambda: []
    signals = create_worker_signals(QtCore)
    controller = WorkerController(signals)
    controller.core = worker
    worker.emit_callback = controller._emit
    page = ui.page
    page.benchmark_callback = controller.start_setup_benchmark
    page.benchmark_cancel_callback = controller.cancel_setup_benchmark
    signals.setup_benchmark_progress.connect(page.accept_benchmark_progress, QtCore.Qt.QueuedConnection)
    signals.setup_benchmark_finished.connect(page.accept_benchmark_finished, QtCore.Qt.QueuedConnection)
    before = ui.path.read_bytes()
    try:
        assert page.start_benchmark()
        assert page.benchmark_active and worker.busy and not page.benchmark_report
        wait_for(lambda: not page.benchmark_active, timeout=35)
    finally:
        worker.cancel_setup_benchmark()
        pool.shutdown(wait=True)
    assert native_threads and all(ident != gui_thread for ident in native_threads)
    assert not events and not worker.busy and worker.services.recorder.started == 0
    assert page.benchmark_report and page.benchmark_report['measurements']['asr_model'] == DEFAULT_MODEL
    assert latest_report(ui.path.parent / 'hardware-benchmarks') == page.benchmark_report
    assert ui.path.read_bytes() == before and '3 timed samples' in page.benchmark_details.text()
    if engine_kind == 'fixture':
        assert len(seen) == 4


@pytest.mark.parametrize('damage', ['other_model', 'bad_time', 'missing_time', 'missing_model'])
def test_invalid_or_different_model_report_is_not_presented_as_measured(ui, damage):
    page = ui.page
    assert page.start_benchmark()
    result = result_for(page)
    measured = result['report']['measurements']
    if damage == 'other_model':
        measured['asr_model'] = 'whisper-small'
    elif damage == 'bad_time':
        measured['asr_seconds'] = float('nan')
    else:
        measured.pop('asr_seconds' if damage == 'missing_time' else 'asr_model')
    page.accept_benchmark_finished(1, result)
    assert not page.benchmark_report and not page.benchmark_details.text()
    assert 'could not be measured' in page.benchmark_status.text()
