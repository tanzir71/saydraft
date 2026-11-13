import pytest

from tools.soak import build_parser, main, run_soak
from tools.soak_runner import SyntheticCycleRunner


class Runner:
    def __init__(self, events, *, warmup_error=False, close_error=False):
        self.events, self.closed = events, False
        self.warmup_error, self.close_error = warmup_error, close_error

    def warmup(self):
        self.events.append('warmup')
        if self.warmup_error:
            raise RuntimeError('fixture')

    def prepare(self, index):
        self.events.append(('prepare', index))

    def __call__(self, index):
        self.events.append(('cycle', index))

    def close(self):
        self.events.append('close')
        self.closed = True
        if self.close_error:
            raise RuntimeError('fixture')

    def details(self):
        self.events.append('details')
        return {'checks_passed': self.closed, 'native_cleanup_exercised': False}


def test_preparation_precedes_rss_baseline_and_each_timed_cycle_and_shutdown_precedes_success():
    events = []
    readings = iter([100_000, 101_000])

    def rss():
        events.append('rss')
        return next(readings)

    result = run_soak(cycles=2, rss_reader=rss, cycle_runner=Runner(events),
        clock=iter([0, .1, .2, .3]).__next__)
    assert events == ['warmup', 'rss', ('prepare', 1), ('cycle', 1), ('prepare', 2),
                      ('cycle', 2), 'rss', 'close', 'details']
    assert result.ok and result.teardown_complete and result.rss_measured
    assert result.completed_cycles == 2 and not result.native_regression_gate_passed


@pytest.mark.parametrize('readings', [[0, 100], [100, 0], [True, 100], [float('nan'), 100]])
def test_unmeasured_rss_cannot_pass_and_owned_runner_still_closes(readings):
    events = []
    values = iter(readings)
    result = run_soak(cycles=1, cycle_runner=Runner(events), rss_reader=lambda: next(values))
    assert not result.ok and not result.rss_measured
    assert result.teardown_complete and events[-2:] == ['close', 'details']


def test_rss_failure_and_warmup_failure_do_not_leave_owned_resources_running():
    events = []
    result = run_soak(cycles=3, cycle_runner=Runner(events, warmup_error=True), rss_reader=lambda: 100)
    assert not result.ok and result.completed_cycles == 0
    assert result.teardown_complete and events == ['warmup', 'close', 'details']
    assert result.errors[0]['phase'] == 'warmup_or_measurement'


def test_shutdown_failure_cannot_be_reported_as_success():
    result = run_soak(cycles=1, cycle_runner=Runner([], close_error=True), rss_reader=lambda: 100)
    assert not result.ok and not result.teardown_complete
    assert any(error['phase'] == 'teardown' for error in result.errors)


def test_native_preparation_failure_stops_before_counting_unprepared_cycles():
    class FailedPreparation(Runner):
        def prepare(self, index):
            raise RuntimeError('fixture')

    runner = FailedPreparation([])
    result = run_soak(cycles=200, cycle_runner=runner, rss_reader=lambda: 100)
    assert result.completed_cycles == 0 and result.failures == 1 and runner.closed
    assert not result.ok and not result.native_regression_gate_passed
    assert result.errors[0]['phase'] == 'preparation'


def test_fail_fast_native_cycle_does_not_keep_counting_after_invalid_delivery():
    class FailedCycle(Runner):
        fail_fast = True

        def __call__(self, index):
            raise RuntimeError('fixture')

    events = []
    result = run_soak(cycles=200, cycle_runner=FailedCycle(events), rss_reader=lambda: 100)
    assert result.failures == 1 and result.completed_cycles == 0 and not result.ok
    assert events == ['warmup', ('prepare', 1), 'close', 'details']


@pytest.mark.parametrize('native_exercised,shutdown,cycles,growth,passed', [
    (True, True, 200, 0, True), (False, True, 200, 0, False),
    (True, False, 200, 0, False), (True, True, 199, 0, False),
    (True, True, 200, .10, False), (True, True, 200, .10000001, False),
])
def test_native_gate_requires_full_cycles_native_exit_and_strict_rss_limit(
        native_exercised, shutdown, cycles, growth, passed):
    class NativeFixture(Runner):
        def details(self):
            return {'checks_passed': True, 'native_cleanup_exercised': native_exercised,
                    'native_shutdown_complete': shutdown, 'clipboard_scope': 'memory',
                    'native_processes_started': 1, 'native_exit_observed': [shutdown],
                    'history_rows': cycles, 'checked_insertions': cycles,
                    'clipboard_failures': 0, 'clipboard_restored': True,
                    'normal_length_limited_streams_checked': 1, 'outcomes_passed': True}

    readings = iter([100_000_000, 100_000_000+round(growth*100_000_000)])
    result = run_soak(cycles=cycles, cycle_runner=NativeFixture([]), rss_reader=lambda: next(readings), isolation_declared=True)
    assert bool(result.native_regression_gate_passed) is passed


