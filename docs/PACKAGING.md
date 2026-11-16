# Windows packaging

The latest **frozen field-reader and brand repair unsigned portable** is built
from clean `12bc27ffdb3ba388ea199e5e51661c968815c2fe`:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/delivery-brand-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: **157,308,167 bytes**. SHA-256:
`b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f`.
All 1,440 disk/ZIP files verify; 89 embedded modules, focus stylesheets and brand
assets match source. The actual EXE passes reader initialization and an approved
metadata-only focused-field check (`ok`, non-password, stable identity/window).
The app/window/tray use the landing-page star. Actual native pasting remains an
owner retest or VM acceptance item. [Evidence and limits](../eval/ui/results/2026-11-16-frozen-delivery/README.md).
Quit the older app from the tray before extracting and running this new portable.

The previous **keyboard-focus repair unsigned portable** is built from clean
`b6322666fc1cee11c06492ab493d9e4d74b3511b`:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/focus-presentation-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: **157,355,451 bytes**. SHA-256:
`0891f00001bf71a26b15fcb527310521846408da52c20dc14f910471ef48e3eb`.
All 1,439 disk/ZIP files verify; 84 embedded modules and both focus stylesheets
match source. The 61 targeted checks pass, including keyboard accessibility and
unchanged 1×/2× snapshots. It includes all prior startup/delivery repairs below.
[Evidence and scope](../eval/ui/results/2026-11-16-focus-presentation/README.md).
Close the older app, extract this ZIP and run its Saydraft.exe. Distribution
remains unsigned and portable-only.

The previous **startup/delivery repair unsigned portable** is built from clean
`87341231c744ebe3fbd5723917ba97b2945acd25`:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/startup-delivery-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: **157,354,466 bytes**. SHA-256:
`8bd71d95b6f17bdac400dd2885426805e65df026014e75d97b4863e504556919`.
All 1,439 disk/ZIP payloads match the actual audit; 84 embedded modules match
Git source. All eight font faces, twenty-one font assets, fifty-two SVGs and
three seven-resolution tray icons verify. Frozen runtime/resource/notices checks
pass without owner recording, clipboard or input. This includes first-use model
preparation, field-verification isolation, tray fixes and optional AI onboarding.
[Repair evidence and remaining real-field retest](../eval/ui/results/2026-11-16-startup-delivery/README.md).
Close the old app and extract this new portable before testing. No installer,
signing or release publication is claimed.

The previous **desktop UI v2 unsigned portable** is built from clean
`c1d0a491bbcbe0a7d5b8c97956dad7e77925d665`:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/app-ui-v2-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: **157,252,943 bytes**. SHA-256:
`3a6a11e792128ad7c17ff3b718fc4f97d363a7f92bba4086a044d23aae6f79e2`.
All 1,439 actual disk/ZIP files verify; 78 modules read from the EXE match the
frozen Git source without executing app code. All eight font faces, twenty-one
font assets/manifest, fifty-two SVGs and packaged shortcut help verify. Frozen
runtime checks pass without audio capture, device discovery, clipboard or native
input. [Evidence and limits](../eval/ui/results/2026-11-16-app-ui-v2/README.md).
This supersedes the microphone-repair build below. Close the older app and use
the new extracted portable to see v2. No installer or signing is claimed.

