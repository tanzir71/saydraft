# Local speaker-model execution smoke · 14 November 2026

Clean source `57be9d26c89842ff00df7145db49f8c6b4864b10` runs the production
`SpeakerDiarizer` with sherpa-onnx 1.13.4 and the two catalogued, fully hashed
models. A guarded Python process exits zero after producing `native-report.json`.
It processes 23.02 seconds in 6.0024 seconds, after 0.7508 seconds of model
preparation, returning three turns in two acoustic clusters. Automatic speaker
count uses the upstream 0.5 threshold. These are observed outputs, without
speaker annotations or diarization error scoring. This is not a meeting-quality,
hardware capture, 30-minute workflow, summary or owner acceptance result.

The inputs are the first male and first female clips in the already-frozen
English FLEURS selection, with one second of generated silence between them.
No inference selected these clips. Original file bytes stay unchanged; the probe
concatenates their decoded float32 samples in memory. `fleurs-en-corpus.json`
retains references, file hashes, source pin and CC-BY-4.0 attribution to
[Google FLEURS](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd).
Gender labels do not establish identities or provide timestamped speaker truth.

The pyannote full-precision ONNX model is MIT licensed by CNRS. The embedding
artifact comes directly from the official sherpa release asset, with the
publisher's Apache-2.0 model card/license and conversion notice retained in
`assets/licenses/3dspeaker-eres2net-base/`. Original API responses, license text,
conversion source and download/source hash records are under `sources/`.
Neither model nor audio binaries are committed. The Chinese-trained embedding
model's other-language accuracy remains unqualified.

`cached-setup.json` records the production explicit setup action from independently
downloaded and hashed staging files. The request opener was set to fail if used;
all cache and final installation hashes passed, with zero requests. It does not
claim a new end-to-end network transfer through the app interface. Raw asset
binary Accept headers, size/hash verification and cache reuse are covered by
the automated fixture tests.

`local-import-guard.py.txt` is the exact local wrapper, with machine-specific
source paths. It bars SoundCard, sounddevice and app/profile-service imports.
The process loads only explicit public audio/model files, creates no microphone
stream and runs Python NetworkGuard's blocked DNS check. Source and model hashes
are checked before and after native inference. Native firewall enforcement is
explicitly false in the report. The pinned native callback reports progress
without interrupting processing; cancellation discards a result after return.

The retained `3aa3e84-windows-ci-failure.log` is the complete original Windows job
log from [run 43599599062](https://github.com/tanzir71/saydraft/actions/runs/43599599062):
4,278 tests pass, 12 skip and one thread-start fault-injection test fails because
a renamed metadata reader bypasses its injection. The corrected source restores
that thread name and extends the injection to streaming mode too. All 39 focused
process/ownership checks pass locally under the import guard. The source's
[package build passes](https://github.com/tanzir71/saydraft/actions/runs/43599599092).
The new speaker work separately passes 41 new and 50 existing downloader/catalog
checks. These local test counts are observed console results, not raw CI receipts
for the corrected source; that full CI result is pending.

Run `python verify-smoke.py.txt --repo <checkout>` for portable raw-file, original
Git source, catalog, input provenance and output consistency checks. Supply
`--models <model-root>` and `--audio-root <FLEURS-English-root>` to rehash the
original model/audio payloads too. The verifier uses only the standard library
and makes no network requests. It validates evidence consistency and does not
turn this smoke into a speaker-accuracy evaluation.

The native source fingerprints hash actual checkout bytes. The manifest Python
and JSON files have Windows CRLF endings; the three new source files have LF.
The verifier accepts only the original Git blob or its exact CRLF checkout
form for these five text files and reports which matched. The first verifier
attempt compared Git's normalized LF blob bytes directly and refused the CRLF
manifest; the raw native report and all source bytes are unchanged.
