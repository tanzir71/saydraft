# Labs license-link fix: current local portable

Fresh clean source `bd6c22af0580f245980cc5b685483728cdf7e609` builds successfully
in an isolated Python 3.13 environment. It contains the Labs palette-aware link
fix and the earlier Hub reflow/cleanup warmup fixes. Its complete app Git tree
matches the [six-test, ten-capture Labs qualification](../2026-11-15-labs-license/README.md)
at `1cd39e3`; no additional app behavior changes are introduced here.

Local preview:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/labs-license-package-20261115-r1/artifacts/Saydraft-0.1.0-win-x64.zip`

- Size: 157,078,561 bytes.
- SHA-256: `21d9ecdf905d588a306c6c4a559173e604540e4c88865b8446d53e27d145a522`.
- All 1,384 actual disk files and every ZIP payload match the bundle audit;
  complete sets, safe paths, uniqueness and artifact bytes/hash verify.
- All 18 critical modules read from the executable's embedded PYZ match compiled
  Git source, excluding only filename metadata. No app module code is executed
  by that structural comparison. The set already includes Labs.
- Frozen runtime/resources and 40 third-party notice components / 511 payloads
  pass package checks. The audio SDKs are located through metadata/files;
  package verification does not import sounddevice/SoundCard or start capture.

The build runs with `-SkipInstaller`. It is unsigned, and its installer-size and
packaging acceptance flags remain false. There is no installer, release,
deployment, native Windows input/device check, physical high-contrast/Narrator
acceptance or full-goal completion. The previous `625c987` portable retains its
historical receipts and lacks this Labs fix.

The first evidence collection stops after two copied audit files because it
mistakes the verifier's private profile directory for a file. The corrected
collector excludes directories and resumes only when existing bytes match.
Both collector sources and the failure receipt are retained; binary verification
had already passed and no model/app rerun follows.

Verify retained hashes and Git source without launching the app:

```powershell
python eval/ui/results/2026-11-15-labs-license-portable/scripts/verify-retained.py.txt --repo .
```

The other retained scripts re-read the original actual build with explicit
`--build`, `--source`, `--output` and, for frozen code, `--repo` paths. Audio,
models, binaries and private profiles are excluded from this evidence bundle.
