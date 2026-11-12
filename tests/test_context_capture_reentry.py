"""GUI reentry during focused-field discovery must not start a stale recording."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from saydraft.config import default_config
from tests.test_session_worker import make_worker


@pytest.mark.parametrize("action", ["cancel", "stop", "settings", "shutdown", "second_start"])
def test_gui_actions_return_before_context_rendering_and_no_stale_microphone_starts(action):
    worker, _, executor, events, _, _ = make_worker(queued=True)
    entered, release = threading.Event(), threading.Event()
    original = worker.services.context.capture()
    services, started, failures = worker.services, [], []
    def capture():
        entered.set()
        assert release.wait(5)
        return original
    services.context.capture = capture
    def start():
        try:
            started.append(worker.start_recording())
        except Exception as error:
            failures.append(error)
    thread = threading.Thread(target=start)
    thread.start()
    try:
        assert entered.wait(2) and worker.busy
        with ThreadPoolExecutor(max_workers=1) as gui:
            def invoke():
                if action == "settings":
                    config = default_config()
                    config["dictation"]["profile"] = "chat"
                    replacement = replace(services, config=config)
                    worker.services_factory = lambda *args, **kwargs: replacement
                    worker.configure(config)
                    assert worker.services is services and worker._pending_config == config
                elif action == "second_start":
                    assert not worker.start_recording()
                    worker.cancel()
                elif action == "shutdown":
                    worker.shutdown()
                elif action == "stop":
                    worker.stop_recording()
                else:
                    worker.cancel()
                return True
            future = gui.submit(invoke)
            try:
                assert future.result(timeout=1)
            finally:
                release.set()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive() and not failures and started == [False]
    assert services.recorder.started == services.recorder.stopped == 0 and not events
    if action == "settings":
        # Only the serial executor may retire/reconfigure the hook dispatcher.
        assert worker.services is services and len(executor.jobs) == 1 and worker.busy
        executor.drain()
        assert worker.services.config["dictation"]["profile"] == "chat" and worker._pending_config is None
    assert not worker.busy and not worker.session.active
    if action != "shutdown":
        worker.shutdown()


def test_context_failure_releases_start_slot_and_keeps_the_hotkey_route_usable():
    worker, _, executor, events, signals, _ = make_worker(queued=True)
    original = worker.services.context.capture
    def fail():
        raise RuntimeError("Public fixture failure")
    worker.services.context.capture = fail
    assert worker.start_recording() is False
    assert not worker.busy and not worker.session.active and not executor.jobs and not events
    assert signals == [("notification_requested", "Could not read the target field. Try dictation again.")]
    worker.services.context.capture = original
    assert worker.start_recording()
    executor.drain()
    assert worker.services.recorder.started == 1
    worker.cancel()
    executor.drain()
    worker.shutdown()


def test_release_while_arming_still_cancels_when_capture_start_has_not_returned():
    worker, _, _, events, _, _ = make_worker()
    worker.services.asr.prepare = worker.stop_recording
    assert worker.start_recording()
    assert not worker.session.active and not worker.busy
    assert worker.services.recorder.started == 0 and not events
    worker.shutdown()
