import threading
from types import SimpleNamespace as NS

import pytest

from saydraft.context.focused_edit import FocusedEdit
from saydraft.context.tracked_edit import ObservedEdit
from saydraft.core.corrections import CorrectionController
from saydraft.history import DictationHistoryStore
from tests.test_session_worker import Executor
from tests.test_uia_delivery import setup


class Observation:
    def __init__(self):
        self.ops, self.prepared = [], True
        self.ticket = NS(done=threading.Event())
        self.result = ObservedEdit("Kubernetis", "Kubernetes")

    def prepare(self, identity, **kwargs):
        self.ops.append(("prepare", kwargs["lease_seconds"]))
        return self.ticket

    def reserve(self, ticket):
        assert ticket is self.ticket
        self.ops.append(("reserve", self.prepared))
        return self.prepared

    def commit(self, ticket, text):
        self.ops.append(("commit", text))
        return True

    def cancel(self, ticket):
        self.ops.append(("cancel",))

    def take(self, ticket):
        self.ops.append(("take",))
        return self.result

    def close(self):
        self.ops.append(("close",))
        return True


def rig(tmp_path, *, enabled=True):
    worker, clock, executor, uia, api, keyboard, _, _ = setup(queued=True)
    observation, signals = Observation(), []
    worker.services.context._observation = observation
    worker.services.config["dictation"]["learn_corrections"] = enabled
    worker.services.config["stt"]["language"] = "en"
    cleaner = NS(process_transcript=lambda text, context: text)
    worker.services.cleaner = worker.services.processor.cleaner = cleaner
    worker.services.asr.transcribe = lambda audio: "Kubernetis"
    store = DictationHistoryStore(tmp_path / "history.db")
    worker.services.history = worker.services.processor.history = store
    worker.emit_callback = lambda name, *args: signals.append((name, args))
    return NS(worker=worker, clock=clock, executor=executor, uia=uia, api=api,
        keyboard=keyboard, observation=observation, signals=signals, store=store)


def record(r):
    assert r.worker.start_recording()
    r.executor.drain()
    r.clock.now += 1
    r.worker.stop_recording()
    r.executor.drain()


def suggestions(r):
    return [args[0] for name, args in r.signals if name == "dictionary_suggestion"]


def test_mic_history_private_delivery_and_one_queued_suggestion_compose(tmp_path, caplog):
    r = rig(tmp_path)
    send = r.keyboard.send
    def checked(key):
        rows = r.store.list_recent()
        assert rows[0].raw_text == rows[0].cleaned_text == "Kubernetis"
        assert r.observation.ops[-1] == ("reserve", True)
        send(key)
    r.keyboard.send = checked
    prepare = r.observation.prepare
    def while_recording(*args, **kwargs):
        assert r.worker.services.recorder.started == 1
        return prepare(*args, **kwargs)
    r.observation.prepare = while_recording
    record(r)
    assert r.observation.ops == [("prepare", 1260), ("reserve", True), ("commit", "Kubernetis")]
    assert r.keyboard.ops == [("send", "ctrl+v")] and not r.worker.busy
    r.observation.ticket.done.set()
    r.worker.poll_corrections()
    r.worker.poll_corrections()
    assert len(r.executor.jobs) == 1 and not r.worker.busy
    r.executor.drain()
    suggestion, = suggestions(r)
    assert suggestion.candidate.term == "Kubernetes" and r.worker.is_current_correction(suggestion)
    assert len(r.store.list_recent()) == 1 and "Kubernet" not in caplog.text
    r.worker.cancel()
    assert not r.worker.is_current_correction(suggestion)
    r.worker.shutdown()
    r.api.assert_retired()


@pytest.mark.parametrize("ready_during_delay", [False, True])
def test_unready_preparation_never_delays_input_but_can_finish_during_existing_delay(tmp_path, ready_during_delay):
    r = rig(tmp_path)
    r.observation.prepared = False
    if ready_during_delay:
        r.worker.services.inserter.sleep = lambda seconds: setattr(r.observation, "prepared", True)
    record(r)
    assert r.keyboard.ops == [("send", "ctrl+v")]
    assert any(op[0] == "commit" for op in r.observation.ops) == ready_during_delay
    r.observation.ticket.done.set()
    r.worker.poll_corrections()
    r.executor.drain()
    assert bool(suggestions(r)) == ready_during_delay
    r.worker.shutdown()
    r.api.assert_retired()


@pytest.mark.parametrize("failure", ["password", "history", "silence", "short", "disabled", "note"])
def test_non_delivery_and_disabled_learning_never_commit_or_suggest(tmp_path, failure):
    r = rig(tmp_path, enabled=failure != "disabled")
    if failure == "password":
        r.worker.services.asr.transcribe = lambda audio: (
            setattr(r.uia, "result", FocusedEdit(status="password", is_password=True)) or "Kubernetis")
    elif failure == "history":
        r.store.append = lambda entry: (_ for _ in ()).throw(OSError("private history error"))
    elif failure == "silence":
        r.worker.services.asr.transcribe = lambda audio: ""
    assert r.worker.start_recording(insert_text=failure != "note")
    r.executor.drain()
    r.clock.now = .2 if failure == "short" else 1
    r.worker.stop_recording()
    r.executor.drain()
    assert not any(op[0] == "commit" for op in r.observation.ops)
    assert not suggestions(r)
    if failure in ("disabled", "note"):
        assert not r.observation.ops
    r.worker.shutdown()
    r.api.assert_retired()


