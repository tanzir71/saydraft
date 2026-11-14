# Full large-v3 development comparison · 14 November 2026

**Both candidates are rejected by their frozen development gate.** No production
model, decoder, language route or default changes follow. These are eighteen
native cases on the same nine already-observed public clips: first three each
for Bengali, Tamil and Telugu. The sixty newly acquired confirmation clips
remain uninferred; neither candidate is admitted to that comparison.

| Three clips per language | Turbo WER / CER | Full large-v3 default WER / CER | Full large-v3 temperature 0 WER / CER |
| --- | ---: | ---: | ---: |
| Bengali | 84.13% / 39.30% | 66.67% / 28.45% | 66.67% / 28.45% |
| Tamil | 75.68% / 46.03% | 75.68% / 51.32% | 37.84% / 8.28% |
| Telugu | 70.21% / 18.66% | 55.32% / 19.72% | 55.32% / 19.72% |

Before each inference, the criteria required every language's aggregate WER to
stay equal or improve, CER to strictly improve, no new empty/U+FFFD cases, and
complete measurement verification. This is an admission gate for a separate
confirmation set, not broad language, owner, latency or default acceptance.
Default full large-v3 fails Tamil and Telugu CER. Fixed temperature zero
substantially reduces Tamil errors, but Telugu still has 56 character errors
versus the unchanged turbo baseline's 53, out of 284 reference characters.
Neither candidate introduces a new empty or replacement-character case.
Improved WER does not override the retained CER requirement.

The baseline is the original [public read-speech result](../2026-11-14-public-read/README.md).
References come from [Google FLEURS](https://huggingface.co/datasets/google/fleurs),
CC-BY-4.0, revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`.
The original corpus IDs, normalized references, audio hashes and baseline
journal hashes are preserved. Difficult outputs remain in the denominator.
These development cases were selected after baseline observation and cannot
establish independent or representative accuracy. No audio or weights are
committed.

Both runs use clean source `1b7e7eaf493e082692343244d6f1aed3e9907d68`, CPU int8,
faster-whisper 1.2.1 / CTranslate2 4.9.0, whole-clip input, normal 30-second
feature padding and unchanged native token limits. No VAD or AI cleanup runs.
The first uses the default temperature fallback sequence. The second changes
only temperature to zero through a diagnostic wrapper; native decode-call
records confirm no sampling fallback. Tamil's first result records repeated
fallback passes, explaining the motivation for the second test without proving
a language-wide fix. Source, runtime, script, corpus/reference/audio, model pins,
raw journals and scores were independently checked, with two observed zero
child exits. Timings are not latency qualification.

The explicitly downloaded QA model is
[`Systran/faster-whisper-large-v3`](https://huggingface.co/Systran/faster-whisper-large-v3/tree/edaa852ec7e145841d8ffdb056a99866b5f0a478),
revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`.
Its 3,087,284,237-byte weight has SHA-256
`69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1`.
The scoped download verified every manifest file and exited zero. It remains
outside the app catalog and packaging. Pinned source metadata is retained:
the conversion card labels MIT while the pinned upstream card labels Apache-2.0;
this record does not resolve distribution licensing or approve shipment.
The runs use explicit local cache paths and the Python network guard;
native OS firewall enforcement was not measured.

`index.json` identifies thirty byte-preserved source records: plans, criteria,
reports, journals, process receipts, scripts, independent verification and
download/source metadata. The original-machine verifiers additionally check
the private QA cache and actual audio; their paths are retained for provenance.
The portable replay uses only the standard library and existing committed
baseline records:

```powershell
python eval/asr/results/2026-11-14-large-v3-development/verify-scores.py.txt
```

It validates indexed bytes, frozen-before-inference criteria, raw score totals,
baseline links, output gates and rejection decisions. It makes no inference,
network request or audio/model-byte claim. All owner accuracy, broad language
quality, mixed/noisy speech and release acceptance remain open under P3.10.
