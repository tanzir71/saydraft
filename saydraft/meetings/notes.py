"""Reviewable Markdown meeting notes, saved independently with retry-safe IDs."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import re
import uuid

from saydraft.data.notes import MAX_NOTE_BYTES, NoteConflict
from .summary import MeetingSummary, decode_summary
from .transcription import MeetingTranscript, _text

_ISSUES = {
    'incomplete_capture': 'Recording ended incompletely; some audio may be missing.',
    'audio_gap': 'Audio capture reported missing samples.',
    'capture_failed': 'Audio capture failed before the recording was complete.',
    'invalid_audio': 'Some captured audio could not be used.',
    'device_unavailable': 'An audio device could not be opened.',
    'transport_failed': 'Audio delivery from the recording process failed.',
    'speaker_analysis_failed': 'Speaker analysis failed; speaker labels are unavailable.',
    'recognition_failed': 'A speech segment could not be transcribed.',
    'empty_recognition': 'A detected speech segment returned no words.',
    'invalid_recognition': 'A speech segment returned unusable text.',
    'vad_failed': 'Speech detection failed for part of a track.',
    'vad_unavailable': 'Speech detection could not start for a track.',
}


def _inline(value):
    # Notes currently display plain text, but exported Markdown must not turn
    # recorded/model-provided text into HTML, links, images or extra sections.
    return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', ' '.join(value.splitlines()))


def _stamp(seconds):
    milliseconds = round(seconds * 1000)
    minutes, seconds = divmod(milliseconds // 1000, 60)
    return f'{minutes:02}:{seconds:02}.{milliseconds % 1000:03}'


def _evidence(citations):
    return '; '.join(f'[u{citation.utterance}] “{_inline(citation.quote)}”' for citation in citations)


def render_meeting_note(transcript, summary=None, *, created_at=None):
    if (type(transcript) is not MeetingTranscript or not transcript.utterances
            or type(transcript.duration) not in (int, float) or not math.isfinite(transcript.duration)
            or transcript.duration <= 0 or type(transcript.capture_complete) is not bool):
        raise ValueError('A meeting note requires a valid nonempty transcript')
    sources = {}
    for part in transcript.utterances:
        if (type(part.id) is not int or part.id < 1 or part.id in sources or _text(part.text) is None
                or part.track not in ('microphone', 'desktop')
                or type(part.start) not in (int, float) or type(part.end) not in (int, float)
                or not math.isfinite(part.start) or not math.isfinite(part.end)
                or not 0 <= part.start < part.end <= transcript.duration + .001
                or any(type(n) is not int or not 0 <= n < 32 for n in part.speakers)
                or type(part.model_id) is not str or not re.fullmatch(r'[a-z0-9.-]{1,128}', part.model_id)
                or part.language is not None and (type(part.language) is not str or not re.fullmatch(
                    r'[A-Za-z0-9-]{1,24}', part.language))):
            raise ValueError('Invalid meeting transcript entry')
        sources[part.id] = part
    if summary is not None:
        if type(summary) is not MeetingSummary:
            raise ValueError('Invalid meeting summary')
        summary = decode_summary(json.dumps(asdict(summary), ensure_ascii=False), sources)
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        date = datetime.fromisoformat(created_at)
        if date.tzinfo is None:
            raise ValueError('Meeting note time must include its timezone')
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid meeting note timestamp') from error
    lines, size = [], 0
    def add(value=''):
        nonlocal size
        size += len(value.encode('utf-8')) + 1
        if size > MAX_NOTE_BYTES:
            raise ValueError('The meeting note exceeds the 1 MiB Notes limit; the transcript is preserved for recovery')
        lines.append(value)
    add(_inline(summary.title if summary else 'Meeting notes'))
    add('=' * 24)
    add()
    add(f'Note created: {date.isoformat(timespec="seconds")}')
    add(f'Duration: {_stamp(transcript.duration)}')
    add('Capture: ' + ('complete' if transcript.capture_complete else 'incomplete'))
    add('Analysis: ' + ('complete' if transcript.complete else 'incomplete; review the issues below'))
    add('Times and speaker labels are approximate. Speaker numbers identify acoustic clusters, not named people.')
    add()
    if transcript.issues:
        add('## Incomplete sections')
        for issue in transcript.issues:
            message = _ISSUES.get(issue.reason, 'Part of this meeting could not be processed.')
            add(f'- {_inline(message)} ({_inline(issue.track)} {_stamp(issue.start)}–{_stamp(issue.end)})')
        add()
    if summary:
        add('Generated locally. Review names, dates, decisions and owners against the transcript.')
        add()
        add('## Summary by topic')
        for topic in summary.topics:
            add(f'- **{_inline(topic.topic)}:** {_inline(topic.summary)}')
            add('  Evidence: ' + _evidence(topic.evidence))
        add()
        add('## Decisions')
        for item in summary.decisions:
            add('- ' + _inline(item.text))
            add('  Evidence: ' + _evidence(item.evidence))
        if not summary.decisions:
            add('None identified in this summary.')
        add()
        add('## Next steps')
        for item in summary.next_steps:
            add(f'- [ ] {_inline(item.task)} — Owner: {_inline(item.owner) if item.owner else "Unassigned"}')
            add('  Evidence: ' + _evidence(item.evidence))
        if not summary.next_steps:
            add('None identified in this summary.')
    else:
        add('## Summary unavailable')
        add('The local summary could not be completed. The transcript is preserved below.')
    add()
    add('## Transcript')
    for part in transcript.utterances:
        speakers = ', '.join(f'Speaker {number + 1}' for number in part.speakers) or 'Unknown speaker'
        if len(part.speakers) > 1:
            speakers += ' (shared interval; attribution uncertain)'
        add(f'- **[u{part.id}] {_stamp(part.start)}–{_stamp(part.end)} · {speakers} · {part.track}:** {_inline(part.text)}')
    add()
    add('## Recognition sources')
    for model, language in sorted({(part.model_id, part.language or 'undetermined') for part in transcript.utterances}):
        add(f'- {_inline(model)} · {_inline(language)}')
    return '\n'.join(lines) + '\n'


@dataclass(frozen=True)
class MeetingNoteDraft:
    id: str
    body: str

    def __post_init__(self):
        if (type(self.id) is not str or len(self.id) != 32 or uuid.UUID(self.id).hex != self.id
                or type(self.body) is not str or not self.body or len(self.body.encode('utf-8')) > MAX_NOTE_BYTES):
            raise ValueError('Invalid meeting note draft')

    @classmethod
    def create(cls, transcript, summary=None, *, created_at=None):
        return cls(uuid.uuid4().hex, render_meeting_note(transcript, summary, created_at=created_at))

    def save(self, store):
        """Worker-only; retry the same draft without duplicates or Scratchpad activation."""
        previous = store.get(self.id)
        if previous is not None:
            if previous.kind == 'meeting' and previous.body == self.body:
                return previous
            raise NoteConflict()
        try:
            return store.save(self.id, self.body, kind='meeting', expected_revision=0, activate=False)
        except NoteConflict:
            # A concurrent retry may have committed this exact immutable draft.
            previous = store.get(self.id)
            if previous is not None and previous.kind == 'meeting' and previous.body == self.body:
                return previous
            raise
