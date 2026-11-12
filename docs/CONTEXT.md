# Local foreground context

The application captures foreground HWND, title and executable basename at the
start of dictation. `GetWindowThreadProcessId` identifies the process;
[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)
uses only `PROCESS_QUERY_LIMITED_INFORMATION`. The owned process handle closes
on success and failure. The path buffer is fixed at 32768 characters; only its
basename reaches context/History, never the full path or process command line.

HWND and PID are checked again after collection. A changed/disappearing target
returns unknown context so insertion is refused. If the executable alone is
inaccessible, the stable HWND/title remain usable with the General group.
This snapshot does not replace the separate delivery focus/integrity checks.

Foreign captions use a fixed 4097-character buffer. Same-process captions are
skipped: [GetWindowTextW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtextw)
sends a GUI message for those windows, which could wait behind the worker lock.
Foreign captions do not wait for a hung target. Delivery uses a separate HWND-only
read, avoiding executable/title work on every paste check.

## Groups and browser hints

Default groups are Messages, Work chat, Email, Docs & notes, Code, AI chat and
General. Common exact executable basenames select a group; unknown executables
use General. For example Telegram selects Messages, Teams/Slack select Work chat,
Outlook selects Email, Notepad/Obsidian select Docs, and editors/terminals select
Code. Matching is case-insensitive, with no prefix or substring matches.

Chrome, Edge and Firefox may supply a title-derived `app_site` hint. The final
browser brand must match the executable and the preceding title segment must
exactly name a known service or a hostname. Gmail, Google Docs, Slack, Notion,
Teams, Discord, WhatsApp, Telegram Web, ChatGPT and Claude have default hints.
An arbitrary article mentioning a service does not match. Missing/private/PWA or
localized title suffixes may produce no hint. Titles can be spoofed: these are
formatting hints, never verified URLs, security evidence or permission checks.
There is no URL-bar access, browser automation, page fetch or network request.

## User overrides

Settings → Dictation's existing Per-app profile JSON accepts group overrides:

```json
[
  {"exe": "notepad.exe", "app_group": "general"},
  {"exe": "chrome.exe", "site": "mail.google.com", "app_group": "email"},
  {"site": "chat.example.org", "app_group": "work_chat"}
]
```

Apply reloads the profiles. Groups are `messages`, `work_chat`, `email`, `docs`,
`code`, `ai_chat` or `general`. The first valid matching entry wins; both selectors
must match when both are present. Exe selectors are exact basenames, site selectors
are exact title hints. At most the first 128 entries are scanned. Invalid entries
are ignored; a group-only entry is never a catch-all. Legacy `match`/`mode`/`profile`
entries retain their title-based cleanup behavior separately.

P5.3 remains open for UI Automation password/type/caret/selection context and
manual password-field refusal. The present adapter does not detect passwords.
Tests cover target races, unavailable processes, bounded/native handle ownership,
same-process GUI avoidance, title hints and group overrides. A quiet Windows child
repeats 50 own-process image queries with zero process-handle growth and reads no
other application's metadata.

## Capture reentry

Focused-field providers may need GUI message processing, so context capture runs
outside the session mutex. A reserved start slot remains busy until capture
finishes. A second start is refused; cancellation, release and shutdown can abort
the pending start before microphone arming. Ordinary release during ARMING still
uses the session transition even if the start callback has not returned yet.

Settings can queue a replacement without waiting for capture. A pending change
discards that start; the serial executor applies it afterward, outside the native
hotkey dispatcher that it may need to retire. Context failures release the slot,
show a generic retry notification and leave the hotkey route usable. Seven
concurrency/lifecycle cases cover these paths using a renderer held until GUI
actions return. This prepares the UIA integration; it does not supply its missing
password/caret/selection implementation or acceptance.

## UIA reader foundation

`focused_edit.py` requires an explicit non-password property before requesting
text. Unsupported/default/failed properties refuse the read. It checks focused
element identity before and after collection, rechecks the password flag, rejects
unrelated windows and discards partial text on errors. Provider exceptions and
field content are never logged. Control type and bounded runtime ID accompany
successful results. Text is limited to 1024 UTF-16 units; incomplete selection is
flagged for later commands rather than represented as a complete selection.

`uia_native.py` creates an in-process Windows UI Automation 2 client on a
windowless MTA thread, following Microsoft's [threading guidance](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Import the module on the owner thread before constructing the client on its MTA
worker. The caller owns construction/use/closure; no COM proxies cross threads.
AutoSetFocus is disabled; connection/transaction timeouts are 100 ms. Type-library
binding metadata is generated in RAM with pinned MIT-licensed comtypes 1.4.16.

