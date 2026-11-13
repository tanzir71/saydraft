# Scratchpad and Notes

Open Scratchpad with **Win + Alt + S**, or choose **New note** in Hub → Notes.
It is a resizable floating plain-text window. Type or dictate into its field;
the normal dictation shortcut still applies when the field is focused. Opening
the window itself does not start a recording. Notes work without an AI model.

The draft saves locally after a 400 ms typing pause. Saving happens on a serial
background worker, and edits made during a write are saved afterwards. Closing
the window, choosing New note, opening another note, and the tray's Quit action
wait for pending edits to save. An untouched blank draft creates no note.
Clearing an existing note saves the empty text. Reopening Scratchpad resumes
the last saved Scratchpad draft, including after a later app launch.

If a save fails, the window keeps the unsaved text and explains how to retry.
Copy remains available. If another edit or deletion changed the stored revision,
Saydraft refuses to overwrite it. **Save as new** keeps the current draft in a
separate note. **Discard changes** asks before dropping only the unsaved buffer
and reloading the stored note. Notes accept up to 1 MiB of UTF-8 text.

## Find and reopen notes

Hub → Notes searches note text and shows up to 200 recent matches. Search is
Unicode-normalized and case-insensitive; `%` and `_` match literal characters.
Select a note to read it, then choose **Open in Scratchpad** to edit it. You can
also double-click a result. Search and detail reads run outside the GUI thread,
and late results cannot replace a newer query or selection.

Notes share `%LOCALAPPDATA%\Saydraft\history.db` with History in additive schema
v3 tables. They have their own identifiers and optimistic revisions. Saving a
note creates no dictation entry and changes no Home dictation statistics.
Migration preserves existing data and retains a pre-change backup; see
[database behavior](DATABASE.md). The stored kind also reserves Command, Ask,
and meeting notes for their future producers; those modes remain planned.

Copy uses Saydraft's existing Windows clipboard privacy handling. Text selection
and dragging use the same private plain-text MIME policy as History. Note text
is never interpreted as HTML. The Notes browsing and saving path uses no network
or microphone and does not inspect another app.

## View the last dictation's changes

**Ctrl + Win + D** opens Hub → History, clears its search, and selects the latest
global dictation with **Show changes** selected. This compares the saved raw and
cleaned text. An empty History shows its empty state. It creates no dictation
or insertion. If the chord starts a new Ctrl+Win recording prefix, that prefix
is cancelled before the action opens; releasing remaining keys cannot submit it.
An existing hands-free recording keeps running and can still finish normally.
A refused new start never cancels unrelated processing or setup work.

Both actions can be rebound or disabled in Settings → Shortcuts. They share
native conflict/prefix validation. An upgrade preserves existing custom
bindings and disables only a newly introduced default that conflicts with them.
Queued requests are revoked when listening stops, restarts, or is reconfigured.

## Verification boundary

The focused checks are in [Contributing](../CONTRIBUTING.md#scratchpad-and-notes-checks).
They use private fixture databases, fake clipboards, synthetic native key
packets, and owned offscreen Qt windows. Physical shortcut/Start-menu acceptance
remains open under P6.5 in the [parity plan](../WISPR_OFFLINE_PARITY_PLAN.md).
No desktop input or microphone session is resumed by these checks.
