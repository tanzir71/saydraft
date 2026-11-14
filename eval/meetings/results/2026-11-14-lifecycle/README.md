# Local meeting lifecycle evidence · 14 November 2026

Clean runtime source `f5eaf0159f547221e09083642c83b2c75fe77ba2` passes a local
owned offscreen capsule/worker/controller/processor run with the actual speech,
VAD, speaker and 4B summary models. Two licensed public English FLEURS files
arrive as **compressed file events**; neither audio SDK is imported and no
microphone, playback, foreground read or clipboard port is used. The default
app profile/model resolver is replaced by explicit verified QA-cache paths.
This does not qualify live capture, physical UI, the whole app/default profile,
the frozen connected workflow, broad semantic/language accuracy or a 30-minute
meeting. P7.5 and its existing failed decision-quality gate remain open.

The corpus is [Google FLEURS, CC-BY-4.0](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd).
The raw report includes source pins, file hashes, sample counts and references;
its exact corpus metadata is already retained in `../2026-11-14-analysis/sources/`.
The two clips total 22.02 seconds and have coincident synthetic time origins.
The 11.46-second Note duration is not elapsed real-meeting capture time.
No audio or model binaries are committed. The model catalog and bundled notices
retain the six artifacts' independent licenses and exact revisions.

The first capsule paint is acknowledged while the fixture capture owner has
not started. Worker status records keep capture active through recording and
switch to processing only after stop. ASR/speaker instances are released before
the shared exclusive editing lease starts its native summary process. A complete
stopped native summary becomes a separate revision 1 `meeting` Note; the fixture
Scratchpad stays active and unchanged. Source/model hashes and the owned model
process exit pass. Python NetworkGuard rejects external DNS. Native firewall
qualification remains explicitly false and separate. A file-execution pass
does not establish optimal topic grouping or the truth of every paraphrase.

The 56 clean-source render states cover 14 states × light/dark × 16/22px fonts.
The renderer checks owned-widget layout bounds. A preliminary transparent-panel
render was rejected; the source explicitly paints its rounded opaque themed
panel and has a regression checking alpha. The original failed development
renders remain on the QA volume, with no qualification claimed for them.

The retained local log records 468 passed checks across meeting capture,
controller, offscreen capsule, the five actual app-shell seams with fake capture/
model/context and disposable profile/log ports, Notes/recovery, existing worker/
editing/model/downloader contracts, release validation and the manual-only
workflow policy. This is a targeted local suite, not the entire repository's
native/physical test matrix. Rules 556/556, authored adversarial 100/100 and Ruff
also pass in observed local runs. Their timings are development observations,
not release latency qualification.

The owner now requests local validation/builds and direct pushes. All five
Actions workflows are manual-only, no automated PR/deployment/release is started
by a push, and no GitHub workflow result is used as a delivery gate.

Run `python verify-lifecycle.py.txt --repo <full-checkout>` for standard-library
raw-file/source/model-pin/corpus/SSE/citation/SQLite/indicator/render consistency
checks. `--audio-root <FLEURS-English-root>` additionally rehashes the two inputs.
The verifier imports no app/audio/model modules and makes no network request.
It accepts only original Git blob bytes or their exact CRLF checkout form for
native source fingerprints. Machine-specific local drivers are retained as
`.py.txt` receipts. Explicit setup and the consented start action still follow.
