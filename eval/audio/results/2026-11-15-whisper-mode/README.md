# Whisper mode implementation checkpoint

The experimental default-off quiet-speech front end and reviewed local GTCRN
setup are implemented at `6edaad6f470b97e7bfed8248a22df0ec8db97a64`. P7.4 remains unchecked: the owner whispered
clip target of at least 20% relative WER improvement is deferred and unmeasured.

The guarded 27-file regression passes **426 tests**, with **3 optional native
skips** and **3 restricted application-entry/desktop checks deselected** in
115.03 seconds. This is a focused regression, not the full repository suite.
Rules pass 556/556, adversarial validation 100/100, and Ruff passes.
The source witness binds 526 application/test files to the clean commit and
their pre-run timestamps; both final render reports match that source.

The 64 owned offscreen renders cover light/dark themes, 880×600 at 22 px and
1080×720 at 16 px, four setup states and two scroll positions, at 1× and 2×.
Controls remain reachable without horizontal overflow; long feedback fits the
minimum-size Hub footer. New model-license links follow the current theme.
No user recording, profile, device, clipboard, foreground or OS input is used.

The actual pinned GTCRN runtime passes nine generated/bundled-file cases with
exact sample counts and unchanged input-array hashes, including a partial hop
and the 400,001-sample window boundary. The model cache is fully verified; the
probe makes no network requests. These are signal integrity checks, not an ASR
accuracy or release-latency result. The 60 reserved BN/TA/TE recordings remain
uninferred. Model weights are kept only in the explicit D: QA cache.

The fresh isolated portable build and its frozen import/resource/runtime,
notice and module/file audits exit successfully from this clean commit. A
separate actual frozen enhancement diagnostic processes a generated 16,001
sample signal offline, with complete finite output. It starts no application
capture, recognition, hooks or clipboard services. SkipInstaller leaves the
installer and complete packaging gates false; nothing is signed or released.
The portable binary stays in the D: build root in receipt.json.

Earlier failed runs are retained unchanged. R2 barred owner application/logging
entry points and exposed an outdated config expectation. R3 exposed the test
profile stub ignoring per-test LOCALAPPDATA, causing stale tiny-fixture model
installs to leak across runs; the harness now confines each requested test
profile to D:. Model assertions were preserved. R4 exposed constructor ordering;
R5 exposed bundled notice versus transfer-size accounting and a stale Notetaker
expectation; R6 exposed a checkbox bool used as a hardware report; R7 selected
a nonexistent test file; R8 exposed draft quiet settings absent from Labs
refresh. R9/R10 passed 380 tests. R11 exposed long footer clipping; R12 passes
its focused UI regression. R13 passes 426 tests before a final setup-link color
fix; R14 passes the same regression with that fix and the final 64 renders.
Native shape probing records the pinned API truncating to 256-sample hops;
production pads before inference, checks complete output and retains every
original sample. Historical UI images remain in the original D: QA directory.

Run the metadata verifier without application dependencies:

```powershell
python eval/audio/results/2026-11-15-whisper-mode/verify.py.txt --repo .
```

Add `--build-root` with the explicit receipt path to independently check every
actual bundle and ZIP file and the unchanged bundled GTCRN notices. This reads
the package; it does not execute it. All workflows remain manual-only. Delivery
uses local checks and direct main pushes; no PR or Actions run was created.