TextPattern selection ranges provide text before the selection start without
moving the real selection. An active TextPattern2 caret is the fallback. Disjoint
selections and unsupported patterns provide no caret text. If a provider promotes
Character movement to a larger unit, a distant truncated document prefix is
discarded. ValuePattern alone cannot establish the caret position, so the reader
does not read an entire value and pretend it precedes the caret.

`python -m tools.probe_uia_reader --output D:\QA\New-Uia-Probe` creates invisible
password/plain EDIT controls and queries only those controls from its MTA worker.
It verifies password short-circuit, plain Edit type, idempotent COM closure, thread
exit and window destruction. It changes no focus, injects no input, opens no
clipboard and reads no active application. CI repeats the probe in a bounded
child process. Pure policy/range tests cover sensitive-state/focus races, unknown
properties, malformed IDs, bounded Unicode and range movement.

The application uses the adapter and refusal checks below. Manual active-field
acceptance remains under P5.3. Provider timeouts alone do not bound a total call
sequence; the adapter supplies the outer caller budget.

Clean immutable `097d502` passes the native own-control probe with no failures,
both worker threads exited and all owned windows closed. The original report and
SHA-256 index are retained in `eval/hardware/results/2026-11-12-uia-reader/`.
This establishes the reader on real UIA providers, not application integration or
manual active-password-field acceptance. Full local suite: 1765 pass, five explicit
native/model skips; rules 432/432, authored adversarial 100/100, Ruff/diff pass.

## Bounded request adapter

`BoundedUIA` owns one daemon MTA worker and permits one outstanding request. The
app allows 500 ms for pre-record context capture and 200 ms for metadata-only
delivery verification. Overlapping, closed or expired requests return unavailable
without adding a worker or queueing more work. An abandoned native call retains
that single slot until it returns. Expired work stops before additional text
reads; late results are discarded. Idle workers retain no completed field text.
Only immutable data crosses threads; proxy construction, reads and closure stay
on the MTA owner.

Close cancels caller waits immediately and signals worker retirement without a
GUI join. If a provider never returns, that one daemon remains until process exit;
the adapter does not claim it can terminate an arbitrary native COM call. A
background/QA wait method observes actual retirement when the call does return.
Initialization failure is terminal for that owner, with no retry loop or logged
provider exception.

The foreground adapter can copy this result into ephemeral field/type/selection
context and perform a fresh metadata-only verification of password state, runtime
ID, HWND and original PID before delivery. Verification never reads caret or
selection text. Closed adapters perform no further foreground reads. Per-app
group changes can update the provider without replacing its owner.

Nineteen adapter cases exercise caller timeout, blocked initialization, shutdown,
overlapping requests, late-text suppression, provider failures and field/window/
process changes.

## Application delivery

Windows services enable UIA and prepare the MTA owner before listening. Settings
reuse the same context/reader, update group overrides and rebind the replacement
inserter's HWND-only provider. Discarded replacement providers never start a
worker. Shutdown signals context closure before retiring hooks; configuration
after shutdown cannot create another owner.

Normal dictation persists both text versions before refusing password, unknown or
changed fields. A fresh metadata-only field guard runs before publication, paste,
typing fallback and trailing Enter. It checks password state, runtime identity,
HWND and original PID. Cancellation and Windows focus/integrity/modifiers are
checked again after any UIA wait. Windows offers no atomic field-check-and-send
operation; these checks reduce races rather than eliminate them.

History reinsertion reserves the serial worker rather than running capture or OS
delivery on the GUI. It uses the same field and cancellation checks; cancelled
queued work reads no field. Rejected queueing is shown as busy instead of claiming
delivery was queued. History-only notes remain available without an insertion
warning. `not_requested` context remains an injected legacy/test seam; production
Windows capture supplies an explicit UIA result.

Sixteen new integration/UI cases cover captured and later password changes,
clipboard preservation, skipped Enter, cancellation during verification, typing/
legacy fallback, History reinsertion and one blocked owner across Settings and
shutdown. Full local suite: 1800 pass, five explicit native/model skips; rules
432/432, authored adversarial 100/100, Ruff/diff pass. Native composed app-context
proof and active-field manual acceptance remain separate; P5.3 stays unchecked.

## Batched metadata and composed native probe

The first composed replay exposed a false refusal: separate element acquisition
and parent traversal took about 244 ms before the password query, exceeding the
original 200 ms capture budget. Both transcript versions survived with no input
or clipboard access. The original initial/diagnostic reports are retained with
the later passing proof; this was not an insertion or privacy failure.

