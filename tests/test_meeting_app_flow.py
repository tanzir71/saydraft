"""App seams on disposable CI: only owned Qt widgets, fake capture/model ports."""

from types import SimpleNamespace as NS

import pytest

from saydraft.app import SaydraftApp, WorkerController
from saydraft.meetings.request import CaptureRequest
from tests.test_history_window import qt_modules
from tests.test_meeting_controller import rig


@pytest.fixture
def subject(tmp_path):
    qt = qt_modules()
    f = rig(tmp_path)
    app = SaydraftApp(argv=[])
    app.controller = WorkerController(NS())
    app.controller.core = f.worker
    calls, callbacks = [], []
    app.qt_app = NS(quit=lambda: calls.append('quit'))
    app.qt_modules = NS(QtCore=NS(QTimer=NS(singleShot=lambda delay, callback: callbacks.append(callback))))
    app.tray = NS(set_state=lambda state: calls.append(('tray', state)),
                  show_notification=lambda text: calls.append(('notification', text)))
    app._show_hub = lambda page: calls.append(('hub', page))
    yield NS(qt=qt, f=f, app=app, calls=calls, callbacks=callbacks)
    f.controller.cancel()
    if f.executor.jobs:
        f.executor.drain()
    if app.meeting_capsule is not None:
        from dataclasses import replace
        app.meeting_capsule.accept_status(replace(f.controller.latest, capture_stopped=True, phase='cancelled'))
        app.meeting_capsule.close()
        app.meeting_capsule.deleteLater()
    if app.meeting_setup is not None:
        app.meeting_setup.close()
        from tests.test_meeting_setup_ui import settle
        settle(lambda: not app.meeting_setup._inflight and app.meeting_setup.task is None)
        app.meeting_setup.deleteLater()
    qt.QtWidgets.QApplication.instance().processEvents()




def present(s):
    assert s.app.controller.request_meeting(CaptureRequest(consent=True, max_seconds=30))
    status = s.f.controller.latest
    s.app._meeting_status(status)
    for _ in range(4):
        s.qt.QtWidgets.QApplication.instance().processEvents()
    assert s.f.controller.active.indicator.is_set()
    return status


def test_app_paints_indicator_before_admission_and_view_notes_does_not_activate_the_scratchpad(subject):
    s = subject
    present(s)
    assert not s.f.owner.started and s.app.meeting_capsule.isVisible()
    s.f.executor.drain()
    s.app._meeting_status(s.f.controller.latest)
    s.app.meeting_capsule.primary.click()
    assert ('hub', 'Notes') in s.calls and s.f.store.active() == s.f.primary


def test_stale_queued_status_never_constructs_or_updates_a_capsule(subject):
    s = subject
    assert s.app.controller.request_meeting(CaptureRequest(consent=True))
    old = s.f.controller.latest
    s.f.controller.cancel()
    s.f.executor.drain()
    s.app._meeting_status(old)
    assert s.app.meeting_capsule is None


def test_quit_stops_and_saves_a_recording_before_closing_the_event_loop(subject):
    s = subject
    present(s)
    def started():
        assert s.app._request_quit() is False
        assert 'quit' not in s.calls and s.f.worker.busy
    s.f.owner.on_start = started
    s.f.executor.drain()
    assert 'quit' not in s.calls and s.callbacks and s.f.controller.latest.phase == 'finished'
    assert not s.f.owner.active
    s.callbacks.pop(0)()
    assert s.calls[-1] == 'quit' and len(s.f.store.list()) == 2
    assert s.f.store.active() == s.f.primary


def test_unsaved_meeting_blocks_quit_until_explicit_retry_or_discard(subject):
    s = subject
    s.f.processor.transcribe_hook = lambda: (_ for _ in ()).throw(OSError('Fixture failure'))
    present(s)
    s.f.executor.drain()
    s.app._meeting_status(s.f.controller.latest)
    assert s.app._request_quit() is False and 'quit' not in s.calls
    assert any(call[0] == 'notification' for call in s.calls)
    assert s.app.controller.discard_meeting(s.f.controller.latest)
    s.f.executor.drain()
    assert s.app._request_quit() is True and s.calls[-1] == 'quit'


def test_repeated_quit_does_not_enqueue_multiple_stop_or_timer_requests(subject):
    s = subject
    present(s)
    assert s.app._request_quit() is False
    assert s.app._request_quit() is False
    assert len(s.callbacks) == 1
    s.f.executor.drain()
    s.callbacks.pop(0)()
    assert s.calls.count('quit') == 1 and not s.f.owner.started


def test_home_setup_start_preserves_first_paint_gate_then_saves_independent_note(subject, monkeypatch):
    from saydraft.ui import meeting_setup
    from tests.test_meeting_setup_ui import inventory, settle, verified
    s = subject
    s.f.worker.services.config['app']['tier'] = 'pro'
    original = meeting_setup.MeetingSetupDialog
    monkeypatch.setattr(meeting_setup, 'MeetingSetupDialog', lambda config, **options:
        original(config, inspector=verified, devices_provider=inventory, **options))
    s.app._show_meeting_setup()
    dialog = s.app.meeting_setup
    settle(lambda: not dialog._inflight)
    dialog.refresh.click()
    settle(lambda: not dialog._inflight)
    dialog.microphone.setCurrentIndex(1)
    dialog.output.setCurrentIndex(1)
    dialog.consent.setChecked(True)
    assert dialog.start() is True
    assert not s.f.owner.started and not s.f.controller.active.indicator.is_set()
    s.app._meeting_status(s.f.controller.latest)
    settle(lambda: s.f.controller.active.indicator.is_set())
    s.f.executor.drain()
    assert s.f.controller.latest.phase == 'finished' and s.f.store.active() == s.f.primary
    assert len(s.f.store.list()) == 2


def test_home_action_during_active_meeting_presents_existing_capsule(subject, monkeypatch):
    from saydraft.ui import meeting_setup
    s = subject
    present(s)
    monkeypatch.setattr(meeting_setup, 'MeetingSetupDialog', lambda *args, **kwargs:
        pytest.fail('Active meeting must not open another setup'))
    s.app._show_meeting_setup()
    assert s.app.meeting_setup is None and s.app.meeting_capsule.isVisible()


def test_worker_config_review_is_an_independent_snapshot(subject):
    s = subject
    snapshot = s.app.controller.meeting_config()
    snapshot['labs']['notetaker'] = False
    assert s.f.worker.services.config['labs']['notetaker'] is True
