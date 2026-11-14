"""Revocation and native-owner switching, with authored text and fake transports."""

import threading
import time
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager, SidecarReply
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from tests.test_command_edit import Model
from tests import test_sidecar_manager

rig = test_sidecar_manager.rig


def fixture(tmp_path, *, enabled=True):
    events, managers = [], []
    def factory(config):
        index, model = len(managers), Model()
        state = {'state': 'idle', 'reason': 'not_started'}
        def warm():
            events.append(('warm', index))
            if state['state'] != 'closed':
                state['state'] = 'ready'
                return True
            return False
        def close():
            state['state'] = 'closed'
            events.append(('close', index))
        def run(operation, *, timeout):
            if state['state'] != 'ready':
                return SidecarReply(None, 'not_ready')
            return SidecarReply(operation(model, time.monotonic() + timeout), 'ok')
        manager = SimpleNamespace(config=config, model=model, status=state, warm=warm, close=close, run=run)
        managers.append(manager)
        events.append(('construct', index))
        return manager
    def client_factory(manager, **kwargs):
        return SimpleNamespace(manager=manager, clean=lambda *a, **kw: SimpleNamespace(text='Cleaned.', reason='ok'))
    cfg = LocalLLMConfig(enabled=enabled, model_path=str(tmp_path / 'cleanup.gguf'), prepare_prompt=False)
    cleaner = LocalLLMCleaner(cfg, manager_factory=factory, client_factory=client_factory)
    config = SidecarConfig(tmp_path / 'command.gguf', startup_seconds=60)
    return SimpleNamespace(cleaner=cleaner, config=config, events=events, managers=managers)


def test_command_is_lazy_independent_of_cleanup_enable_and_uses_explicit_model_identity(tmp_path):
    f = fixture(tmp_path, enabled=False)
    assert not f.cleaner.available() and not f.events
    with f.cleaner.command_session(f.config, 'command-fixture') as session:
        assert not f.events and session.model_id == 'command-fixture'
        assert session.prepare() == 'ready'
        reply = session.edit_selection('I wanted to say the file arrived.', 'Make shorter.')
        assert reply.text == 'The file arrived.' and reply.reason == 'ok' and reply.stream_complete
        assert f.cleaner.clean('words') == (None, 'busy') and not f.cleaner.warm()
        assert f.cleaner.edit_selection('Text.', 'Make shorter.').reason == 'busy'
    assert f.events == [('construct', 0), ('warm', 0), ('close', 0)]
    assert not f.cleaner.available() and f.cleaner.clean('words') == (None, 'disabled')


def test_switch_retires_cleanup_preparation_and_restores_only_on_next_cleanup_request(tmp_path):
    f = fixture(tmp_path)
    assert f.cleaner.warm()
    preparation = SimpleNamespace(close=lambda: f.events.append(('preparation_close', 0)))
    f.cleaner._preparation = preparation
    session = f.cleaner.command_session(f.config, 'command-fixture')
    assert f.events[-2:] == [('preparation_close', 0), ('close', 0)]
    assert f.cleaner._preparation is None and f.cleaner._client is None
    assert session.prepare() == 'ready'
    assert f.cleaner.command_session(f.config, 'second') is None
    session.close()
    assert len(f.managers) == 2 and f.managers[1].status['state'] == 'closed'
    assert f.cleaner.warm() and len(f.managers) == 3
    assert f.managers[2].config.model_path.name == 'cleanup.gguf'
    session.close()  # Old closure cannot retire the new normal owner.
    assert f.managers[2].status['state'] == 'ready'
    f.cleaner.close()


def test_late_cleanup_reply_cannot_escape_across_a_command_reservation_and_release(tmp_path):
    f = fixture(tmp_path)
    f.cleaner.warm()
    def late(*args, **kwargs):
        session = f.cleaner.command_session(f.config, 'command-fixture')
        session.close()
        assert f.cleaner.warm()
        return SimpleNamespace(text='Retired private text.', reason='ok')
    f.cleaner._client.clean = late
    assert f.cleaner.clean('Authored fixture.') == (None, 'retired')
    f.cleaner.close()


@pytest.mark.parametrize('state,expected', [('missing', 'unavailable'), ('failed', 'unavailable'),
                                          ('loading', 'startup_timeout')])
def test_failed_or_timed_out_preparation_retires_manager_and_releases_reservation(tmp_path, state, expected):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    manager = session._get_manager()
    manager.warm = lambda: manager.status.update(state=state)
    assert session.prepare(timeout=.01) == expected
    assert manager.status['state'] == 'closed' and f.cleaner._command is None
    assert session.edit_selection('Text.', 'Make shorter.').reason == 'cancelled'
    assert f.cleaner.warm()
    f.cleaner.close()


def test_cancel_before_preparation_has_no_runtime_or_request(tmp_path):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    assert session.prepare(cancelled=lambda: True) == 'cancelled'
    assert not f.events and f.cleaner._command is None
    assert session.prepare() == 'cancelled'


def test_cancel_while_waiting_never_joins_starter_and_releases_owner(tmp_path):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    manager = session._get_manager()
    waiting = threading.Event()
    def warm():
        manager.status['state'] = 'loading'
        waiting.set()
    manager.warm = warm
    results = []
    thread = threading.Thread(target=lambda: results.append(session.prepare()))
    thread.start()
    assert waiting.wait(2)
    session.close()
    thread.join(2)
    assert not thread.is_alive() and results == ['cancelled'] and f.cleaner._command is None
    assert manager.status['state'] == 'closed'