def test_actual_synthetic_runner_checks_history_before_paste_and_restores_memory_clipboard(tmp_path):
    runner = SyntheticCycleRunner(history_path=tmp_path/'history.db')
    result = run_soak(cycles=5, cycle_runner=runner, rss_reader=lambda: 100)
    assert result.ok and result.runner['checked_insertions'] == result.runner['history_rows'] == 5
    assert result.runner['clipboard_restored'] and result.runner['clipboard_failures'] == 0
    assert runner.keyboard.sent == ['ctrl+v']*5 and not runner.keyboard.written
    assert result.runner['os_clipboard_used'] is False


def test_clipboard_restore_failure_cannot_pass_even_when_insertion_reported_success(tmp_path):
    runner = SyntheticCycleRunner(history_path=tmp_path/'history.db')
    copy = runner.clipboard.copy
    runner.clipboard.copy = lambda text: copy(text) if text != 'clipboard sentinel' else None
    result = run_soak(cycles=1, cycle_runner=runner, rss_reader=lambda: 100)
    assert not result.ok and result.runner['clipboard_failures'] == 1
    assert not result.runner['checks_passed'] and not result.runner['clipboard_restored']


def test_history_before_paste_violation_is_not_hidden_by_successful_clipboard_restore(tmp_path):
    runner = SyntheticCycleRunner(history_path=tmp_path/'history.db')
    runner.history.list_recent = lambda **kwargs: []
    result = run_soak(cycles=1, cycle_runner=runner, rss_reader=lambda: 100)
    assert not result.ok and result.runner['checked_insertions'] == 0
    assert result.runner['clipboard_restored']


@pytest.mark.parametrize('options', [
    {'cycles': True}, {'cycles': 2.5}, {'cycles': 0},
    {'max_rss_growth_ratio': float('nan')}, {'freeze_timeout_seconds': float('inf')},
])
def test_invalid_measurement_contract_is_rejected(options):
    with pytest.raises(ValueError):
        run_soak(cycle_runner=lambda index: None, **options)


@pytest.mark.parametrize('arguments', [
    ['--cleanup-model', 'fixture.gguf'],
    ['--cleanup-runtime-dir', 'runtime'],
    ['--device', 'Vulkan1'],
    ['--cleanup-backend', 'vulkan'],
    ['--target', 'notepad'],
    ['--cycles', 'nan'],
    ['--max-rss-growth', 'nan'],
    ['--cleanup-model', 'fixture', '--cleanup-runtime-dir', 'runtime', '--output', 'output',
     '--cycles', '200', '--max-rss-growth', '.2'],
    ['--cleanup-model', 'fixture', '--cleanup-runtime-dir', 'runtime', '--output', 'output',
     '--cycles', '200', '--isolated', '--max-rss-growth', '.2'],
])
def test_cli_rejects_missing_native_paths_unmeasured_thresholds_and_misleading_window_mode(arguments):
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_default_is_full_regression_count_with_explicit_memory_scope():
    assert build_parser().parse_args([]).cycles == 200
    result = run_soak(cycles=1, cycle_runner=lambda index: None, rss_reader=lambda: 100)
    assert result.report()['ui_freezes_measured'] is False
    assert result.report()['owner_windows_acceptance_evaluated'] is False


def test_passing_generic_threshold_cannot_relax_the_native_slow_cycle_gate():
    class NativeFixture(Runner):
        def details(self):
            return {'checks_passed': True, 'native_cleanup_exercised': True,
                    'native_shutdown_complete': True, 'clipboard_scope': 'memory',
                    'native_processes_started': 1, 'native_exit_observed': [True],
                    'history_rows': 200, 'checked_insertions': 200,
                    'clipboard_failures': 0, 'clipboard_restored': True,
                    'normal_length_limited_streams_checked': 1, 'outcomes_passed': True}

    result = run_soak(cycles=200, cycle_runner=NativeFixture([]), rss_reader=lambda: 100,
        freeze_timeout_seconds=3, isolation_declared=True)
    assert result.ok and not result.native_regression_gate_passed


def test_cli_writes_failed_teardown_before_returning_nonzero(tmp_path, monkeypatch, capsys):
    import json
    from tools import soak

    runner = Runner([], close_error=True)
    monkeypatch.setattr(soak, 'SyntheticCycleRunner', lambda **kwargs: runner)
    monkeypatch.setattr(soak, 'current_rss_bytes', lambda: 100)
    monkeypatch.setattr(soak, 'source_receipt', lambda: {'source_commit': 'fixture', 'source_dirty': False})
    target = tmp_path/'retained'
    assert main(['--cycles', '1', '--output', str(target), '--json']) == 1
    report = json.loads((target/'report.json').read_text(encoding='utf-8'))
    assert not report['command_passed'] and not report['teardown_complete']
    assert json.loads(capsys.readouterr().out)['command_passed'] is False
