"""One owned, cache-only cleanup server with bounded requests and recovery."""

from __future__ import annotations

import logging
import math
import os
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from saydraft.model_download import find_installed_model
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.models.runtime_ids import runtime_model_id
from .loopback import LoopbackClient
from .ownership import PROCESS_SLOT
from .windows_process import WindowsJobProcess

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SidecarConfig:
    model_path: Path
    backend: str = "cpu"
    threads: int = 4
    context_size: int = 4096
    idle_seconds: float = 900
    startup_seconds: float = 15
    retry_seconds: float = 1
    max_restarts: int = 3

    def __post_init__(self):
        runtime_model_id(self.backend)
        if not Path(self.model_path).is_absolute():
            raise ValueError("Cleanup model path must be absolute")
        if type(self.threads) is not int or not 1 <= self.threads <= 64:
            raise ValueError("Cleanup thread count is invalid")
        if type(self.context_size) is not int or not 256 <= self.context_size <= 65536:
            raise ValueError("Cleanup context size is invalid")
        if any(not math.isfinite(value) or value <= 0 for value in (
                self.idle_seconds, self.startup_seconds, self.retry_seconds)):
            raise ValueError("Cleanup lifecycle durations must be positive and finite")
        if type(self.max_restarts) is not int or not 0 <= self.max_restarts <= 10:
            raise ValueError("Cleanup restart count is invalid")


@dataclass(frozen=True)
class SidecarReply:
    value: dict | None
    reason: str


def _capable(backend):
    from saydraft.models.windows_hardware import cpu_features, vulkan_devices

    return bool(os.name == "nt" and cpu_features().get("avx2") and
                (backend == "cpu" or vulkan_devices()))


