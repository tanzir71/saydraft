# Dictionary correction learning

P5.6 is in progress. Offline frequency filtering and pure span alignment are
implemented. The native original-field reader and asynchronous owner are
implemented, including session delivery and result polling. Suggestion presentation,
explicit Add, optional Auto-add, revision-scoped Undo and Settings controls are
implemented. Both learning settings default off.
Manual desktop acceptance remains deferred after Computer Use was stopped.

## Suggestions and actions

Settings → Dictionary exposes **Suggest words from my corrections** and a separate
**Auto-add to dictionary** control, available when suggestions are enabled. The
default shows an Add/Dismiss toast for the latest valid suggestion. Auto-add
queues the same store operation and shows Undo after a successful save. Toasts
show without requesting activation, use plain text and directional isolates for
candidate words, and dismiss after 12 seconds, Dismiss or Escape. They do not
use the logged notification channel. Visible native focus behavior still needs
manual acceptance.

A suggestion can be claimed only once and must still match the current session
and observation epoch. Saves run on the transcript executor, reload the current
cleaner's glossary and never create History entries. Cancellation or Settings
replacement invalidates a queued Add before it starts. Once a write begins, its
saved receipt still produces Undo; a later recording retires suggestions without
hiding an actual saved change's Undo. Busy Undo remains available for retry;
manual claims/newer changes cause a safe no-op. A cleanup reload failure does not
discard an already committed receipt. Closed presenters reject queued results.

QObject slots receive suggestion/result signals through explicit queued
connections on the GUI thread. Tests cover Add/Auto-add/Undo, cancellation,
default-off settings, stale results, busy/rejected queues, write/reload failures,
timer/Escape dismissal and GUI-thread delivery. Offscreen English/Arabic/Bengali
states were inspected. The offscreen font database needs explicit loading of the
existing Windows Segoe UI and Nirmala fonts; Bengali/Arabic glyph checks pass
with those fonts. No proprietary font is redistributed. P6 font bundling remains.

## Atomic dictionary edits

The glossary JSON remains the live dictionary until the planned Hub migration;
the SQLite v2 dictionary table remains its earlier copy-only import. All current
app glossary writers now use `dictionary.store`: a bounded strict read, a shared
per-path process lock, a same-directory temporary file, flush/fsync and atomic
replacement. Unknown owner fields, protected terms and replacements survive a
single-term edit. Invalid or oversized files are refused without overwriting
them. A final byte-revision comparison refuses external edits observed during
staging. This is not a cross-process editor lock.

Learning returns a dictionary-path-bound receipt with a unique per-term revision.
Undo checks both the revision and exact current spelling, removes only that
addition or restores its earlier capitalization, and retains unrelated changes.
A manual Add claims the word and revokes the old learning receipt. A newer
learning change also revokes it; restoring a previous learned spelling creates a
fresh revision, preventing an older Undo from becoming valid again. The small
`_saydraft_learning` metadata map records learned provenance, without retaining
the original field span or the mistaken word. Receipts stay in memory.

Settings hides that internal map. An unchanged dictionary editor refreshes from
disk without writing over newer learning. An edited stale snapshot is refused
before applying configuration, leaving the editor text available. Valid edits
retain provenance only for unchanged terms; they cannot resurrect a revoked
receipt. Reload Dictionary explicitly replaces the editor with the latest saved
version, including after a conflict. Invalid JSON must be repaired on disk before
reloading; it is never silently replaced by an empty dictionary.
The visible actions use these store methods; observation remains disabled by
default.

## Session delivery

`dictation.learn_corrections` is a persisted, default-off integration flag.
`dictation.auto_add_dictionary` separately defaults off. Default profiles do
not start the observation owner. When enabled, the session prepares after the
recorder starts. Pending lease length follows the configured recording cap plus
60 seconds, bounded at 3660 seconds. History-only notes do not prepare.

The inserter calls the optional reservation hook inside delivery, after the
existing clipboard delay and before its final safety check and keyboard call.
Typing, native paste, legacy paste and guarded typing fallback use the same
protocol. Callback failure cannot bypass the field/cancellation checks or change
the insertion result. Raw and cleaned History remain saved before delivery.
Successful insertion commits the exact cleaned text and resolved language;
failure, short/silent recording, cancelled arming, Settings changes and shutdown
retire the observation. History reinsertion uses a fresh attempt with a 60-second
lease and the configured language, without creating another History row. An
unresolved Auto language yields no suggestion.

A parented 250 ms Qt timer checks only a plain completion event. At most one
alignment task per observation is submitted to the existing serial executor;
polling does not mark dictation busy or wait for UIA. The result is a separate
`dictionary_suggestion` object signal, never the notification channel that is
logged. Generation and observation-epoch checks revoke late consumers and queued
UI events. Only the latest candidate's individual words remain available for a
future presentation/action handler; full field spans are not retained there.

