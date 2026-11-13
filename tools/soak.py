"""Soak real services with explicit synthetic devices and optional owned native cleanup."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.soak_runner import MemoryClipboard, MemoryKeyboard, SyntheticCycleRunner  # noqa: E402,F401


@dataclass(frozen=True)
class SoakResult:
    cycles: int
    completed_cycles: int
    failures: int
    ui_freezes: int  # Compatibility: this counts slow worker cycles, not GUI frame freezes.
    start_rss_bytes: int
    end_rss_bytes: int
    rss_growth_ratio: float
    max_rss_growth_ratio: float
    slow_cycle_threshold_seconds: float
    isolation_declared: bool
    rss_measured: bool
    timing_measured: bool
    preparation_seconds: float
    teardown_complete: bool
    errors: list
    runner: dict

    @property
    def ok(self):
        return (self.completed_cycles == self.cycles and self.failures == 0 and self.ui_freezes == 0
            and self.rss_measured and self.timing_measured and self.teardown_complete
            and self.rss_growth_ratio <= self.max_rss_growth_ratio
            and self.runner.get('checks_passed', True))

    @property
    def native_regression_gate_passed(self):
        exits = self.runner.get('native_exit_observed', [])
        processes = self.runner.get('native_processes_started', 0)
        return (self.ok and self.isolation_declared and self.cycles >= 200 and self.rss_growth_ratio < .10
            and self.max_rss_growth_ratio <= .10 and self.slow_cycle_threshold_seconds <= 2
            and self.runner.get('native_cleanup_exercised') is True
            and self.runner.get('native_shutdown_complete') is True
            and type(processes) is int and processes > 0 and len(exits) == processes
            and all(value is True for value in exits)
            and self.runner.get('history_rows') == self.runner.get('checked_insertions') == self.cycles
            and self.runner.get('clipboard_failures') == 0 and self.runner.get('clipboard_restored') is True
            and self.runner.get('normal_length_limited_streams_checked', 0) > 0
            and self.runner.get('outcomes_passed') is True
            and self.runner.get('clipboard_scope') == 'memory')

    def to_text(self, *, command_passed=None):
        passed = self.ok if command_passed is None else command_passed
        return (f"{'PASS' if passed else 'FAIL'}: cycles={self.cycles} completed={self.completed_cycles} "
            f"failures={self.failures} slow_cycles={self.ui_freezes} "
            f"rss_growth={self.rss_growth_ratio*100:.1f}% limit={self.max_rss_growth_ratio*100:.1f}% "
            f"scope={'native-cleanup/memory-input' if self.runner.get('native_cleanup_exercised') else 'synthetic'} "
            f"native_gate={'passed' if self.native_regression_gate_passed else 'not-established'}")

    def report(self):
        return {**asdict(self), 'ok': self.ok, 'slow_cycles': self.ui_freezes,
            'ui_freezes_measured': False, 'timing_scope': 'worker cycle; model preparation recorded separately',
            'rss_scope': 'current process working set; initial preparation and schema precede baseline; end precedes shutdown',
            'native_regression_gate_passed': self.native_regression_gate_passed,
            'owner_windows_acceptance_evaluated': False}


def run_soak(*, cycles=200, rss_reader=None, cycle_runner=None, max_rss_growth_ratio=.10,
             freeze_timeout_seconds=2.0, clock=time.monotonic, isolation_declared=False):
    """Own and close the supplied runner, including failure paths, before reporting."""
    if type(cycles) is not int or not 1 <= cycles <= 10000:
        raise ValueError('cycles must be an integer from 1 to 10000')
    if type(isolation_declared) is not bool:
        raise ValueError('isolation declaration must be boolean')
    if (type(max_rss_growth_ratio) not in (int, float) or not math.isfinite(max_rss_growth_ratio)
            or max_rss_growth_ratio < 0):
        raise ValueError('max_rss_growth_ratio must be finite and non-negative')
    if (type(freeze_timeout_seconds) not in (int, float) or not math.isfinite(freeze_timeout_seconds)
            or freeze_timeout_seconds <= 0):
        raise ValueError('freeze_timeout_seconds must be finite and positive')
    rss = rss_reader or current_rss_bytes
    runner = cycle_runner if cycle_runner is not None else SyntheticCycleRunner()
    errors = []
    failures = completed = slow = 0
    start_rss = end_rss = 0
    measured = timed = teardown = True
    preparation_seconds = 0.0
    details = {'scope': 'provided cycle callable', 'checks_passed': True, 'native_cleanup_exercised': False}

    def error(phase, caught, index=None):
        errors.append({'phase': phase, 'cycle': index, 'error_type': type(caught).__name__})

    def reading(phase):
        nonlocal measured
        try:
            value = rss()
            if type(value) is not int or value <= 0:
                raise ValueError('RSS was not measured')
            return value
        except Exception as caught:
            measured = False
            error(phase, caught)
            return 0

    def preparation(callback, *args):
        nonlocal preparation_seconds
        started = time.monotonic()
        try:
            callback(*args)
        finally:
            preparation_seconds += time.monotonic()-started

    try:
        warmup = getattr(runner, 'warmup', None)
        if warmup is not None:
            preparation(warmup)
        start_rss = reading('rss_start')
        for index in range(1, cycles+1):
            prepare = getattr(runner, 'prepare', None)
            if prepare is not None:
                try:
                    preparation(prepare, index)
                except BaseException as caught:
                    failures += 1
                    error('preparation', caught, index)
                    break
            started = None
            try:
                started = clock()
                runner(index)
                completed += 1
            except BaseException as caught:
                failures += 1
                error('cycle', caught, index)
                if not isinstance(caught, Exception) or getattr(runner, 'fail_fast', False):
                    break
            finally:
                try:
                    finished = clock()
                    if started is None or not math.isfinite(started) or not math.isfinite(finished) or finished < started:
                        raise ValueError('Cycle timing was not measured')
                    if finished-started > freeze_timeout_seconds:
                        slow += 1
                except Exception as caught:
                    timed = False
                    error('timing', caught, index)
        end_rss = reading('rss_end')
    except BaseException as caught:
        failures += 1
        error('warmup_or_measurement', caught)
    finally:
        close = getattr(runner, 'close', None)
        if close is not None:
            try:
                close()
            except BaseException as caught:
                teardown = False
                error('teardown', caught)
        describe = getattr(runner, 'details', None)
        if describe is not None:
            try:
                details = describe()
            except Exception as caught:
                teardown = False
                error('runner_report', caught)
    growth = max(0.0, (end_rss-start_rss)/start_rss) if measured and start_rss > 0 else 0.0
    return SoakResult(cycles, completed, failures, slow, start_rss, end_rss, growth,
        float(max_rss_growth_ratio), float(freeze_timeout_seconds), isolation_declared,
        measured and start_rss > 0 and end_rss > 0, timed,
        preparation_seconds, teardown, errors, details)


def current_rss_bytes():
    if os.name == 'nt':
        return _windows_rss_bytes()
    # /proc reports current resident pages; ru_maxrss is a peak and cannot substitute.
    try:
        fields = Path('/proc/self/statm').read_text().split()
        return int(fields[1])*os.sysconf('SC_PAGE_SIZE')
    except (OSError, ValueError, AttributeError, IndexError):
        return 0


def _windows_rss_bytes() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD,
    ]
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        handle,
        ctypes.byref(counters),
        counters.cb,
    )
    if not ok:
        raise OSError("Could not measure Windows working set")
    return int(counters.WorkingSetSize)



def source_receipt():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT_ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=PROJECT_ROOT, text=True).strip())
    names = ['tools/soak.py', 'tools/soak_runner.py', 'tools/soak_native.py', 'tools/probe_cleanup_app.py',
        'saydraft/models/manifest.json']
    names += [path.relative_to(PROJECT_ROOT).as_posix() for path in (PROJECT_ROOT/'saydraft').rglob('*.py')]
    return {'source_commit': head, 'source_dirty': dirty,
        'source_fingerprints': {name: hashlib.sha256((PROJECT_ROOT/name).read_bytes()).hexdigest() for name in names}}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, default=200)
    parser.add_argument('--target', choices=('synthetic', 'notepad'), default='synthetic',
        help='notepad is a legacy visible-window lifetime check; input still uses memory devices')
    parser.add_argument('--max-rss-growth', type=float, default=.10)
    parser.add_argument('--freeze-timeout', type=float, default=2.0,
        help='slow worker-cycle threshold; does not measure GUI frame freezes')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--cleanup-model', type=Path)
    parser.add_argument('--cleanup-runtime-dir', type=Path)
    parser.add_argument('--cleanup-backend', choices=('cpu', 'vulkan'), default='cpu')
    parser.add_argument('--device')
    parser.add_argument('--fixture-context-override', action='store_true')
    parser.add_argument('--output', type=Path, help='fresh retained QA folder; required with native cleanup')
    parser.add_argument('--isolated', action='store_true', help='declare no competing tests/builds/model transfers are active')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    native = args.cleanup_model is not None or args.cleanup_runtime_dir is not None
    if args.target == 'notepad':
        parser.error('The old Notepad mode only opened a window and still used memory input; use explicit owned/manual Windows checks')
    if native and (args.cleanup_model is None or args.cleanup_runtime_dir is None or args.output is None):
        parser.error('native cleanup needs explicit --cleanup-model, --cleanup-runtime-dir and a fresh --output')
    if not native and (args.device or args.fixture_context_override or args.cleanup_backend != 'cpu'):
        parser.error('device/context options require native cleanup')
    if args.device and (args.cleanup_backend != 'vulkan' or not re.fullmatch(r'Vulkan\d{1,2}', args.device)):
        parser.error('device must identify the selected Vulkan backend')
    if args.output is not None and args.output.exists():
        parser.error('choose a fresh QA output directory')
    if native and not 2 <= args.cycles <= 1000:
        parser.error('native cleanup requires 2–1000 cycles')
    if native and args.cycles >= 200 and not args.isolated:
        parser.error('full native runs require --isolated after stopping competing QA/model workloads')
    if native and args.cycles >= 200 and (args.max_rss_growth > .10 or args.freeze_timeout > 2):
        parser.error('full native runs retain the 10% RSS and 2 s slow-cycle thresholds')
    if (type(args.cycles) is not int or not 1 <= args.cycles <= 10000
            or not math.isfinite(args.max_rss_growth) or args.max_rss_growth < 0
            or not math.isfinite(args.freeze_timeout) or args.freeze_timeout <= 0):
        parser.error('cycles and measurement thresholds must be finite, positive and bounded')
    receipt = source_receipt()
    if native and args.cycles >= 200 and receipt['source_dirty']:
        parser.error('full native runs require a clean source checkout; use a committed worktree')
    from saydraft.privacy.netguard import NetworkGuard
    installed_here = not NetworkGuard.is_installed()
    if installed_here:
        NetworkGuard.install()
    report, runner = None, None
    try:
        if native:
            from tools.soak_native import NativeCycleRunner
            runner = NativeCycleRunner(runtime_dir=args.cleanup_runtime_dir, model=args.cleanup_model,
                output=args.output, backend=args.cleanup_backend, device=args.device,
                fixture_context_override=args.fixture_context_override)
        else:
            if args.output is not None:
                args.output.mkdir(parents=True, exist_ok=False)
            runner = SyntheticCycleRunner(history_path=args.output/'history.db' if args.output else None)
        result = run_soak(cycles=args.cycles, cycle_runner=runner, max_rss_growth_ratio=args.max_rss_growth,
            freeze_timeout_seconds=args.freeze_timeout, isolation_declared=args.isolated)
        report = {**result.report(), **receipt, 'network_guard_installed': True}
        success = result.native_regression_gate_passed if native and args.cycles >= 200 else result.ok
        report['command_passed'] = success
    except Exception as caught:
        report = {**receipt, 'ok': False, 'command_passed': False, 'error_type': type(caught).__name__}
        success = False
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception as caught:
                report = {**(report or receipt), 'ok': False, 'command_passed': False,
                    'teardown_complete': False, 'error_type': type(caught).__name__}
                success = False
        if installed_here:
            NetworkGuard.uninstall()
    if args.output is not None and args.output.is_dir():
        with (args.output/'report.json').open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2, allow_nan=False)
            output.write('\n')
    if args.json:
        print(json.dumps(report, allow_nan=False))
    elif 'result' in locals():
        print(result.to_text(command_passed=success))
    else:
        print('FAIL: '+report.get('error_type', 'measurement unavailable'))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
