"""Ask freezes only verified UIA text, including read-only sources, before UI."""

from types import SimpleNamespace as NS

import pytest

from saydraft.context.foreground import SelectedContext
from saydraft.context.selection import SelectionSnapshot
from saydraft.core.ask import capture_ask_source
from saydraft.core.interfaces import TargetContext


def rig(*, status='ready', origin='uia', read_only=True, verify='', revoke=True):
    events, current = [], [True]
    snapshot = SelectedContext(TargetContext(app_title='Public article', app_exe='browser.exe', app_group='browser'),
        SelectionSnapshot(status=status, text='Public العربية বাংলা reference.', read_only=read_only, origin=origin))
    def capture(**options):
        events.append(('capture', options))
        return snapshot
    def check(captured, **options):
        assert captured is snapshot
        events.append(('verify', options))
        return verify
    def cancel(captured):
        assert captured is snapshot
        events.append(('revoke',))
        return revoke
    context = NS(capture_selection=capture, verify_selection=check, cancel_selection=cancel)
    return NS(context=context, current=current, events=events, snapshot=snapshot)


@pytest.mark.parametrize('read_only', [True, False])
def test_readable_selection_is_frozen_and_lease_revoked_before_return(read_only):
    f = rig(read_only=read_only)
    result = capture_ask_source(f.context, current=lambda: f.current[0])
    assert result.reason == 'ready' and result.source.text == f.snapshot.selection.text
    assert result.source.app_title == 'Public article' and result.source.app_exe == 'browser.exe'
    assert f.events == [('capture', {'lease_seconds': 10, 'allow_copy': False}),
                        ('verify', {'for_write': False}), ('revoke',)]
    assert not hasattr(result.source, 'selection') and not hasattr(result.source, 'identity')


@pytest.mark.parametrize('status', ['password_field', 'empty', 'selection_too_long', 'unsupported', 'copy_pending'])
def test_unavailable_or_sensitive_selection_is_never_returned(status):
    f = rig(status=status)
    result = capture_ask_source(f.context, current=lambda: True)
    assert result.source is None and result.reason == status
    assert [event[0] for event in f.events] == ['capture', 'revoke']


@pytest.mark.parametrize('origin,reason', [('clipboard', ''), ('uia', 'password_field'), ('uia', 'selection_changed')])
def test_copy_origins_and_fresh_sensitivity_or_change_fail_closed(origin, reason):
    f = rig(origin=origin, verify=reason)
    result = capture_ask_source(f.context, current=lambda: True)
    assert result.source is None
    assert result.reason == ('unsupported' if origin == 'clipboard' else reason)
    assert f.events[-1] == ('revoke',)


def test_failed_revocation_does_not_present_a_source_with_live_selection_authority():
    f = rig(revoke=False)
    result = capture_ask_source(f.context, current=lambda: True)
    assert result.source is None and result.reason == 'selection_unavailable'


@pytest.mark.parametrize('when', ['before', 'after_capture', 'after_verify'])
def test_cancelled_capture_does_not_escape_as_a_late_ui_source(when):
    f = rig()
    if when == 'before':
        f.current[0] = False
    elif when == 'after_capture':
        old = f.context.capture_selection
        def capture(**options):
            result = old(**options)
            f.current[0] = False
            return result
        f.context.capture_selection = capture
    else:
        old = f.context.verify_selection
        def verify(*args, **options):
            result = old(*args, **options)
            f.current[0] = False
            return result
        f.context.verify_selection = verify
    result = capture_ask_source(f.context, current=lambda: f.current[0])
    assert result.source is None and result.reason == 'cancelled'
    assert not f.events if when == 'before' else f.events[-1] == ('revoke',)
