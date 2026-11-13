import threading
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.loopback import LocalHTTPError
from saydraft.cleanup.llm.ownership import ProcessSlot
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
        clock=lambda: clock.now, timer_factory=Timer, port_factory=lambda: 12345, waiter=clock.advance,
        process_slot=ProcessSlot(timer_factory=Timer))
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


def test_repeated_requests_refresh_idle_time_without_starting_more_timers(rig):
    assert rig.manager.prepare()
    timer = rig.timers[-1]
    count = len(rig.timers)
    for _ in range(100):
        rig.clock.advance(.01)
        assert rig.manager.request_json("/completion", {}, timeout=1).reason == "ok"
    assert len(rig.timers) == count and not timer.cancelled
    rig.clock.advance(4.1)
    timer.callback()
    assert rig.manager.ready and len(rig.timers) == count+1
    assert rig.timers[-1].delay == pytest.approx(.9)
    # A fired/cancelled callback cannot replace or disarm its successor.
    successor = rig.timers[-1]
    timer.callback()
    assert rig.timers[-1] is successor and not successor.cancelled
    rig.clock.advance(1)
    successor.callback()
    assert rig.manager.status["reason"] == "idle_unloaded"


def test_idle_check_during_active_request_rearms_until_the_next_quiet_period(rig):
    assert rig.manager.prepare()
    entered, release = threading.Event(), threading.Event()
    replies = []

    def request(**_kwargs):
        entered.set()
        assert release.wait(2)
        return {"content": "fixture"}

    rig.mode.request = request
    worker = threading.Thread(target=lambda: replies.append(rig.manager.request_json("/completion", {}, timeout=20)))
    worker.start()
    try:
        assert entered.wait(2)
        rig.clock.advance(6)
        rig.timers[-1].callback()
        assert rig.manager.ready and not rig.processes[0].closed
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive() and replies[0].reason == "ok"
    rig.clock.advance(4)
    rig.timers[-1].callback()
    assert rig.manager.ready
    rig.clock.advance(1.1)
    rig.timers[-1].callback()
    assert rig.manager.status["reason"] == "idle_unloaded"


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


def replacement(manager):
    return SidecarManager(manager.config, resolver=manager._resolver, verify=manager._verify,
        capability_check=manager._capable, process_factory=manager._process_factory,
        client_factory=manager._client_factory, clock=manager._clock, timer_factory=manager._timer,
        port_factory=manager._port_factory, waiter=manager._wait, process_slot=manager._process_slot)


def test_replacement_cannot_launch_until_closed_managers_process_exit_is_observed(rig):
    assert rig.manager.prepare()
    old = rig.processes[0]
    old.stubborn = True
    new = replacement(rig.manager)
    try:
        rig.manager.close()
        assert not old.closed and not new.prepare() and len(rig.processes) == 1
        assert new.status["reason"] == "another_manager_active"
        old.code = 1
        rig.clock.advance(1)
        assert new.prepare() and old.closed and len(rig.processes) == 2
        # A late old-manager close cannot kill the replacement.
        rig.manager.close()
        assert new.ready and rig.processes[1].poll() is None
    finally:
        old.code = 1
        new.close()


def test_two_live_managers_share_one_process_admission_slot(rig):
    assert rig.manager.prepare()
    new = replacement(rig.manager)
    try:
        assert not new.prepare() and rig.manager.ready and len(rig.processes) == 1
        new.close()
        assert rig.manager.ready
    finally:
        new.close()


def test_async_exit_reaper_releases_handles_even_without_a_replacement(rig):
    assert rig.manager.prepare()
    old = rig.processes[0]
    old.stubborn = True
    rig.manager.close()
    pending = rig.timers[-1]
    assert not old.closed
    pending.callback()
    assert not old.closed and rig.timers[-1] is not pending
    old.code = 1
    rig.timers[-1].callback()
    assert old.closed and rig.manager._process_slot._process is None


def test_failed_exit_observation_refuses_admission_and_preserves_handles(rig):
    assert rig.manager.prepare()
    old = rig.processes[0]
    poll = old.poll
    old.poll = lambda: (_ for _ in ()).throw(OSError("fixture inaccessible handle"))
    new = replacement(rig.manager)
    try:
        rig.manager.close()
        assert not new.prepare() and len(rig.processes) == 1 and not old.closed
        rig.timers[-1].callback()
        assert not old.closed
    finally:
        old.poll = poll
        old.code = 1
        rig.manager._process_slot.retire(old)
        new.close()


def test_simultaneous_manager_admission_never_runs_two_factories():
    slot = ProcessSlot()
    entered, release = threading.Event(), threading.Event()
    calls, results = [], []
    process = SimpleNamespace(poll=lambda: None)

    def factory(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return process

    first = threading.Thread(target=lambda: results.append(slot.start(factory, [], env={})))
    second = threading.Thread(target=lambda: results.append(slot.start(factory, [], env={})))
    first.start()
    try:
        assert entered.wait(1)
        second.start()
    finally:
        release.set()
        first.join(2)
        second.join(2)
    assert not first.is_alive() and not second.is_alive()
    assert len(calls) == 1 and results.count(process) == 1 and results.count(None) == 1
