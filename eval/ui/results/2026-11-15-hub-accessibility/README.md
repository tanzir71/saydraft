# Hub accessibility checkpoint — 15 November 2026

Source `6831b0ec8c8f79d4c09a7bca10ad13dc5a39b6a7` passes **164 tests** across ten fresh guarded processes,
with three app-entry integrations deliberately deselected. All process trees
retire normally. The final renderer passes **108 public fixture states**, each
with named forward/reverse Tab walks (216 walks), at actual 16px/32px text in
light, dark and injected high contrast. No owner audio/device/input/clipboard
port is used. This is partial P6.7 progress, not full Windows acceptance.

See the [behavior and remaining checklist](../../../../docs/HUB_ACCESSIBILITY.md).
The [final report](final/report.json), [test summary](tests/summary.json),
[render guard](final/guard.json), [parent guard](tests/parent-guard.json), and
[lint result](tests/ruff.log) retain the actual results. The source witnesses
are exact Git bytes, separate from the external producer scripts.

## What changed

The rail fits its actual font/icon/scrollbar metrics. Home wraps its shortcut
explanation; native forms can stack long rows. History/results/model/matrix/JSON
controls have names. Populated Dictionary, Snippets and Style tables and
multiline form editors let Tab leave without editing text. Help/model license
links are keyboard reachable. Dictionary source chips use native paired colors
for normal/selected and active/inactive/disabled states.

The 21 new regression cases include actual Qt focus events and accessible-name
queries, expanded fields, live 16→32→16px changes, two window sizes, six chip
raster checks and queued-callback exception enforcement. The three deselections
import the app entry point; they were not run around the owner's desktop stop.
The existing History tests now inject memory clipboards explicitly. The Snippets
test installs a forbidden fake clipboard module rather than importing the real
implementation merely to forbid a method.

## Original diagnostics

The diagnostic records are excluded from final qualification:

- Early inspector preflights exposed a wrong font-function name and a fake
  clipboard that incorrectly raised during `hasattr`. These are harness errors.
- The original focus walk exposed multiline and populated-table Tab traps.
  The first new-suite run omitted required History fixture metadata; subsequent
  runs exposed real table traps, then an overbroad text assertion during normal
  first-row selection. The final fixture preselects rows and checks editable
  text. Original logs are retained without rewriting their outcomes.
- The first broad run has 153 passes/five guard refusals: four History defaults
  attempted native clipboard construction and one Snippets monkeypatch attempted
  to import it. The guard stopped them before import. App-entry integrations were
  also deselected. This long combined run is diagnostic; the final per-file
  runs use the corrected tests on clean committed source.
- Initial rendering supplied the wrong inventory fake shape, producing queued
  callback errors. It is not accepted. The corrected fixture supplies the actual
  `Inventory` value and treats callback exceptions as failures.
- The second render at `d711e23` has 108 states but predates the chip correction.
  Its retained [chip image](diagnostics/before-chip-fix.png) exposed unreadable
  white-on-white text under the injected palette. Only the final 6831b0e captures
  establish the corrected result.
- The first fresh-process driver hid user-site dependencies with its private
  profile and all ten children stopped at missing PySide6. The next driver
  passed explicit read-only dependency paths but its end-of-run clean-source
  check failed as the chip fix was being developed. Neither run qualifies.
  Final `final-tests-r3` ran from clean source throughout, with explicit dependency
  paths, no user-site processing and bounded kill-on-close Windows Job trees.

The two earliest large-text images are diagnostic captures from the initial
8144585 checkout; their external inspector changed during investigation. They
are not an exact-producer reproducibility claim. The final scripts are retained
under [scripts](scripts/) with their original D-drive paths. Adapt copies to an
isolated machine to reproduce; leave these original records unchanged.

## Limits

High contrast is a fake Qt preference plus a fixture palette, not a changed or
verified Windows preference. These are offscreen Qt widgets, not native Narrator
or UIA acceptance. Wide pages still need horizontal scrolling at 32px/880px;
universal reflow, physical focus/keyboard, mixed-DPI, Bar/onboarding and complete
P6.7 acceptance remain open. The 2× text check does not claim 2× display-density
acceptance. The earlier portable 5848e53 is historical and lacks these UI changes;
no new portable/installer, release, deployment, Actions run or signing follows.
The full original goal and accuracy/manual/release gates remain open. Reserved
audio is uninferred, and both outstanding owner decisions remain pending.

Verify retained bytes, original Git source, state coverage, focus/name results,
guards and test exits from the repository root:

```powershell
python eval/ui/results/2026-11-15-hub-accessibility/scripts/verify-delivery.py.txt --repo .
```

Add `--check-current` only when verifying delivery of unchanged app/QA source.
By default the verifier checks the recorded historical source; later intentional
UI changes do not rewrite or invalidate this historical measurement.