def _port():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def child_environment(key):
    # Never forward credentials, proxy settings or inherited LLAMA/GGML switches.
    values = {name: value for name, value in os.environ.items()
              if name.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")}
    values.update(LLAMA_API_KEY=key, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    return values


class SidecarManager:
    def __init__(self, config, *, resolver=find_installed_model, verify=installation_ready,
                 capability_check=_capable, process_factory=WindowsJobProcess, client_factory=LoopbackClient,
                 clock=time.monotonic, timer_factory=threading.Timer, port_factory=_port, waiter=None,
                 process_slot=PROCESS_SLOT):
        self.config = config
        self._resolver, self._verify, self._capable = resolver, verify, capability_check
        self._process_factory, self._client_factory = process_factory, client_factory
        self._process_slot = process_slot
        self._clock, self._timer, self._port_factory = clock, timer_factory, port_factory
        self._lock, self._starting, self._requesting = threading.RLock(), threading.Lock(), threading.Lock()
        self._closed = threading.Event()
        self._wait = waiter or self._closed.wait
        self._process = self._client = self._idle_timer = self._retry_timer = self._warmer = None
        self._epoch, self._failed_epoch, self._failures = 0, -1, 0
        self._next_start = self._last_used = 0.0
        self._state, self._reason = "idle", "not_started"

    @property
    def status(self):
        with self._lock:
            if self._closed.is_set():
                return {"state": "closed", "reason": "closed", "failures": self._failures}
            if self._state == "ready":
                try:
                    if self._process.poll() is not None:
                        self._fail_locked(self._epoch, "process_exit")
                except Exception:
                    self._fail_locked(self._epoch, "process_unavailable")
            return {"state": self._state, "reason": self._reason, "failures": self._failures}

    @property
    def ready(self):
        return self.status["state"] == "ready"

    def _cancel(self, name):
        timer = getattr(self, name)
        if timer is not None:
            timer.cancel()
            setattr(self, name, None)

    def _schedule(self, seconds, action):
        timer = self._timer(seconds, action)
        timer.daemon = True
        timer.start()
        return timer

    def _retire_locked(self):
        if self._process is None:
            return True
        if not self._process_slot.retire(self._process):
            return False  # Never replace an old process until its exit is observed.
        self._process = self._client = None
        return True

    def _retry_locked(self):
        self._cancel("_retry_timer")
        if self._closed.is_set() or self._failures > self.config.max_restarts:
            return
        delay = min(30, self.config.retry_seconds * 2 ** max(0, self._failures - 1))
        self._next_start = self._clock() + delay
        self._retry_timer = self._schedule(delay, self.warm)

    def _fail_locked(self, epoch, reason):
        if self._closed.is_set() or epoch != self._epoch or self._failed_epoch == epoch:
            return
        self._failed_epoch, self._failures = epoch, self._failures + 1
        self._client = None
        self._cancel("_idle_timer")
        self._state, self._reason = "backoff", reason
        if self._process is not None:
            try:
                self._retire_locked()
            except Exception:
                self._state, self._reason = "failed", "stop_failed"
                self._cancel("_retry_timer")
                return
        if self._failures > self.config.max_restarts:
            self._state, self._reason = "failed", "restart_limit"
        logger.warning("Local cleanup unavailable (%s)", reason)
        self._retry_locked()

    def warm(self):
        with self._lock:
            if self._closed.is_set() or self._state == "failed" or self._clock() < self._next_start:
                return False
            if self._state == "ready":
                return self.ready
            if self._warmer is not None and self._warmer.is_alive():
                return True
            self._warmer = threading.Thread(target=self.prepare, name="Saydraft-cleanup-warmup", daemon=True)
            self._warmer.start()
            return True

    def prepare(self):
        if not self._starting.acquire(blocking=False):
            return False
        try:
            with self._lock:
                if self._closed.is_set() or self._state == "failed" or self._clock() < self._next_start:
                    return False
                if self._state == "ready":
                    if self._process.poll() is None:
                        return True
                    self._fail_locked(self._epoch, "process_exit")
                    return False
                if not self._retire_locked():
                    self._state, self._reason = "backoff", "stopping"
                    self._retry_locked()
                    return False
                self._cancel("_retry_timer")
            model_id = runtime_model_id(self.config.backend)
            directory = self._resolver(model_id)
            if (not Path(self.config.model_path).is_file() or directory is None or
                    not self._capable(self.config.backend) or
                    not self._verify(get_model(model_id), directory, check_hashes=True)):
                with self._lock:
                    if not self._closed.is_set():
                        self._state, self._reason = "missing", "model_runtime_or_hardware_unavailable"
                return False
            with self._lock:
                if self._closed.is_set():
                    return False
                self._epoch += 1
                epoch = self._epoch
                port, key = self._port_factory(), secrets.token_urlsafe(32)
                argv = [str(Path(directory) / "llama-server.exe"), "--offline", "--model", str(self.config.model_path),
                    "--host", "127.0.0.1", "--port", str(port), "--ctx-size", str(self.config.context_size),
                    "--threads", str(self.config.threads), "--parallel", "1", "--n-gpu-layers",
                    "0" if self.config.backend == "cpu" else "auto", "--no-webui", "--no-agent",
                    "--no-ui-mcp-proxy", "--cache-ram", "0", "--no-cache-idle-slots", "--no-context-shift",
                    "--alias", "saydraft-cleanup"]
                try:
                    self._process = self._process_slot.start(self._process_factory, argv, env=child_environment(key))
                    if self._process is None:
                        self._state, self._reason = "backoff", "another_manager_active"
                        self._retry_locked()
                        return False
                    self._client = self._client_factory(port, key)
                except Exception:
                    self._fail_locked(epoch, "startup_failed")
                    return False
                self._state, self._reason = "loading", "health_pending"
                client, process = self._client, self._process
            deadline = self._clock() + self.config.startup_seconds
            while not self._closed.is_set() and self._clock() < deadline:
                with self._lock:
                    if self._closed.is_set() or epoch != self._epoch:
                        return False
                    if process.poll() is not None:
                        break
                try:
                    health = client.request_json("/health", deadline=min(deadline, self._clock() + 0.25))
                    # Tokenization is authenticated even if a server exempts health/models.
                    client.request_json("/tokenize", payload={"content": ""}, deadline=min(deadline, self._clock() + 0.25))
                    if health.get("status") == "ok":
                        with self._lock:
                            if epoch != self._epoch or self._closed.is_set():
                                return False
                            if process.poll() is not None:
                                break
                            self._state, self._reason = "ready", "ready"
                            self._touch_locked(epoch)
                            return True
                except Exception:
                    pass
                self._wait(min(0.05, max(0, deadline - self._clock())))
            with self._lock:
                self._fail_locked(epoch, "health_failed")
            return False
        except Exception:
            with self._lock:
                if not self._closed.is_set():
                    if self._process is not None:
                        self._fail_locked(self._epoch, "prepare_failed")
                    else:
                        self._state, self._reason = "missing", "prepare_failed"
            return False
        finally:
            self._starting.release()

    def _touch_locked(self, epoch):
        self._last_used = self._clock()
        self._cancel("_idle_timer")

        def idle():
            with self._lock:
                if epoch != self._epoch or self._state != "ready" or self._requesting.locked():
                    return
                if self._clock() - self._last_used < self.config.idle_seconds:
                    return
                try:
                    self._retire_locked()
                except Exception:
                    self._state, self._reason = "failed", "stop_failed"
                    return
                self._client = None
                self._state, self._reason = "idle", "idle_unloaded"

        self._idle_timer = self._schedule(self.config.idle_seconds, idle)

    def request_json(self, path, payload, *, timeout):
        return self.run(lambda client, deadline: client.request_json(path, payload=payload, deadline=deadline), timeout=timeout)

    def run(self, operation, *, timeout):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Cleanup request timeout must be positive and finite")
        if not self._requesting.acquire(blocking=False):
            return SidecarReply(None, "busy")
        epoch = None
        try:
            with self._lock:
                if not self.ready:
                    self.warm()  # Loads installed files in the background; never downloads.
                    return SidecarReply(None, "not_ready")
                epoch, client = self._epoch, self._client
                self._cancel("_idle_timer")
            deadline = self._clock() + timeout
            try:
                value = operation(client, deadline)
                if self._clock() >= deadline:
                    raise TimeoutError("Cleanup deadline expired")
                with self._lock:
                    if self._closed.is_set() or epoch != self._epoch:
                        return SidecarReply(None, "closed")
                    self._failures = 0
                return SidecarReply(value, "ok")
            except Exception as error:
                reason = "closed" if self._closed.is_set() else "timeout" if isinstance(error, TimeoutError) else "unavailable"
                with self._lock:
                    self._fail_locked(epoch, reason)
                return SidecarReply(None, reason)
        finally:
            self._requesting.release()
            with self._lock:
                if epoch == self._epoch and self._state == "ready":
                    self._touch_locked(epoch)

    def close(self):
        self._closed.set()
        with self._lock:
            self._cancel("_idle_timer")
            self._cancel("_retry_timer")
            if self._process is not None:
                try:
                    self._retire_locked()
                except Exception:
                    logger.warning("Local cleanup handle closure failed; owner-exit job cleanup remains active")
            self._client = None
            self._state, self._reason = "closed", "closed"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
