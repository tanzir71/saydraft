# Snippets

Hub → Snippets has a searchable trigger/expansion list, a multiline editor,
Add/Update/Remove/New actions, variable insertion buttons and a test panel.
Edits are staged until the Hub's shared Save; Save includes a pending form.
Advanced JSON also accepts the legacy `trigger=expansion` syntax. Invalid drafts
stay available for repair; Reload saved Snippets explicitly discards a draft.
Search and editing do not write to the store.

Triggers match complete phrases, longest first, ignoring case. Original spelling
is retained, and matching includes canonical NFC/NFD and case-folded forms.
Combining-mark boundaries protect other words. Duplicate identities use NFC and
case folding. Expansions retain multiline text, leading/trailing spaces, equals
signs, Unicode, literal markup and backslashes.

- `{date}` writes the local date as `YYYY-MM-DD`, frozen once per result.
- `{clipboard}` reads the current copied text once when a used expansion needs
  it. Password/unverified targets, History-only processing and a cancelled or
  refused field guard do not read clipboard contents.
- `{{date}}` and `{{clipboard}}` write the corresponding literal variable name.
  Unknown variables and unrelated braces stay literal. Values containing another
  trigger or variable are substituted once.

The processor protects matched snippets before cleanup. It resolves variables and
restores their values afterwards, before existing final punctuation/caret layout
and History persistence. Clipboard values never enter the cleanup prompt. History
retains the exact raw trigger and final expanded result before attempted delivery.
An unavailable or oversized expansion retains its original spoken trigger and
shows a content-free notification. The date and remaining valid expansions still
work. Clipboard values and provider errors are not written to logs.

Limits are 2,048 snippets, 256 characters per trigger, 65,536 characters per
template/expanded value, and a 4 MB canonical UTF-8 JSON document/result budget.
Variable substitution checks each piece before joining, and total-result budgeting
keeps overflow triggers intact. Used-template values are reused within one result.
The Windows reader bounds the native allocation to 128 KiB plus the terminator,
copies its terminated UTF-16 text while the clipboard is open, and unlocks it
without freeing the owner's handle. It follows Microsoft's
[clipboard data ownership](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclipboarddata)
and [CF_UNICODETEXT format](https://learn.microsoft.com/en-us/windows/win32/dataxchg/standard-clipboard-formats)
contracts. Busy access or pending restoration refuses the read; it never publishes
or restores clipboard data. The provider follows the current shared clipboard
port after Settings replaces services.

The test panel uses a supplied clipboard sample and the same matching,
variable-resolution and restoration functions. It includes an unfinished form
without saving it. Its input is limited to 4,096 characters; samples/results remain
in memory and use the private text selection MIME converter. It accesses no system
clipboard, persistent History, microphone, model or OS insertion. Dictation still
applies the chosen cleanup/final-formatting policy around opaque expansions.

`data/snippets.py` makes the existing SQLite v2 `snippets` table live. At adoption,
the latest legacy file supersedes its earlier SQL import copy, while manually
maintained SQL rows take priority. A consistent `history.db.bak-*` preserves the
pre-adoption database. The legacy file stays untouched. UTF-8/BOM, comments,
ignored legacy lines and last-duplicate-wins behavior are retained; the structured
editor validates legacy draft lines strictly. A receipt named
`saydraft:snippets-canonical-v1` in `legacy_imports` records adoption, so subsequent
startup migration cannot reimport an edited legacy copy or resurrect deleted
snippets. Invalid/oversized source data does not mark adoption complete, allowing
repair and retry. Newer database versions are refused.

Reads/writes use short-lived SQLite connections. A content revision covers the
complete saved snippet rows. Changed stale drafts refuse Save before applying
other page edits; unchanged editors retain newer saved rows. Changes commit in a
single snippet transaction, preserving unchanged IDs/source and unknown owner
columns. Failed writes roll back the complete snippet edit. The runtime, Style
preview and Snippets test field retain the same trigger spelling.

```powershell
python -m pytest tests/test_snippets_store.py tests/test_snippet_variables.py tests/test_snippets_page.py tests/test_services.py tests/test_processing.py tests/test_hub.py -q
python -m saydraft.eval --min-pass-rate 100 --min-cases 556
```

QA uses authored public data, injected clipboard ports and owned memory. Native
owner clipboard, microphone/input and manual accessibility acceptance remain
deferred while desktop control is stopped. Full P6.3 also retains the remaining
History, microphone, model/disk, Privacy and Notes work.

Verification on 2026-11-13 adds 34 cases. The final full suite passes 2466 tests
with five explicit optional/native skips, rules 556/556, adversarial validation
100/100, lint and all 12 generated outputs. Forty-eight owned PNGs cover editor,
test and advanced states across light/dark, 1080×720/880×600, 16/22 px body text
and 1×/2× density. Logical/pixel sizes and absence of horizontal overflow are
checked; selected final renders are visually inspected. Existing component/Bar
snapshots remain exact. These are QA exports; full P6.6/P6.7 acceptance remains.
