"""Own a bounded meeting stream until drained output and full tree exit agree.

Start/finish/stop run on an application worker, never the Qt GUI thread. The
GUI shows the persistent capsule before admission and keeps it until an outcome
confirms stopped=True. Stop intent, END and primary exit alone are insufficient.
"""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import queue
import site
import sys
import sysconfig
import threading
import time
import weakref

from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from .child import REQUEST_ENV
from .protocol import CaptureDecoder, CaptureEnd
from .request import CaptureRequest
from .stop import StopEvent


class CaptureBackpressure(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptureOutcome:
    stopped: bool
    complete: bool
    reason: str
    exit_code: int | None = None
    forced: bool = False
    end: CaptureEnd | None = None


def capture_command(request, signal_name):
    env = {key: value for key, value in os.environ.items()
           if key.upper() in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')}
    env.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    env[REQUEST_ENV] = request.to_json()
    executable = str(Path(sys.executable).resolve())
    if getattr(sys, 'frozen', False):
        return [executable, '--meeting-capture', signal_name], str(Path(executable).parent), env
    root = Path(__file__).resolve().parents[2]
    # Explicit source-library paths, not ambient PYTHONPATH, proxies, tokens or
    # profile settings. PYTHONPATH does not execute a site's .pth startup files.
    candidates = [str(root), sysconfig.get_path('purelib'), sysconfig.get_path('platlib'),
                  *site.getsitepackages(), site.getusersitepackages()]
    paths = []
    for supplied in candidates:
        if type(supplied) is not str or supplied.startswith(('\\\\', '//')):
            continue
        path = Path(supplied)
        if not path.is_absolute():
            continue
        path = path.resolve()
        if str(path).startswith(('\\\\', '//')) or not path.is_dir():
            continue
        value = str(path)
        if value not in paths:
            paths.append(value)
    env['PYTHONPATH'] = os.pathsep.join(paths)
    return [executable, '-m', 'saydraft', '--meeting-capture', signal_name], str(root), env


class CaptureProcess:
    def __init__(self, request, *, process_factory=WindowsJobProcess, event_factory=StopEvent.create,
                 command_factory=capture_command, queue_size=200, clock=time.monotonic):
        if type(request) is not CaptureRequest or type(queue_size) is not int or not 8 <= queue_size <= 400:
            raise ValueError('Invalid meeting capture owner')
        self.request = request
        self._factory, self._event_factory, self._command_factory = process_factory, event_factory, command_factory
        self._clock, self._lock, self._finishing = clock, threading.RLock(), threading.Lock()
        self._events = queue.Queue(maxsize=queue_size)
        self._decoder = CaptureDecoder(self._events.put_nowait, max_seconds=request.max_seconds)
        self._process = self._signal = self._result = None
        self._used = self._starting = self._stop_requested = self._forced = False
        self._failure = None
        self._protocol_checked = False
        self._accepted_end = None

    @property
    def active(self):
        with self._lock:
            return self._starting or self._process is not None

    def _receive(self, data):
        try:
            self._decoder.feed(data)
        except queue.Full as error:
            self._failure = 'backpressure'
            raise CaptureBackpressure('Meeting receiver is full') from error
        except Exception:
            self._failure = 'invalid_transport'
            raise

    def start(self, *, indicator_ready=False):
        if self.request.consent is not True or indicator_ready is not True:
            raise PermissionError('Confirm consent and show the persistent recording capsule before capture')
        self.request.to_json()  # Reject oversized selections before creating native resources.
        with self._lock:
            if self._used:
                raise RuntimeError('A meeting capture owner can start only once')
            if self._stop_requested:
                self._used = True
                self._result = CaptureOutcome(True, False, 'cancelled')
                return self
            self._used = self._starting = True
        signal = process = None
        try:
            signal = self._event_factory()
            with self._lock:
                self._signal = signal
                if self._stop_requested:
                    signal.set()
            argv, cwd, env = self._command_factory(self.request, signal.name)
            reference = weakref.ref(self)
            def receive(data):
                owner = reference()
                if owner is None:
                    raise RuntimeError('Meeting capture owner retired')
                owner._receive(data)
            process = self._factory(argv, cwd=cwd, env=env, on_output=receive)
            if process is None:
                raise RuntimeError('Meeting helper was not created')
            with self._lock:
                self._process = process
                self._starting = False
                if self._stop_requested:
                    signal.set()
            return self
        except BaseException:
            with self._lock:
                self._starting = False
                if process is not None and self._process is None:
                    self._process = process
                # If native creation completed, retain ownership for stop/exit
                # observation even if signalling afterwards failed.
                if self._process is None:
                    self._signal = None
                    if signal is not None:
                        signal.close()
                else:
                    self._forced = True
            if process is not None:
                try:
                    process.terminate()
                except OSError:
                    pass  # Retain the job for a later explicit exit observation.
            raise

    def take(self, *, limit=64):
        if type(limit) is not int or not 1 <= limit <= 400:
            raise ValueError('Invalid meeting event batch size')
        result = []
        for _ in range(limit):
            try:
                result.append(self._events.get_nowait())
            except queue.Empty:
                break
        return result

    def request_stop(self):
        with self._lock:
            self._stop_requested = True
            if self._signal is not None:
                self._signal.set()

    def poll(self):
        with self._lock:
            if self._result is not None:
                return self._result
            process, starting = self._process, self._starting
        if starting or process is None or process.poll_tree() is None:
            return None
        try:
            return self.finish(timeout=0)
        except TimeoutError:
            return None  # EOF may trail the kernel exit by a reader-thread turn.

    def finish(self, *, timeout=2):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 10:
            raise ValueError('Invalid meeting exit deadline')
        if not self._finishing.acquire(blocking=False):
            raise RuntimeError('Meeting exit observation is already running')
        try:
            with self._lock:
                if self._result is not None:
                    return self._result
                process = self._process
                if self._starting or process is None:
                    raise RuntimeError('Meeting capture has not finished starting')
            deadline = self._clock() + timeout
            code = process.wait_tree(timeout)
            if not self._protocol_checked:
                try:
                    process.finish_output(max(0, deadline - self._clock()))
                except TimeoutError:
                    raise  # Keep the owner/capsule until pipe EOF is observed.
                except OSError:
                    self._failure = self._failure or 'transport_failed'
                else:
                    try:
                        self._accepted_end = self._decoder.finish()
                    except ValueError:
                        self._failure = self._failure or 'incomplete_transport'
                self._protocol_checked = True
            end = self._accepted_end
            complete = code == 0 and end is not None and end.complete and not self._forced and self._failure is None
            reason = (self._failure or ('forced_stop' if self._forced else end.reason if end is not None
                                       else 'unexpected_exit'))
            if code != 0 and complete is False and reason in ('stopped', 'limit'):
                reason = 'unexpected_exit'
            result = CaptureOutcome(True, bool(complete), reason, code, self._forced, end)
            process.close()
            with self._lock:
                if self._signal is not None:
                    self._signal.close()
                self._signal = self._process = None
                self._result = result
            return result
        finally:
            self._finishing.release()

    def stop(self, *, timeout=2):
        """Worker-only graceful stop, then confirmed Job Object termination."""
        try:
            self.request_stop()
            with self._lock:
                if self._result is not None:
                    return self._result
                if self._starting:
                    return CaptureOutcome(False, False, 'starting')
                if self._process is None:
                    return CaptureOutcome(True, False, 'cancelled')
            return self.finish(timeout=timeout)
        except (TimeoutError, OSError):
            with self._lock:
                process = self._process
                if process is None:
                    raise
                self._forced = True
            process.terminate()
            try:
                return self.finish(timeout=2)
            except (TimeoutError, OSError):
                return CaptureOutcome(False, False, 'stop_unconfirmed', forced=True)

    def __del__(self):
        # Best-effort owner loss kills the Job Object. This does not manufacture
        # a confirmed-stop result; live UI controllers explicitly finish first.
        try:
            process, signal = getattr(self, '_process', None), getattr(self, '_signal', None)
            if process is not None:
                process.close()
            if signal is not None:
                signal.close()
        except Exception:
            pass