def test_new_session_survives_old_session_repeated_close(tmp_path):
    f = fixture(tmp_path)
    first = f.cleaner.command_session(f.config, 'first')
    first.close()
    second = f.cleaner.command_session(f.config, 'second')
    first.close()
    assert second.prepare() == 'ready' and f.cleaner._command is second
    f.cleaner.close()
    assert f.managers[-1].status['state'] == 'closed'
    assert second.edit_selection('Text.', 'Make shorter.').reason == 'cancelled'
    assert f.cleaner.command_session(f.config, 'third') is None and not f.cleaner.warm()


def test_close_during_stream_drops_complete_late_output(tmp_path):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    assert session.prepare() == 'ready'
    f.managers[0].model.on_request = f.cleaner.close
    assert session.edit_selection('I wanted to say the file arrived.', 'Make shorter.').reason == 'cancelled'
    assert len(f.managers[0].model.calls) == 1 and f.managers[0].status['state'] == 'closed'


@pytest.mark.parametrize('when', ['before', 'during'])
def test_edit_cancellation_retires_temporary_owner_without_requiring_a_later_caller_close(tmp_path, when):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    assert session.prepare() == 'ready'
    cancelled = [when == 'before']
    f.managers[0].model.on_request = lambda: cancelled.__setitem__(0, True)
    reply = session.edit_selection('I wanted to say the file arrived.', 'Make shorter.',
                                   cancelled=lambda: cancelled[0])
    assert reply.reason == 'cancelled' and reply.text is None
    assert f.cleaner._command is None and f.managers[0].status['state'] == 'closed'
    assert len(f.managers[0].model.calls) == (0 if when == 'before' else 1)
    assert f.cleaner.warm()
    session.close()
    assert f.managers[-1].status['state'] == 'ready'
    f.cleaner.close()


def test_factory_exception_releases_reserved_task_without_enabling_cleanup(tmp_path):
    f = fixture(tmp_path, enabled=False)
    def broken(config):
        raise OSError('private path')
    f.cleaner._manager_factory = broken
    session = f.cleaner.command_session(f.config, 'fixture')
    assert session.prepare() == 'unavailable' and f.cleaner._command is None
    assert f.cleaner.clean('Text.') == (None, 'disabled')


def test_concurrent_close_keeps_admission_reserved_until_manager_retirement_is_initiated(tmp_path):
    f = fixture(tmp_path)
    session = f.cleaner.command_session(f.config, 'fixture')
    assert session.prepare() == 'ready'
    closing, release = threading.Event(), threading.Event()
    close = f.managers[0].close
    def blocked():
        closing.set()
        assert release.wait(3)
        close()
    f.managers[0].close = blocked
    thread = threading.Thread(target=session.close)
    thread.start()
    assert closing.wait(2)
    session.close()
    assert f.cleaner.command_session(f.config, 'next') is None and not f.cleaner.warm()
    release.set()
    thread.join(2)
    assert not thread.is_alive() and f.cleaner._command is None
    assert f.events.count(('close', 0)) == 1


def test_actual_managers_and_process_slot_refuse_both_switches_until_old_exit_is_observed(tmp_path, rig):
    base = rig.manager
    managers = []
    def factory(config):
        manager = SidecarManager(config, resolver=base._resolver, verify=base._verify,
            capability_check=base._capable, process_factory=base._process_factory,
            client_factory=base._client_factory, clock=base._clock, timer_factory=base._timer,
            port_factory=base._port_factory, waiter=base._wait, process_slot=base._process_slot)
        managers.append(manager)
        return manager
    cfg = LocalLLMConfig(enabled=True, model_path=str(base.config.model_path), prepare_prompt=False)
    cleaner = LocalLLMCleaner(cfg, manager_factory=factory,
        client_factory=lambda manager, **kwargs: SimpleNamespace(manager=manager))
    command_model = tmp_path / 'command.gguf'
    command_model.write_bytes(b'authored fake weight')
    try:
        assert cleaner._get_client().manager.prepare()
        old = rig.processes[0]
        old.stubborn = True
        session = cleaner.command_session(SidecarConfig(command_model), 'fixture')
        command = session._get_manager()
        assert not command.prepare() and len(rig.processes) == 1
        assert command.status['reason'] == 'another_manager_active'
        old.code = 1
        rig.clock.advance(1)
        assert command.prepare() and old.closed and len(rig.processes) == 2
        rig.processes[1].stubborn = True
        session.close()
        normal = cleaner._get_client().manager
        assert not normal.prepare() and len(rig.processes) == 2
        rig.processes[1].code = 1
        rig.clock.advance(1)
        assert normal.prepare() and len(rig.processes) == 3 and rig.processes[1].closed
        session.close()
        assert normal.ready  # A stale command cannot terminate its successor.
    finally:
        for process in rig.processes:
            process.stubborn = False
        cleaner.close()
        for manager in managers:
            manager.close()


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan'), True, '65', 186])
def test_invalid_startup_budget_is_rejected_before_runtime_creation(tmp_path, timeout):
    f = fixture(tmp_path)
    with f.cleaner.command_session(f.config, 'fixture') as session:
        with pytest.raises(ValueError):
            session.prepare(timeout=timeout)
        assert not f.events