@pytest.mark.parametrize("action", ["cancel", "new_recording", "settings", "shutdown"])
def test_late_queued_alignment_is_revoked_by_session_changes(tmp_path, action):
    r = rig(tmp_path)
    record(r)
    r.observation.ticket.done.set()
    r.worker.poll_corrections()
    if action == "cancel":
        r.worker.cancel()
    elif action == "new_recording":
        assert r.worker.start_recording()
    elif action == "settings":
        r.worker.services_factory = lambda *a, **kw: r.worker.services
        r.worker.configure(r.worker.services.config)
    else:
        r.worker.shutdown()
    r.executor.drain()
    assert not suggestions(r)
    r.worker.shutdown()
    r.api.assert_retired()


def test_cancellation_between_input_and_commit_drops_learning(tmp_path):
    r = rig(tmp_path)
    send = r.keyboard.send
    def cancel(key):
        send(key)
        r.worker.cancel()
    r.keyboard.send = cancel
    record(r)
    assert len(r.store.list_recent()) == 1 and r.keyboard.ops == [("send", "ctrl+v")]
    assert not any(op[0] == "commit" for op in r.observation.ops)
    r.worker.shutdown()
    r.api.assert_retired()


def test_history_reinsertion_uses_its_own_observation_without_adding_a_history_row(tmp_path):
    r = rig(tmp_path)
    assert r.worker.reinsert_text("Kubernetis")
    r.executor.drain()
    assert r.keyboard.ops == [("send", "ctrl+v")] and not r.store.list_recent()
    assert r.observation.ops == [("prepare", 60), ("reserve", True), ("commit", "Kubernetis")]
    r.observation.ticket.done.set()
    r.worker.poll_corrections()
    r.executor.drain()
    assert suggestions(r)[0].candidate.term == "Kubernetes"
    r.worker.shutdown()
    r.api.assert_retired()


def test_learning_flag_defaults_off_and_round_trips(tmp_path):
    from saydraft.config import default_config, load_config, save_config
    config = default_config()
    assert config["dictation"]["learn_corrections"] is False
    config["dictation"]["learn_corrections"] = True
    path = tmp_path / "config.json"
    save_config(config, path)
    assert load_config(config_path=path)["dictation"]["learn_corrections"] is True


def test_cancellation_while_preparation_returns_cannot_resurrect_scope():
    entered, release = threading.Event(), threading.Event()
    observation = Observation()
    context = NS(cancel_observation=observation.cancel)
    def prepare(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return observation.ticket
    context.prepare_observation = prepare
    controller = CorrectionController(executor=Executor(), current=lambda gen: True, emit=lambda *a: None)
    thread = threading.Thread(target=lambda: controller.prepare(1, context, None, enabled=True, lease_seconds=60))
    try:
        thread.start()
        assert entered.wait(2)
        controller.cancel()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive() and controller.hook(1) is None
    assert observation.ops == [("cancel",)]


def test_failed_old_consumer_cannot_cancel_replacement_with_the_same_generation():
    old, new = Observation(), Observation()
    def context(observation):
        return NS(prepare_observation=lambda target, **kw: observation.prepare(None, **kw),
            reserve_observation=observation.reserve, commit_observation=observation.commit,
            take_observation=observation.take, cancel_observation=observation.cancel)
    first, second = context(old), context(new)
    controller = CorrectionController(executor=Executor(), current=lambda gen: True, emit=lambda *a: None)
    controller.prepare(1, first, None, enabled=True, lease_seconds=60)
    controller.hook(1)()
    controller.complete(1, "Kubernetis", NS(status="inserted"), "en")
    def replaced(ticket):
        controller.prepare(1, second, None, enabled=True, lease_seconds=60)
        raise RuntimeError("private provider detail")
    first.take_observation = replaced
    old.ticket.done.set()
    controller.poll()
    assert controller.hook(1) is not None and new.ops == [("prepare", 60)]


@pytest.mark.parametrize("method", ["typing", "legacy_paste"])
def test_before_input_hook_is_followed_by_safety_checks(method):
    from saydraft.insert.inserter import Inserter
    from tests.test_inserter import FakeClipboard, FakeKeyboard
    clipboard, keyboard, state = FakeClipboard(), FakeKeyboard(), NS(password=False)
    inserter = Inserter(clipboard=clipboard, keyboard=keyboard, focus_provider=lambda: 123,
        sleep=lambda _: None, profiles=[{"match": "Fixture", "insertion": "typing"}] if method == "typing" else [])
    result = inserter.insert_text("Kubernetis", start_focus=123, app_title="Fixture",
        field_guard=lambda: "password_field" if state.password else "",
        before_insert=lambda: setattr(state, "password", True))
    assert result.reason == "password_field" and not keyboard.ops and clipboard.value == "original"
