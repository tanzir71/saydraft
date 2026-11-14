"""Ask shares the revocable editing slot without changing dictation cleanup."""

import pytest

from tests.test_cleanup_streaming import DONE, frame
from tests.test_command_session import fixture


def prepared(tmp_path):
    f = fixture(tmp_path, enabled=False)
    session = f.cleaner.command_session(f.config, 'shared-editing-model')
    assert session.prepare() == 'ready'
    f.managers[0].model.chunks = [frame('{"answer":"The library opens on Saturday."}', finish='stop'), DONE]
    return f, session


def test_answer_owns_one_shared_model_and_cleanup_stays_off(tmp_path):
    f, session = prepared(tmp_path)
    try:
        reply = session.ask_about('The library opens on Saturday.', 'When does it open?')
        assert reply.reason == 'ok' and reply.text == 'The library opens on Saturday.' and reply.stream_complete
        assert f.cleaner.clean('Words') == (None, 'busy')
        assert f.cleaner.command_session(f.config, 'second') is None
        assert len(f.managers) == 1
    finally:
        session.close()
    assert f.managers[0].status['state'] == 'closed'
    assert f.cleaner.clean('Words') == (None, 'disabled')


@pytest.mark.parametrize('when', ['before', 'during_template', 'during_stream'])
def test_ask_cancellation_discards_late_answer_and_releases_only_its_owner(tmp_path, when):
    f, session = prepared(tmp_path)
    cancelled = [when == 'before']
    model = f.managers[0].model
    if when == 'during_template':
        model.on_request = lambda: cancelled.__setitem__(0, True)
    if when == 'during_stream':
        def chunks():
            yield frame('{"answer":')
            cancelled[0] = True
            yield frame('"Late answer"}', finish='stop')
            yield DONE
        model.chunks = chunks()
    reply = session.ask_about('Public source.', 'Question', cancelled=lambda: cancelled[0])
    assert reply.reason == 'cancelled' and reply.text is None
    assert f.cleaner._command is None and f.managers[0].status['state'] == 'closed'
    successor = f.cleaner.command_session(f.config, 'next')
    assert successor.prepare() == 'ready'
    session.close()
    assert f.managers[-1].status['state'] == 'ready'
    successor.close()


def test_app_shutdown_during_request_discards_answer_and_closes_model(tmp_path):
    f, session = prepared(tmp_path)
    f.managers[0].model.on_request = f.cleaner.close
    reply = session.ask_about('Public source.', 'Question')
    assert reply.reason == 'cancelled' and reply.text is None
    assert f.managers[0].status['state'] == 'closed'
    assert f.cleaner.command_session(f.config, 'next') is None
