# App styles

The Style page also has a separate **Translate while speaking · Labs** section.
Save an English, Spanish or Arabic output target per non-code app group, or choose
Keep recognized language. Translation additionally requires Pro, its independent
Labs toggle and the explicitly installed shared editing model. The cleanup
preview remains separate; Raw and Code bypass spoken translation. See
[Translate setup and recovery](TRANSLATE.md).

The Hub's Style page hosts the reusable matrix and cleanup preview. Its shared
Save action applies staged choices together with Settings. Native/manual Hub
acceptance remains tracked separately in the parity plan.

The recording snapshots one tone and intensity after target capture. The same
policy drives deterministic rules, prompt preparation, the request header,
need-score input, validation and History metadata. Changes to preferences do not
alter an already started recording. History recognition retries retain the saved
tone/intensity. Raw and Code keep their dedicated bypasses.

## Matrix and preview

Hub → Style shows all seven groups, three tones and four cleanup levels.
Default entries remain inherited when saved, so changing a legacy global mode
does not accidentally freeze every row at its previous level. Editing a row
selects its preview. Code's prose controls are disabled. Optional app executable,
site and legacy title inputs simulate captured metadata without reading another
application. Per-app entries remain editable in the existing Cleanup profile
editor.

The parented 180 ms timer renders the actual transcript processor with memory-only
History and simulated delivery. Snippets, final punctuation and opt-in Enter
intent use the same ordering as dictation, without recording, OS input, clipboard
access or persistent History/stats. The live preview accepts at most 4096 input
characters; longer text remains in its editor and is refused, never truncated.

The preview includes staged Dictionary terms, protected terms and replacement
pairs, including the pending form that Save would apply. It uses the same
vocabulary conversion and edit validation as the saved dictionary, without
changing the form, claiming learned words, or writing to disk. Invalid drafts
show their error instead of a result from an older dictionary. With no edits,
the running dictionary remains available so newly learned words are reflected.

**Preview language** follows the current speech settings by default. When those
settings use Auto, choose a language to simulate the recognizer's resolved
language. This choice belongs only to the preview: it does not change language
pins, download models, or run recognition. The menu shares the alphabetic language
names from Settings, including Brazilian Portuguese under `pt`. Cleanup previews
do not run spoken translation or inherit its per-group target.

Preview with current AI submits one job to the existing serial worker and refuses
while work is active. It uses the current installed cleaner, its ordinary budget
and validation, with a two-second outer deadline. A light pipeline wrapper keeps
the active dictation pipeline's result/timing metadata intact. Draft styles,
Dictionary, snippets and punctuation settings are previewed; changing model
settings requires Apply before AI preview. No download is requested. Warming, disabled, unavailable
or rejected AI keeps a labeled rules result. These interface tests do not establish
native model tone quality.

Queued QObject results carry the original request identity. New text, Dictionary,
language or settings, hidden pages and stale requests cannot replace the current
output. All 84 matrix
states match the authored goldens; tests also cover real debounce, app overrides,
saved inheritance, simulated Enter/snippets, rejected model edits, busy/shutdown,
unapplied models, active metadata preservation and GUI-thread signal wiring.
Earlier offscreen English/Bengali/Arabic matrix layouts were inspected using
installed Windows fonts. The current app uses its bundled theme/fonts and
reviewed component-gallery snapshots. The matrix and language selector fit the
minimum Hub width with larger text; vertical scrolling keeps the lower preview
controls reachable. Full native/manual acceptance and model tone quality remain
separate.

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