The six-case native probe now includes the real session worker, critical and
learning UIA owners, SQLite History, an authored ASR/recorder stub, and checked
memory delivery that mutates only its own invisible EDIT. It verifies one
Kubernetes suggestion, History-before-input ordering, clipboard-port restoration
and owner/serial retirement. It uses no microphone, real ASR, OS input or owner
clipboard. This is integration evidence, not manual Notepad or end-to-end latency
acceptance. That session case also saves the suggestion through the serial worker,
verifies the reloaded glossary, and undoes it with no additional History row.

## Background scheduling

`ObservationWorker` owns one additional fixed, windowless MTA for optional
learning. Critical `BoundedUIA` context/insertion queries keep their existing
owner and deadlines. A stalled learning provider cannot occupy that owner.
Neither worker starts replacements after caller timeout or terminal failure.
The context creates the learning owner lazily and closes both without joining
either on the GUI thread. All element/range creation, use and retirement remains
on each object's owning MTA.

Preparation reads only the verified insertion edges while the user speaks; no
transcript is available or retained yet. A pending lease can cover the recording
cap plus processing time, at most 3660 seconds. Preparation itself has a separate
two-second budget. Before OS insertion, `reserve()` accepts only an already-ready
snapshot. An unready snapshot is cancelled; it cannot capture after paste.
Successful delivery calls `commit()` with the final inserted text and insertion
timestamp. Neither call waits for native UIA. Failed/cancelled delivery must cancel
its ticket. Session wiring above uses these ports only when the integration flag
is explicitly enabled.

The owner polls only the original field's metadata until focus leaves or 15
seconds from insertion, then reads its bounded span once. An edit already present
at baseline confirmation returns that span immediately for the same strict
alignment policy, so a quick correction is not lost. Unknown/changed metadata or
edges return no content. Confirmed scope retirement remains 16 seconds from
insertion. Completed results are consumed once and retained at most 30 seconds;
idle worker frames retain no consumed result. New tickets revoke old work and
payloads; there is one scope and no request backlog. Cancellation and shutdown
invalidate late provider results between reads.

The native probe includes an asynchronous case with two independent MTA clients:
the critical reader verifies its owned field while learning is blocked, then
preparation/reservation/commit/correction completes and both clients retire.
The control-plane calls measured about 0.04–0.05 ms in this fixture; native work
still takes the times below in the background. These are helper measurements,
not full microphone/ASR/clipboard latency or browser acceptance.

One initial PR CI run failed in the older `probe_uia_reader` fixture with a COM
error; the parallel push run passed. That fixture now uses a standard invisible
window rather than its previous clipboard-oriented HWND_MESSAGE host, and reports
the initialization/acquisition/policy/close stage and HRESULT without provider
messages. Tests surface the full bounded report on failure. The original report
lacked that detail, so the exact COM cause is unproven. No production timeout or
retry policy changed; the final local full rerun passes 2093 tests with five skips.

## Original-field reader

`context/tracked_edit.py` owns one pending/confirmed insertion on the UIA MTA.
It captures hashes and lengths of the text on each side of the actual selection,
then confirms that a fresh read contains exactly those edges and the inserted
text. The replaced selection is not read. Only the inserted text, field identity,
edge hashes/lengths and timestamp remain in the observation. No COM proxy leaves
the MTA; foreign-thread mutation is refused. Callers must clear cancelled work
and drive idle expiry. Prepared leases expire at their bounded deadline;
confirmed scopes retire at 16 seconds, with a final check due at 15 seconds or
when that field loses focus.

Checks read only the original field. Fresh metadata is obtained from its handle
or an exact runtime-ID lookup under the original window. Every bounded text read
checks the window PID, runtime ID, ownership and an explicit non-password state
from the newly fetched metadata batch. The cache contains no Name/Value/text.
No newly focused element is requested after capture. Missing/changed/unreadable
fields, unknown focus/password state, cancellation, expired scope, malformed
Unicode or changed edges retire without returning content. The final read is
one-shot, at most 8192 UTF-16 units; the inserted span is capped at 4096. Controls
without a usable TextPattern selection are skipped, including ValuePattern-only
controls whose caret cannot be established.

Microsoft documents [range invalidation after edits](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-textpattern-overview).
The owned Win32 probe also found that a retained element and BuildUpdatedCache
returned stale text/password state after a second edit. Reacquiring the same
handle returned current state; no retained text ranges are used after edits.
The reader uses [metadata batching](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-cachingforclients)
on each fresh element, rather than trusting a retained cache.

`tools/probe_tracked_edit.py` exercises native EDIT controls, public fixture
replacement/correction, an emoji boundary and password changes with no desktop
input, active-app access or clipboard access. The runtime-ID route is forced on
an owned standalone EDIT window: this verifies the lookup API, not a real browser
provider. An invisible child is absent from its parent's enumerated UIA subtree,
so that earlier diagnostic is retained as a failed probe. Current successful
captures take about 0.8–1.0 seconds, confirmation 0.4–0.6 and final check 0.5–0.7
on this fixture. These timings exceed the existing 500 ms caller budget in some
stages. The separate asynchronous owner addresses scheduling without increasing
critical-query budgets. Notification/store integration remains;
no manual Notepad/browser acceptance is claimed. Fixture selection is established
after the provider exists; earlier startup/baseline refusals remain in diagnostic
reports rather than being hidden by retries of the code under test.

