# Packaged dependency notices

These are upstream license texts, copyright notices and attribution catalogs,
retained separately from Saydraft's MIT-licensed code. Exact versions, immutable
source revisions, byte counts and SHA-256 hashes are recorded in
[`installer/notice-supplements.json`](../../../installer/notice-supplements.json).
The collector checks those hashes before including a supplement in a build.

The supplement supplies open-source Qt/PySide license texts and Qt's upstream
third-party attribution catalogs, CTranslate2's MIT and CPU dependency notices,
the matching Intel OpenMP runtime agreement, sherpa-onnx-core's Apache license,
tokenizers' Apache license, and PyAV's upstream FFmpeg/native dependency notices.
Intel's DLL was compared byte for byte with the DLL in the CTranslate2 4.9.0
Windows wheel. The collector enforces that DLL hash and the PyAV 19.0.2 Windows
native payload hashes. A dependency change requires a new source review.

Upstream catalogs include optional components and platforms. Their inclusion
preserves attribution; it does not mean every cataloged component ships in
Saydraft. Compiler-runtime license texts retain their upstream source revision;
they do not establish which compiler version produced a third-party wheel.

PyAV native source archives were checked against the hashes in its pinned
upstream recipe. The lamer archive did not match its recipe hash; its license is
instead retained from the immutable commit resolved by its v3.101.0 tag. That
text is an attribution supplement, not a verified source-build equivalence claim.

The build additionally collects full notices and public package metadata from
each installed distribution represented in the actual frozen module graph,
plus Python's runtime license and the installed Inno Setup compiler's license.
Only notice data is copied from PyInstaller; its Python build modules stay
excluded. The shipped `third_party_licenses/index.json` records components,
versions, module coverage, source links and hashes of all collected notice data.

The notice check is part of explicit package verification, not ordinary app
startup. It does not restrict replacing dynamically linked libraries. Matching
notices and hashes establish the retained bytes; corresponding-source delivery
and other public-release obligations still need their release checks.
