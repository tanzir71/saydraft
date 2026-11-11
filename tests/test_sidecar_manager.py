import threading
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.loopback import LocalHTTPError
from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager, child_environment


class Clock:
    now = 10.0

    def advance(self, seconds):
        self.now += seconds


class Process:
    def __init__(self):
        self.code = None
        self.closed = self.stubborn = False

    def poll(self):
        return self.code

    def terminate(self):
        if not self.stubborn:
            self.code = 1

    def close(self):
        self.closed = True
        self.code = 1


@pytest.fixture
def rig(tmp_path):
    clock = Clock()
    timers, processes, launches, keys = [], [], [], []
    mode = SimpleNamespace(healthy=True, request=lambda **kwargs: {"content": "clean words"})
    model = tmp_path / "fixture.gguf"
    model.write_bytes(b"fixture model")
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    class Timer:
        def __init__(self, delay, callback):
            self.delay, self.callback, self.cancelled = delay, callback, False
            timers.append(self)

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

    def process_factory(argv, *, env):
        process = Process()
        processes.append(process)
        launches.append((argv, env))
        return process

    class Client:
        def __init__(self, port, key):
            keys.append(key)

        def request_json(self, path, **kwargs):
            if path == "/health":
                return {"status": "ok" if mode.healthy else "loading"}
            if path == "/tokenize":
                return {"tokens": []}
            return mode.request(**kwargs)

    manager = SidecarManager(SidecarConfig(model, idle_seconds=5, startup_seconds=0.3),
        resolver=lambda model_id: runtime, verify=lambda *args, **kwargs: True,
        capability_check=lambda backend: True, process_factory=process_factory, client_factory=Client,
        clock=lambda: clock.now, timer_factory=Timer, port_factory=lambda: 12345, waiter=clock.advance)
    yield SimpleNamespace(manager=manager, clock=clock, timers=timers, processes=processes,
                          launches=launches, keys=keys, mode=mode)
    manager.close()
    if manager._warmer is not None:
        manager._warmer.join(timeout=2)


def test_constructor_is_inactive_and_preparation_reuses_one_authenticated_server(rig):
    assert not rig.processes and rig.manager.status["state"] == "idle"
    assert rig.manager.prepare() and rig.manager.prepare() and len(rig.processes) == 1
    argv, env = rig.launches[0]
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert {"--offline", "--no-webui", "--no-agent", "--no-ui-mcp-proxy"} <= set(argv)
    assert argv[argv.index("--cache-ram") + 1] == "0" and "--no-context-shift" in argv
    assert "--api-key" not in argv and env["LLAMA_API_KEY"] not in argv
    reply = rig.manager.request_json("/completion", {"prompt": "fixture"}, timeout=0.2)
    assert reply.value == {"content": "clean words"} and reply.reason == "ok"


def test_deadline_discards_late_output_and_restarts_with_new_key_after_backoff(rig):
    assert rig.manager.prepare()

    def late(**kwargs):
        rig.clock.advance(0.21)
        return {"content": "late words"}

    rig.mode.request = late
    reply = rig.manager.request_json("/completion", {}, timeout=0.2)
    assert reply.value is None and reply.reason == "timeout"
    assert rig.processes[0].code == 1 and rig.manager.status["state"] == "backoff"
    assert not rig.manager.prepare() and len(rig.processes) == 1
    rig.clock.advance(1)
    assert rig.manager.prepare() and len(rig.processes) == 2 and rig.keys[0] != rig.keys[1]
    rig.mode.request = lambda **kwargs: {"content": "recovered"}
    assert rig.manager.request_json("/completion", {}, timeout=1).reason == "ok"
    assert rig.manager.status["failures"] == 0


