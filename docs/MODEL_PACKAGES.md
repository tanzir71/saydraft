# Pinned archive model installation

`models.packages.install_archive` extends explicit model downloads to ZIP and
tar.bz2 packages. The catalog pins a GitHub release asset ID, its binary API URL,
archive size/SHA-256, and every extracted file's size/SHA-256. Existing Hugging
Face entries keep their exact commit URLs. Archive entries use
`github-release-asset-<id>` revisions and reject mutable release-tag URLs.

The installer requests binary content with `Accept: application/octet-stream`;
public assets need no GitHub token. Only `api.github.com` and
`release-assets.githubusercontent.com` are allowed. The existing downloader
provides scoped network access, pinned-byte limits, Range resume, pause and
archive verification. See the [GitHub asset API](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).

## Publication and preservation

Bundled notices are verified before any transfer. Disk preflight includes the
remaining compressed package, a full new extraction and the 64 MiB reserve,
grouped by target/cache volume. Verified complete installations return immediately.

Extraction writes only explicitly declared regular files with flat destination
names into a new staging directory. Links, duplicate payload members, unexpected
sizes and bad hashes fail. Unlisted paths, including traversal entries, are never
written. Windows device names, alternate-stream syntax and reserved completion
markers are rejected by catalog validation. ZIP encryption/special file entries
are unsupported. Notice copies also pass their pinned hashes.

The completion receipt is written after all payloads are verified. Before moving
directories, the installer checks resolved staging, target and archive paths.
An existing installation is retained under `_archive`, then the complete staging
directory is published. Publication failure restores the old path when possible;
all files remain available. This is a sequence of directory renames, with a brief
gap during replacement; already loaded inference sessions continue in memory.

Pause or failure preserves the package/partials, staging directories and old
installation. Resume reuses the verified package and starts a new extraction;
it does not resume inside the compressed stream. Staging and cached archives are
not automatically deleted. Progress reserves its final 100% for publication.
No import, microphone startup or recognition action invokes the installer.

## English preview package

The catalog now contains `nemotron-preview-160ms-int8` under the `preview` role,
separate from the normal speech-model picker. Its explicit download helper targets
`models/preview/<id>`. Labs controls and streaming integration follow separately;
there is no automatic download or change to default final recognition.

The 463,945,198-byte archive installs 661,999,126 bytes, including the NVIDIA
agreement and attribution. Keeping the archive and payload needs about 1.13 GB
plus the disk reserve. The full agreement is bundled unchanged at
`assets/licenses/nvidia-open-model-license-2025-10-24.pdf`; `.gitattributes`
preserves notice text bytes across Windows checkouts. See
[the preview spike](spikes/streaming-preview.md) for provenance and cadence.

A real cached package installation ran with zero network calls under NetworkGuard.
All model and notice hashes passed; the installed model then recognized the
bundled English fixture with native sherpa-onnx. Installation plus a final full
hash audit took 58.159 s while other tests ran concurrently. This is not a startup
latency result. The original archive, older cache receipt and prior probe model
were retained in private QA storage.

Tests cover both formats, binary request headers, cache reuse, notice integrity,
malformed paths/metadata, corrupt or missing payloads, linked/duplicate entries,
pause/resume, disk preflight and publication rollback. The normal manifest/parser
stays independent of inference and download imports.

Final verification: 485 tests passed, four optional native checks skipped with
real Silero and language detection enabled; cleanup evaluation 42/42; Ruff and
diff checks pass.
