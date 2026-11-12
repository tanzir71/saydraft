# App styles

P5.7's engine is implemented. The Style matrix UI and shared live preview remain
pending, so P5.7 acceptance stays open. No desktop control has resumed.

The recording snapshots one tone and intensity after target capture. The same
policy drives deterministic rules, prompt preparation, the request header,
need-score input, validation and History metadata. Changes to preferences do not
alter an already started recording. History recognition retries retain the saved
tone/intensity. Raw and Code keep their dedicated bypasses.

## Selection

The groups are Messages, Work chat, Email, Docs & notes, Code, AI chat and Other
(`messages`, `work_chat`, `email`, `docs`, `code`, `ai_chat`, `general`). Defaults
are Casual, except Formal for Email and Docs & notes. Global legacy Email/Chat
profiles still supply their tone until a group or app preference overrides it.
Legacy Balanced/Aggressive modes supply intensity 3/4 when no intensity is saved.

`dictation.styles` stores partial group preferences, for example:

```json
{"work_chat": {"tone": "formal", "intensity": 2}}
```

Per-app entries in the existing app-profile file accept `tone` and `intensity`,
alongside their current mode/profile/group fields:

```json
{"exe": "slack.exe", "tone": "very_casual", "intensity": 2}
```

A site selector matches an exact captured hostname hint, optionally with an exe;
it does not fetch or inspect browser pages. Executable selectors match basenames.
The first matching entry with valid cleanup fields wins. Title-only legacy
profiles keep their literal, bounded match. Per-app tone/intensity takes priority
over the group, then the legacy/default policy. Invalid values are ignored.

## Rules and model policy

| Level | Rules | Prose model |
| --- | --- | --- |
| 1 Verbatim-ish | Preserve words, repetitions and spoken numbers; normalize whitespace/punctuation spacing | Skipped |
| 2 Light | Remove hesitation fillers, normalize casing and ITN, allow document/email list layout | Optional, within the existing gate/budget |
| 3 Balanced | Also remove accidental repetition | Optional, within the existing gate/budget |
| 4 Polished | Also remove aggressive fillers, apply explicit self-corrections and spoken punctuation | Optional, within the existing gate/budget |

At levels 2–4, Formal and Casual apply standard sentence casing; Formal keeps
terminal punctuation and Casual uses the existing messaging-period policy.
Very casual preserves dictated
casing in rules, including list items; it does not force names or whole sentences
to lowercase. Mixed-case names and case-expanding letters are preserved. Both
casual tones keep questions, exclamations, protected literals and multi-sentence
punctuation. The prompt requests complete wording for Formal and conversational
wording for casual tones, with no invented slang, emoji, facts or translation.
Real model tone quality is not established by these deterministic tests.

The corpus adds 84 authored group × tone × intensity cases (472 → 556). Two
earlier intensity-1 ITN cases intentionally change from digits to the original
spoken words, matching Verbatim-ish. CI and full native bakeoff minimums now
require 556 cases. Old 432/472-case model reports do not establish current
acceptance; native positive quality/tier evidence remains pending until the app
and UI source stabilizes. The test suite also covers saved settings, selector
precedence, invalid fields, frozen sessions, Raw/Code/verbatim bypasses and
agreement between preparation, request hints, rules and History.
