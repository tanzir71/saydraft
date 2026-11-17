# F10 voice-note toggle

The former three-second History-only action now starts/stops an independent
voice note. Notes exposes Record note / Stop recording / Saving note states and
the configured binding; Settings calls it Record note. Custom bindings keep the
existing `hotkeys.save` key. The normal recording cap and Esc cancellation apply.
The Bar says Recording note, then Note saved, without prompting for paste.

**262 unique successful guarded cases** across the listed runs cover the changed
worker and cleanup paths, Notes/SQLite and Scratchpad recovery, synthetic native
F10/rebound-key repeat handling, offscreen Notes controls, Settings and app/Bar
wiring. History commits before Notes, a voice note preserves the active draft,
and failing History/Notes writes cannot claim a new saved Note. Tests refuse
foreground, clipboard and insertion ports; no host microphone or physical input
was exercised. Themed offscreen screenshots were visually checked.

`manifest.json` pins the original archive, every member and changed source bytes.
Original failed attempts remain: two test assertions initially used summary
objects as full records; the first UI invocation named a nonexistent test file;
the next UI runners lacked a logging stub, then correctly refused the unrelated
main/single-instance import. The successful UI run explicitly deselects that
legacy main smoke test, leaving its native startup boundary unqualified. The
unthemed first render lacked font bootstrap; the corrected render uses the real
bundled fonts and theme. These were harness/assertion issues, not erased passes.

All successful runs have empty guard attempts, no real audio SDK imports, and
false owner-profile, clipboard, input, device-enumeration and microphone flags.
Actual microphone/F10 acceptance remains owner testing; no VM work was done.
See the [cleanup native record](../../../cleanup/results/2026-11-17-cleanup-repair/README.md)
for the separate measured model suites and their limits.
