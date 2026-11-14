from dataclasses import replace
import json
import uuid

import pytest

from saydraft.data.notes import NoteConflict, NoteStore
from saydraft.meetings.notes import MeetingNoteDraft, render_meeting_note
from saydraft.meetings.summary import decode_summary
from saydraft.meetings.transcription import AnalysisIssue
from tests.test_meeting_summary import summary_value, transcript

DATE = '2026-11-14T14:30:00+00:00'


def summary():
    return decode_summary(json.dumps(summary_value()), {part.id: part for part in transcript().utterances})


def test_markdown_note_contains_topics_decisions_owners_evidence_timed_speakers_and_provenance():
    body = render_meeting_note(transcript(), summary(), created_at=DATE)
    for text in ('Launch planning', '## Summary by topic', '## Decisions', '## Next steps', 'Owner: Ada',
                 'Evidence: [u2]', '## Transcript', 'Speaker 1', 'Speaker 2', 'microphone', 'desktop',
                 '00:00.000–00:01.000', '## Recognition sources', 'parakeet-fixture', 'Capture: complete'):
        assert text in body
    assert 'Ada will send the draft by Friday.' in body


def test_failed_summary_retains_transcript_and_partial_capture_and_asr_are_not_labeled_complete():
    partial = replace(transcript(), capture_complete=False, issues=(
        AnalysisIssue('desktop', 1., 2., 'audio_gap'), AnalysisIssue('desktop', 1., 2., 'recognition_failed')))
    body = render_meeting_note(partial, created_at=DATE)
    assert 'Capture: incomplete' in body and 'Analysis: incomplete' in body
    assert '## Summary unavailable' in body and 'Audio capture reported missing samples' in body
    assert 'Ada will send the draft by Friday.' in body
    assert 'None identified in this summary.' not in body


def test_recorded_markdown_and_html_stay_literal_in_exported_notes():
    part = replace(transcript().utterances[0], text='[click](https://example.com)\n# Fake section\n<script>x</script>')
    body = render_meeting_note(replace(transcript(), utterances=(part,)), created_at=DATE)
    assert '\\[click\\]' in body and '\\<script\\>' in body
    assert '\n# Fake section' not in body and '<script>' not in body


def test_overlapping_and_unknown_speakers_do_not_claim_named_identity():
    parts = (replace(transcript().utterances[0], speakers=(0, 1)), replace(transcript().utterances[1], speakers=()))
    body = render_meeting_note(replace(transcript(), utterances=parts), created_at=DATE)
    assert 'Speaker 1, Speaker 2 (shared interval; attribution uncertain)' in body
    assert 'Unknown speaker' in body


def test_save_is_independent_from_active_scratchpad_and_retries_do_not_duplicate(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    primary = store.save(uuid.uuid4().hex, 'My current Scratchpad')
    draft = MeetingNoteDraft.create(transcript(), summary(), created_at=DATE)
    first, second = draft.save(store), draft.save(store)
    assert first.id == second.id == draft.id and first.kind == 'meeting' and first.revision == 1
    assert store.active() == primary and store.get(primary.id).body == 'My current Scratchpad'
    assert len(store.list()) == 2 and first.title == 'Launch planning'


def test_retry_after_a_committed_save_reports_failure_does_not_create_another_note(tmp_path):
    actual = NoteStore(tmp_path / 'history.db')
    class FailAfterCommit:
        get = actual.get
        def save(self, *args, **kwargs):
            actual.save(*args, **kwargs)
            raise OSError('simulated notification failure')
    draft = MeetingNoteDraft.create(transcript(), created_at=DATE)
    with pytest.raises(OSError):
        draft.save(FailAfterCommit())
    assert draft.save(actual).id == draft.id and len(actual.list()) == 1


def test_retry_refuses_to_overwrite_an_independent_edit_of_the_saved_note(tmp_path):
    store = NoteStore(tmp_path / 'history.db')
    draft = MeetingNoteDraft.create(transcript(), created_at=DATE)
    saved = draft.save(store)
    store.save(saved.id, 'Owner edited this note.', kind='meeting', expected_revision=1, activate=False)
    with pytest.raises(NoteConflict):
        draft.save(store)
    assert store.get(saved.id).body == 'Owner edited this note.'


def test_save_failure_keeps_the_same_immutable_draft_for_recovery():
    class Store:
        def get(self, identifier):
            return None
        def save(self, *args, **kwargs):
            assert kwargs['activate'] is False and kwargs['kind'] == 'meeting'
            raise OSError('disk unavailable')
    draft = MeetingNoteDraft.create(transcript(), summary(), created_at=DATE)
    before = (draft.id, draft.body)
    with pytest.raises(OSError):
        draft.save(Store())
    assert (draft.id, draft.body) == before


@pytest.mark.parametrize('change', [
    lambda data: replace(data, utterances=()),
    lambda data: replace(data, duration=float('nan')),
    lambda data: replace(data, utterances=(replace(data.utterances[0], end=3.),)),
    lambda data: replace(data, utterances=(replace(data.utterances[0], speakers=(True,)),)),
    lambda data: replace(data, utterances=(replace(data.utterances[0], text='bad\0text'),)),
])
def test_invalid_or_empty_transcripts_never_produce_a_saved_meeting_draft(change):
    with pytest.raises(ValueError):
        MeetingNoteDraft.create(change(transcript()), created_at=DATE)
