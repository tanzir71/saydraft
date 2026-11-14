# Hub style preview qualification, 15 November 2026

Application source `875716bef32c05c885489701d09f596fb9a8e417` includes staged
Dictionary terms/protected terms/replacements and pending forms in the Hub's
Style preview. Previewing neither writes those edits nor claims learning Undo.
Invalid drafts decline preview; clean drafts can use the current running
dictionary. A preview-only language selector follows speech settings or simulates
resolved recognition, without changing pins or loading/downloading a model.
Spoken translation targets are kept separate. Bounded table widths and a guarded
geometry update preserve larger-text layouts without automatic content resizing.

The expanded guarded local run exits **0**, with **283 passed**, three app-entry
tests deselected, in 426.76 seconds. The real Hub matches all **84** authored
group/tone/intensity goldens and the actual memory-delivery processor. **20**
requested-language authored text samples and **96** previously qualified English
dictionary outputs also agree. Existing fixture History is unchanged. Stale AI
results, pending forms, provenance/import renames, invalid drafts, translation
targets, language pins, inheritance and shared Save behavior are covered. Rules
pass **556/556**, adversarial validation **100/100**, and Ruff passes.

**32** owned offscreen Hub PNGs cover light/dark, 880×600 and 1080×720, 16/22 px
text, and 1×/2× density. Each checks row heights, no page horizontal overflow,
reachable preview controls, correct dictionary output and unchanged form/file/
History. **Eight** gallery exports cover both themes/densities; four 1× images
match the inspected snapshots, with only the two Style baselines updated.

The tests and Hub renders ran before the local code commit, with dirty Git
metadata. All eight edited code/test files predate the final process launch;
their retained byte hashes and normalized Git blobs match `875716b` exactly.
Render reports separately bind all six edited application files. No code/test
bytes changed during the final run. The later 2× gallery records the clean code
commit. The verifier imports no application, Qt, audio or model SDK.

```powershell
python eval/styles/results/2026-11-15-hub-preview/verify.py.txt --repo .
```

All **79** raw records, including the verifier, are retained in `files.json`.
Original failures remain in `diagnostics/`: initial test assumptions incorrectly
expected empty History and used the Notes profile against General-profile
goldens; one checkbox name and a test path were wrong. These harness errors were
corrected without changing goldens or qualified dictionary outputs. The initial
render invocation failed, then a valid run found actual large-text overflow.
Automatic content sizing was replaced by bounded widths. One earlier mixed
theme run was explicitly stopped after two stack inspections suggested an event
loop; its partial log and termination reason are preserved. The final run's
later stacks show advancing, slow native Qt repolishing, and its observed exit
proves completion. The isolated styles/theme run also passes 41 checks.

Real SoundCard/PortAudio imports, application/profile entry points and owner
services were barred in the parent test process; the separate font subprocess
uses bundled public font fixtures. The three app-entry tests were explicitly
excluded. No owner microphone, devices, clipboard, foreground, hooks or OS input
were used. AI checks use fake ports; language samples are typed text, not new
speech evaluation. This accepts P5.7's engine/Hub-preview requirement, not model
tone quality, multilingual/owner accuracy, physical dictation, full accessibility
or a portable rebuild. The full original goal remains active. No Actions or PRs
were used for delivery.