The replacement unsigned portable at clean `44ed9c4` fixes multi-input discovery,
virtual-input guidance and silent/quiet capture diagnostics. Its actual 1,384
disk/ZIP payloads and 28 embedded modules match the audit and Git source.
Artifact: `D:/Saydraft-Codex-QA-20261112-01a1cbc7/microphone-repair-package-20261115-r2/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: 157,082,564 bytes; SHA-256:
`83456b5a9a50672db1ad74119c956c733c2768a287f301f701711b2e75aceb5c`.
This supersedes the older `e7c60b0` preview below. A running old executable must
be closed and replaced; saved microphone preferences alone cannot patch it.

The earlier local portable at `e7c60b0` includes delivery-target cleanup admission,
the Labs link contrast fix, Hub reflow and selected-intensity cleanup warmup.
Runtime/resource/notices and all 1,384 disk/ZIP payload checks pass; 22 critical
modules read from the executable match Git bytecode. The
[retained delivery](../eval/latency/results/2026-11-15-delivery-planning/README.md)
records exact source, dependencies, artifact hash, original diagnostics and
remaining qualifications. The owner explicitly chose unsigned distribution and
a bounded working preview on 15 November; signing does not block that delivery.
This `-SkipInstaller` artifact is a portable ZIP. A current installer, broader
native Windows qualification and full-parity acceptance remain separate future
work. See [minimum preview acceptance](MINIMUM_PREVIEW_ACCEPTANCE.md). The previous
[Hub-only portable](../eval/ui/results/2026-11-15-hub-reflow/README.md) at `f6cd0bf`
retains its historical qualification and lacks the newer cleanup fix.

Delivery now uses local checks/builds followed by direct Git pushes. The Package
and draft-release workflows are retained as manual-only tools; pushes and tags
start neither, and no successful GitHub Actions run is required for delivery.
The historical runner receipts below retain their original dates and scope.

The local `4d49758` portable diagnostic passes on a fresh Python environment,
including frozen imports/resources/notices, the actual module/file audit and a
hashed ZIP. Its first attempt exposed a launcher-PATH ICU collision; the build
now excludes unrelated application directories from DLL discovery. The original
failure, exact diagnosis and passing follow-up are retained with the
[meeting setup records](../eval/meetings/results/2026-11-14-setup/README.md).
This run used `-SkipInstaller`, so its installer and packaging gates remain false;
it does not accept a connected frozen meeting or publish an app release.

`tools/build.ps1` now builds in a fresh Python 3.13 virtual environment outside
the source checkout. It installs only `requirements.txt`, uses the canonical
`Saydraft.spec`, verifies the frozen runtime, audits the actual module graph and
files, and compiles an unsigned per-user Inno Setup installer. Pytest is a
development dependency; PyInstaller remains the pinned build dependency.
Dependencies use published wheels, with source-distribution exceptions for the
pinned pure-Python pyperclip and Metaphone packages, which have no wheel at those
versions. The dictionary evaluation also retains the exact Metaphone source
SHA-256 and verifies installed Python files against that source distribution.

The clean `94e4cce` build and installer lifecycle pass, with a 103,968,660-byte
(104.0 MB) installer and no forbidden pyarrow/aiohttp modules. The
[retained evidence](../eval/packaging/results/2026-11-14-notices/README.md)
includes exact artifact hashes, runtime checks, the notice index and
install/uninstall receipts. Notice verification covers 38 components and 506
files before and after installation. The downloaded installer and portable ZIP
match their reported hashes; all notice payloads were also checked inside the ZIP.
These checks complete P8.1's unsigned packaging acceptance. The
[initial afddeec evidence](../eval/packaging/results/2026-11-14-unsigned/README.md)
is retained with its notice-coverage gap, which this build corrects.
This does not establish signing, owner accuracy, physical Windows acceptance
or readiness for a public release. Corresponding-source delivery and other
public-release checks remain separate. No installer release is published yet.

## Build

Use Windows x64, PowerShell 7, Python 3.13 and Inno Setup 6 or 7. Start with committed source
and a new output directory outside the checkout:

```powershell
./tools/build.ps1 -Python C:\Python313\python.exe -OutputRoot D:\QA\Saydraft-Build-New
```

Use `-InnoCompiler` for a nonstandard `ISCC.exe` location. The script does not
reuse a venv, inherit user site packages, delete previous builds or overwrite an
existing output root. Temporary files, Python/packager caches and application
state use the build directory; environment changes are restored on return.
The build also restricts the native DLL search PATH to the selected Python/Git
and Windows directories. A desktop launcher's private ICU DLL can otherwise
shadow Windows ICU and make a successfully compiled Qt bundle fail at import.
Use `-PipCache D:\QA\Shared-Pip-Cache` to reuse downloaded wheels while retaining
a fresh virtual environment and output directory; the default cache stays
inside the new build directory.

The output retains `dist/Saydraft/`, `work/`, a dependency/version receipt,
resource/runtime reports, the module/file audit, a portable ZIP, the installer
and `SHA256SUMS`. `-SkipInstaller` permits a bundle diagnostic; its installer and
packaging gates remain false. `-AllowDirtySource` permits source diagnostics but
cannot earn the clean-source packaging gate.

The spec selects the public audio fixture, fonts, dictionary, tray assets and
license notices. Website/readme assets, downloaded models and owner profile
files are excluded. The app uses its explicitly installed pinned VAD; the
unused faster-whisper package-data model is omitted. Native runtime DLLs remain
bundled. The audit inspects PyInstaller's module table as well as visible files,
so a forbidden package hidden inside the PYZ archive cannot pass. It refuses
pyarrow, aiohttp, testing/build modules, model weights, profile data and linked
files/directories. Installer size must be at most 250,000,000 bytes.

The collector retains supplied full license/copyright/notice files and package
metadata for the actual frozen module graph, plus Python and the installer
compiler. [Pinned supplements](../assets/licenses/packaged/README.md) cover gaps
in Qt/PySide, CTranslate2, tokenizers, sherpa-onnx-core and native dependency
notices. It rejects unknown module owners, missing full texts, unreviewed
supplement versions and changed pinned bytes. Both the bundle audit and the
explicit frozen check validate `third_party_licenses/index.json`. Metadata and
an SPDX label alone cannot replace a full license file. The unused PDF and
virtual-keyboard Qt plugins are filtered before their dependencies are scanned;
the audit refuses their PDF/QML/Quick runtimes if they enter the bundle.

The explicit `Saydraft.exe --verify-package NEW_REPORT.json` command checks
frozen imports, fonts/model notices, dictionary/prompt resources, tray images
and the Python NetworkGuard, plus the collected third-party notice hashes.
It does not start the application, audio devices,
recognition, hooks, foreground reads or clipboard access. It does not prove the
native firewall boundary. Sounddevice is checked without importing it, because
that import initializes PortAudio.

The optional `--verify-package NEW_REPORT.json --enhancement-smoke VERIFIED_GTCRN_DIRECTORY`
also runs the pinned local enhancement model on a generated 16,001-sample signal.
It verifies finite, exact-length output under the Python NetworkGuard, without
downloading or using audio devices, recognition, clipboard or input hooks. The
directory must already contain the complete verified model installation. This
diagnostic and `--firewall-smoke` are mutually exclusive. It does not establish
whispered-speech accuracy, release latency or connected application acceptance.

The separate disposable-runner firewall step invokes the actual bundled helper
to create/remove its path-specific rule, reject ownership conflicts and narrowed
rules, and preserve an unrelated witness. Its explicit
`--verify-package NEW_REPORT.json --firewall-smoke PINNED_BASE_DIRECTORY` mode
performs public-fixture Whisper recognition, rules and temporary History, plus
fixed native WinHTTP and pinned model-file download probes. Online controls must
work before/after removal and fail under the rule, with clear resume guidance.
This mode refuses source Python and owner/self-hosted machines. The ordinary
verification command above retains its original no-recognition scope. See
[Verify offline](VERIFY_OFFLINE.md) for effective-policy and helper-process limits.

## Installation and removal

The installer targets the current user's Programs folder, creates a Start menu
entry and offers an unchecked Start with Windows task. It requests no admin
installation. Ordinary uninstall retains the Saydraft profile. The extra
unchecked **Also remove my Saydraft data** option removes settings, History,
notes and default model downloads. Custom model folders and earlier VoiceTray
backups remain. Silent uninstall also keeps data unless explicitly passed
`/REMOVEDATA=1`.

Removal checks the explicitly named local-app-data directory before recursive
deletion. Inno's documented `DelTree` behavior removes reparse points without
recursing into their targets. Startup cleanup removes only the entry matching
this installation's quoted executable path.

The **Package** workflow builds on a disposable Windows runner. Its lifecycle
smoke installs, verifies the frozen resources, confirms default data retention,
reinstalls with autostart, explicitly removes data, and checks that an external
junction target survives. That script refuses an account with pre-existing
Saydraft data or startup registration; it is intended for disposable QA accounts.
The manual workflow retains unsigned artifacts and reports even on failure. It creates no release.

## Draft release automation

`release.yml` is manual-only and accepts an explicitly selected `v*` tag ref.
It does not query or wait for GitHub CI. It builds a fresh unsigned package for
the selected source, repeats the disposable installer lifecycle and
validates delivered artifact hashes against the package audit and SHA256SUMS.
The tag must match the packaged version, with an optional prerelease suffix.
It then creates a GitHub **draft**, attaching the installer, portable ZIP,
checksums and release manifest. Existing releases are not overwritten.

The release notes identify the unsigned build and its remaining publication
checks. Signing is the separate G5/P8.3 owner gate. P8.2 passed its real
[`v0.1.0-dry-run.20261114` tag verification](../eval/packaging/results/2026-11-14-draft/README.md):
the workflow created a draft with four verified uploaded assets. The release
remains unsigned and unpublished.

The build uses PyInstaller's supported spec-file output/work paths. References:
[PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html),
[Inno DelTree](https://jrsoftware.org/ishelp/topic_isxfunc_deltree.htm).
