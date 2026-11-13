# Selected-target boundary — 2026-11-14

Source `5339fa94077540416d9466cc908b015aaa8d0180` passes
[CI 43528600278](https://github.com/tanzir71/saydraft/actions/runs/43528600278):
**3,343 tests / 12 explicit skips** in 262.90 seconds, rules **556/556** and authored
adversarial checks **100/100**. Update metadata and disposable firewall checks also
pass. [Package 43528600306](https://github.com/tanzir71/saydraft/actions/runs/43528600306)
passes its clean build, frozen import/resource/notice checks, installer lifecycle
and frozen speech/network firewall smoke.

The new selected-target API is verified with 195 focused synthetic/integration
checks and an actual native probe on both the development host and CI. Each
native probe reads only its process's invisible EDIT control, substitutes its
own focus identity and uses the real single bounded UIA MTA. It verifies:

- exact complete capture of a 1,408-UTF-16-unit selection;
- rejection when the same text is selected at a different range;
- rejection when text changes in the same field/range;
- read-only text access with write verification refused;
- password refusal with no selected-text read;
- cancellation, native owner retirement and owned-window cleanup.

Synthetic cases additionally cover complete/overlong/invalid UTF-16 data,
identity/password changes during reads, both endpoint comparisons, no surrounding
document reads, expiry without polling text, stale-generation cleanup, cancellation
during capture and verification, and a result expiring before consumption.

The five JSON payloads are unchanged originals: local/CI native reports, two
completed workflow API snapshots and artifact metadata. `index.json` hashes them
and the privately retained logs. The downloaded metadata ZIP matches GitHub's
SHA-256. Pytest's numeric/current directory aliases produced two identical copies
of the CI report; these are one measurement, with both entry names retained.

**P7.1 is still incomplete.** This evidence qualifies its selected-target
foundation, not instruction recording, hotkey/tier/Labs admission, clipboard-copy
fallback, edit generation/30-case validation, replacement or Scratchpad recovery.
The frozen workflow is regression evidence; it does not execute a complete
packaged Command Mode flow. No owner active application, input, clipboard,
microphone or physical focus/paste is exercised. See
[Command Mode work](../../../../docs/COMMAND_MODE.md).
