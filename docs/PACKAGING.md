# Windows packaging

`tools/build.ps1` now builds in a fresh Python 3.13 virtual environment outside
the source checkout. It installs only `requirements.txt`, uses the canonical
`Saydraft.spec`, verifies the frozen runtime, audits the actual module graph and
files, and compiles an unsigned per-user Inno Setup installer. Pytest is a
development dependency; PyInstaller remains the pinned build dependency.
Dependencies use published wheels, with a source-distribution exception for the
pinned pure-Python pyperclip package, which has no wheel at that version.

The clean `afddeec` build and installer lifecycle pass, with a 109.2 MB installer
and no forbidden pyarrow/aiohttp modules. The [retained evidence](../eval/packaging/results/2026-11-14-unsigned/README.md)
includes exact artifact hashes, runtime checks and install/uninstall receipts.
Artifact review found incomplete upstream license-text coverage; its correction
and an enforcing coverage gate are pending before P8.1 acceptance.
This does not establish signing, owner accuracy, physical Windows acceptance
or readiness for a public release. No installer release is published yet.

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

The explicit `Saydraft.exe --verify-package NEW_REPORT.json` command checks
frozen imports, fonts/model notices, dictionary/prompt resources, tray images
and the Python NetworkGuard. It does not start the application, audio devices,
recognition, hooks, foreground reads or clipboard access. It does not prove the
native firewall boundary. Sounddevice is checked without importing it, because
that import initializes PortAudio.

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
CI retains unsigned artifacts and reports even on failure. It creates no release.

The build uses PyInstaller's supported spec-file output/work paths. References:
[PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html),
[Inno DelTree](https://jrsoftware.org/ishelp/topic_isxfunc_deltree.htm).
