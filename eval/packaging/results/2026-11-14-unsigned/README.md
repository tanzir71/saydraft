# Unsigned Windows package evidence

Producer: `afddeec5fc2f38747d739d5df9f07e60393c3325`.
[Package run](https://github.com/tanzir71/saydraft/actions/runs/43498108469)
and [full CI](https://github.com/tanzir71/saydraft/actions/runs/43498108425) pass.
CI records 3,137 passed / 12 skipped, rules 556/556 and authored validator 100/100.

The installer is **109,188,877 bytes** (109.2 MB), below the 250,000,000-byte gate.
The portable ZIP is 166,768,090 bytes. The unpacked application is 424,852,776
bytes across 526 files; the size gate applies to the installer. Artifact SHA-256
values are retained in `index.json` and `bundle.json`.

The fresh build installs only runtime/build requirements. Its actual Analysis
table contains 1,516 modules, with no forbidden pyarrow/aiohttp/testing/build
modules. The file audit refuses downloaded weights, profile data and links.
Preflight and post-compilation file hashes match. Frozen imports, resources,
fonts, tray images and Python NetworkGuard checks pass both before packaging
and after installation.

The disposable Windows lifecycle confirms default data retention, explicit
removal, autostart off by default, opt-in startup registration and removal, and
preservation of a junction target outside the app-data fixture. No microphone,
audio-device enumeration, ASR, OS key injection, clipboard or foreground read
is used by these checks.

The JSON and text receipts are copied byte for byte from the Package artifact.
`module-table.json` is a derived list of names/kinds, with the source TOC hash;
the original TOC remains in the workflow's receipts artifact. `index.json` pins
every retained file. The compiler's PE version receipt is `0.0.0.0`; it is not a
verified compiler-version measurement.

The first attempt at `9336a2e` failed before freezing because the binary-only
dependency policy refused source-only pinned pyperclip 1.9.0. The correction
permits that source package; module, size and lifecycle gates remain unchanged.
The original failed workflow is linked in `index.json`.

This is resource/lifecycle proof. Artifact review subsequently found missing
full upstream license texts for several bundled libraries; P8.1 remains open
until that coverage is corrected and checked. These unsigned development
artifacts are not a published release and prove no owner accuracy, physical
dictation, signing, update or native-firewall acceptance.
