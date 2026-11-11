# Local database v2

Startup migrates the Saydraft history copy in place using an additive transaction.
Before changing an existing schema, SQLite's backup API writes
`history.db.bak-<UTC timestamp>-<unique suffix>`, including committed WAL data.
Backups are retained. Newer, unsupported schema versions are refused without
modification. Failed migrations roll back their schema and data changes.

The original history columns and unknown owner columns/tables remain intact.
New columns record app identity/group, style/intensity, language, ASR/LLM choices,
timings, edits and optional audio paths. Existing `model` values are copied into
`asr_model`. Raw/cleaned text and row IDs remain identical. Audio retention is
not enabled by adding the nullable `audio_path` column.

New tables hold dictionary terms (user/protected/replacement), snippets, style
rules and daily statistics. Dictionary JSON, snippets and app-profile files are
read without modification and copied into tables. Source path/hash receipts make
imports idempotent; existing database entries are preserved. Additional profile
settings such as insertion fallbacks are retained as JSON. The current Settings
editor continues to use its existing files until the Hub migration.

History insertion and daily counters commit together, before foreground insertion.
Final insertion timing metadata is updated afterwards without changing transcript
text. Repeated timing updates apply only the difference, avoiding duplicate counters.
Daily keys use the machine's local date; backup names explicitly use UTC.

## Verification (2026-11-12)

The v1 runtime database from the actual Notepad fixture test was copied into a
separate QA directory and migrated. Its one row, raw text and cleaned text were
identical before/after and in the pre-migration backup. The source database remained
byte-for-byte unchanged. The copy and report are retained in ignored
`build/qa/p2-real-migration/`; transcript data is not committed as a test fixture.

Automated tests additionally cover v0/v1 version flags, Unicode text, unknown
owner data, WAL-backed rows, backup contents, transactional rollback, new-schema
refusal, copy-only imports, invalid-file repair, final metadata and daily counters.

## Retained audio and recognition retries

Audio retention is opt-in and off by default. Complete recordings are saved as
local float32 WAV files before recognition and linked through the existing
`audio_path` field. Failed/empty recognition can therefore remain available for
an explicit retry. Retention write failures do not prevent text recognition.

Retries append a new row, retaining the original row and shared recording.
`edits_json` records `{"type":"asr_retry","source_history_id":123}`. The source
must exist and reference the same audio to classify the row as a retry for stats.
Reprocessing adds processing time without adding dictation, word or audio totals.
Failed database writes retain recognized retry text and its audio path in the
processor's pending results. No schema version change or data deletion is needed.