## Alignment policy

`suggest_correction(inserted, current, language)` accepts two already-scoped
insertion spans. It does not read a field, prove field identity or modify the
dictionary. Exactly one word may change; every character outside that word must
stay identical, including punctuation and whitespace. Returned offsets index the
original Python strings, while the candidate spelling is NFC. The native observer
proves field identity and derives its span using UIA endpoints and edge hashes;
these Python offsets must not be passed directly to UIA.

Words include Unicode letters/marks and internal apostrophes/hyphens. Input is
limited to 4096 characters, 512 words, and 3–64 characters per changed word. A
candidate must be uncommon and within one edit (two for words of at least six
characters), counting adjacent transposition. English ASCII names also have a
bounded [Soundex](https://www.archives.gov/research/census/soundex) route: matching
codes with at least two consonant digits, at most three edits and a length
difference of at most two. Independent National Archives examples verify the
coding rules. This heuristic is correction evidence, not pronunciation proof.

Case-only edits require name-like casing. Common words require an explicitly
known proper term or an exact built-in proper spelling (iPhone, iPad, iOS, macOS,
eBay, YouTube, GitHub, GitLab, OpenAI, WhatsApp). Arbitrary mixed casing such as
`tHe` is insufficient. Uppercase emphasis and casefold
expansions are skipped. The known-term scan is capped at 1024 entries. Unicode
normalization, Arabic vowel/tatweel and apostrophe-presentation changes alone
never create a word.

Known double-quoted/backtick literals, address shapes, numbers, identifier fragments, format-control
boundaries, mixed scripts, additions/deletions and broader rewrites are skipped.
Only single-script spaced alphabetic words are eligible; Chinese, Japanese,
Korean and other languages needing segmentation currently skip learning. Their
dictation support is unchanged. Unknown/Auto or unavailable frequency data also
skips. The tests include exact Kubernetes evidence with bundled data, Bengali and
Arabic corrections, raw Unicode offsets and the refusal cases above. No desktop
field observation is enabled by this foundation.

## Common-word filter

`saydraft/dictionary/frequency.py` reads bundled membership sets derived from
[wordfreq 3.1.1](https://pypi.org/project/wordfreq/3.1.1/), by **Robyn Speer**.
The 42 small lists contain entries occurring at least once per million words in
wordfreq's source data. They include English, Bengali and Arabic. This is a
conservative common-word filter, not a spell checker or a measure of whether a
correction is right. An absent word alone must never trigger learning.

Lookup normalizes Unicode compatibility forms and case, straightens curly
apostrophes, and removes Arabic vowel marks/tatweel. Bengali vowel marks remain.
Learned spelling must retain the user's original NFC form. Region tags resolve to
the base language; Norwegian, Serbo-Croatian and Filipino aliases share lists.
An unknown language, missing list or failed size/hash/decompression check returns
unavailable; callers must skip suggestions. Auto without a resolved language
must also skip. The loader caches at most four language sets and never writes to
the user's profile or accesses the network. No wordfreq runtime dependency or
extra model download is needed. The existing bundle includes the entire assets
directory.

## Dataset provenance and reproduction

`assets/dictionary/frequency/manifest.json` pins the source wheel URL, size and
SHA-256, original member names, all output hashes/counts and retained notices.
The adapted membership data remains **CC-BY-SA-4.0**; Saydraft's own Python code
remains MIT. The generator flattens frequency bins, omits empty/whitespace keys,
normalizes/deduplicates/sorts
lookup keys and writes gzip with a zero timestamp. Original wordfreq license and
all credits/citations following its published License section are retained,
including Marc Brysbaert and the other SUBTLEX authors. SUBTLEX is freely
available data. Google Books, Leeds, Wikipedia, ParaCrawl and OpenSubtitles
attribution remains in the retained notice. Full Apache-2.0 and CC-BY-SA-4.0 texts
are bundled.

Use development requirements (including msgpack 1.1.1), a local verified source
wheel and the complete CC license text. The generator performs no downloads,
does not import/install wordfreq, and refuses an existing output directory:

```powershell
python -m tools.build_frequency_lists --wheel <local-wheel> --license <local-CC-BY-SA-4.0.txt> --output <fresh-directory>
```

The CC text was retrieved from Creative Commons' own pinned
[source revision](https://github.com/creativecommons/cc-legal-tools-data/blob/a0dac18d1a773b4cdb7d8dd5d9bf4efab7901030/docs/licenses/by-sa/4.0/legalcode.txt)
because direct HTTP retrieval of the canonical text returned 403. Its canonical
[license URL](https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt) and
complete byte hash remain in the manifest. Tests verify all 42 distributed
language sets and notice hashes offline, common words in English/Bengali/Arabic,
unknown/corrupt-data refusal, bounded caching and unpinned-source rejection.