def test_unavailable_transport_preserves_fallback_contract_and_never_overlaps_old_process(rig):
    assert rig.manager.prepare()
    old = rig.processes[0]
    old.stubborn = True

    def unavailable(**kwargs):
        raise LocalHTTPError("fixture failure")

    rig.mode.request = unavailable
    assert rig.manager.request_json("/completion", {}, timeout=0.2).value is None
    rig.clock.advance(1)
    assert not rig.manager.prepare() and len(rig.processes) == 1
    assert rig.manager.status["reason"] == "stopping"
    old.code = 1
    rig.clock.advance(1)
    assert rig.manager.prepare() and len(rig.processes) == 2 and old.closed


def test_idle_unloads_without_restart_and_stale_timer_cannot_stop_recent_use(rig):
    assert rig.manager.prepare()
    old_timer = rig.timers[-1]
    rig.clock.advance(4)
    assert rig.manager.request_json("/completion", {}, timeout=1).reason == "ok"
    rig.clock.advance(1.1)
    old_timer.callback()
    assert rig.manager.ready
    rig.clock.advance(5)
    rig.timers[-1].callback()
    assert rig.manager.status["reason"] == "idle_unloaded" and rig.processes[0].closed
    assert len(rig.processes) == 1
    assert rig.manager.prepare() and len(rig.processes) == 2


def test_health_failure_backoff_is_bounded_and_never_downloads(rig):
    rig.mode.healthy = False
    for _ in range(4):
        assert not rig.manager.prepare()
        rig.clock.advance(31)
    assert len(rig.processes) == 4 and rig.manager.status["reason"] == "restart_limit"
    assert not rig.manager.warm() and not rig.manager.prepare()
    assert all(process.code == 1 for process in rig.processes)


def test_missing_runtime_and_verification_failure_remain_rules_available(rig):
    rig.manager._resolver = lambda model: None
    assert not rig.manager.prepare() and not rig.processes
    assert rig.manager.status["state"] == "missing"
    rig.manager._resolver = lambda model: rig.manager.config.model_path.parent
    rig.manager._verify = lambda *args, **kwargs: False
    assert not rig.manager.prepare() and not rig.processes


def test_close_during_verification_prevents_late_spawn_and_duplicate_prepare(rig):
    entered, release = threading.Event(), threading.Event()

    def verify(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return True

    rig.manager._verify = verify
    thread = threading.Thread(target=rig.manager.prepare)
    thread.start()
    try:
        assert entered.wait(1)
        assert not rig.manager.prepare()
        rig.manager.close()
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive() and not rig.processes and rig.manager.status["state"] == "closed"


def test_busy_request_is_not_queued_and_close_rejects_inflight_response(rig):
    assert rig.manager.prepare()
    entered, release, replies = threading.Event(), threading.Event(), []

    def request(**kwargs):
        entered.set()
        assert release.wait(2)
        return {"content": "late after close"}

    rig.mode.request = request
    thread = threading.Thread(target=lambda: replies.append(rig.manager.request_json("/completion", {}, timeout=1)))
    thread.start()
    try:
        assert entered.wait(1)
        assert rig.manager.request_json("/completion", {}, timeout=1).reason == "busy"
        rig.manager.close()
    finally:
        release.set()
        thread.join(timeout=2)
    assert replies[0].value is None and replies[0].reason == "closed" and rig.processes[0].closed


def test_child_environment_does_not_forward_credentials_or_runtime_switches(monkeypatch):
    for key in ("OPENAI_API_KEY", "GH_TOKEN", "HTTP_PROXY", "LLAMA_ARG_AGENT", "GGML_RPC_SERVERS"):
        monkeypatch.setenv(key, "fixture must not reach child")
    env = child_environment("fixture_api_key")
    assert not set(env) & {"OPENAI_API_KEY", "GH_TOKEN", "HTTP_PROXY", "LLAMA_ARG_AGENT", "GGML_RPC_SERVERS"}
    assert env["LLAMA_API_KEY"] == "fixture_api_key" and env["HF_HUB_OFFLINE"] == "1"
