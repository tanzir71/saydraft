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