The reader now [batches metadata](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-cachingforclients)
in each fresh GetFocusedElementBuildCache request: password flag, control type,
runtime ID and native HWND only. No Name, Value, text or patterns enter the cache.
Native HWND ancestry uses GetAncestor; HWND-less elements use a filtered UIA
parent walk. Current password/focus properties remain live checks; cached false
never replaces a fresh password check before/after reading text. Metadata-only
verification needs one final live password/focus pair and reads no field text.

`tools.probe_uia_app` composes bounded native context, the real session worker,
rules and SQLite with invisible password/plain fields. Its transcript/recorder
are authored stubs, and delivery uses a checked in-memory clipboard/keyboard.
The password case performs no text read or delivery; the plain case delivers once
only after exact raw/clean History persistence. Serial/MTA retirement and owned
window destruction are observed. It also verifies that the real focus property
refuses the inactive fixture; fixture focus selection is deliberately injected.
No active application, real clipboard, microphone, ASR, OS input or hooks are used.
Per-method timings diagnose this probe and establish no parity latency claim.

Clean immutable `db3db47` passes both composed cases with one exact History row
each, zero password text reads/deliveries, one plain delivery and observed
serial/MTA/window retirement. The original clean report plus initial refusal,
uncached timing and first passing reports/digests are retained in
`eval/hardware/results/2026-11-12-uia-app/`. Full local suite: 1812 pass, five
explicit native/model skips; rules 432/432, authored adversarial 100/100 and
Ruff/diff pass. Active-field manual acceptance remains open.

## Desktop field acceptance helper

`tools/fixtures/FieldProbe.cs` supplies a local public WinForms fixture with an
empty password-style field and a fixed plain field. It has no sign-in, submission
or saved user data. Compile with the preinstalled .NET Framework compiler, for
example `csc /target:winexe /r:System.Windows.Forms.dll /r:System.Drawing.dll
/out:D:\QA\Saydraft.FieldProbe.exe tools\fixtures\FieldProbe.cs`.
The running fixture writes its PID beside the executable.

Launch/select the fixture through Computer Use, then run
`python -m tools.probe_desktop_fields --fixture-pid <pid> --output D:\QA\New-Desktop-Field-Probe`.
Hold F9 for at least 0.5 s and release in its password field. In its plain field
press End, then hold/release F9 the same way. The observer uses actual foreground/focus/UIA and native
integrity checks, restricted to the supplied fixture PID/executable. Transcript,
microphone and delivery remain authored/in-memory stubs. It never sends keys,
opens the real clipboard or requests field content from an unrelated window.

The probe checks two exact History rows, no password text reads/delivery, one
plain text read/delivery and hook/serial/MTA retirement with zero native recovery.
It exits after completion or its bounded timeout; writing `stop.request` inside
its fresh output directory also requests graceful closure. Keep the fixture's
controls unchanged and close its window through Computer Use afterward. This
helper provides no actual ASR, microphone, OS paste, elevated-window, Win+V or
parity-latency acceptance.

Desktop attempt (2026-11-12): the fixture compiled and its two public controls
were inspected. The owner stopped Computer Use with physical Escape before the
observer started or any F9 test input. No desktop acceptance report was produced.
Keep active-field acceptance open; desktop interaction remains stopped pending an
explicit owner request to resume it. Independent repository work continues.

## Caret range availability

Caret capture distinguishes a known empty prefix/end-of-field from unsupported
or ambiguous context. A single TextPattern selection supplies known replacement
boundaries; a caret-only fallback cannot claim a known selection. Disjoint or
unsupported patterns keep layout context unknown while retaining verified field
metadata. A promoted/distant preceding range is also unknown.

After the selection, the reader moves a cloned endpoint by at most two Character
units and requests at most two UTF-16 units. Transport keeps one complete Unicode
character, or marks a broken surrogate peek unknown. The real selection never
moves. Requests check expiry/cancellation before each additional native GetText;
late/partial context is discarded. Metadata-only delivery verification reads none
of these ranges.

The before/selection/after availability flags reach cleanup in ephemeral context;
field surroundings never enter History rows. Legacy injected two-string readers
remain supported. [Caret formatting](CARET_FORMATTING.md) applies layout only at
reliable boundaries, with 40 authored golden cases. Truncated selections disable
layout. The native own-control probe checks exact formatted History/delivery;
the desktop helper now requires the plain caret at End and checks that geometry.
Desktop testing remains stopped as requested.

Paste-last uses `capture_for_insertion`, which captures the same verified
window/PID/password/control/runtime identity with `include_text=False`. No
caret/selection/body range is requested. This snapshot is frozen at the shortcut
invocation before the asynchronous History read; normal fresh metadata and OS
delivery guards apply afterward. It does not recapture a different field and
treat that as the requested target. Ordinary dictation retains its text-aware
capture for caret formatting.
