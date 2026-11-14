from types import SimpleNamespace as NS

from saydraft.meetings import summary as module
from saydraft.meetings.summary import SummaryReply
from tests.test_command_session import fixture


def test_meeting_summary_uses_the_exclusive_existing_lease_and_bounded_meeting_budgets(tmp_path, monkeypatch):
    f = fixture(tmp_path, enabled=False)
    calls = []
    def client(manager, **options):
        def summarize(transcript, **arguments):
            calls.append((transcript, arguments))
            return SummaryReply('fixture-summary', 'ok', 1)
        return NS(summarize=summarize)
    monkeypatch.setattr(module, 'SummaryClient', client)
    with f.cleaner.command_session(f.config, 'fixture-meeting-model') as session:
        assert session.prepare() == 'ready'
        assert session.summarize_meeting('public fixture', timeout=300, total_seconds=900).reason == 'ok'
        assert f.cleaner.clean('ordinary dictation') == (None, 'busy')
    assert calls[0][0] == 'public fixture' and calls[0][1]['timeout'] == 300 and calls[0][1]['total_seconds'] == 900
    assert f.cleaner._command is None


def test_late_meeting_completion_after_lease_cancellation_is_discarded(tmp_path, monkeypatch):
    f = fixture(tmp_path, enabled=False)
    session = f.cleaner.command_session(f.config, 'fixture-meeting-model')
    def client(manager, **options):
        def summarize(*args, **kwargs):
            session.close()
            return SummaryReply('late fixture summary', 'ok', 1)
        return NS(summarize=summarize)
    monkeypatch.setattr(module, 'SummaryClient', client)
    reply = session.summarize_meeting('public fixture')
    assert reply.summary is None and reply.reason == 'cancelled' and f.cleaner._command is None


def test_cancelled_meeting_cannot_construct_a_late_summary_manager(tmp_path):
    f = fixture(tmp_path, enabled=False)
    session = f.cleaner.command_session(f.config, 'fixture-meeting-model')
    assert session.summarize_meeting('public fixture', cancelled=lambda: True).reason == 'cancelled'
    assert not f.managers and f.cleaner._command is None
