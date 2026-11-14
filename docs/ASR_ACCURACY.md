# Multilingual speech accuracy work

Status, 14 November 2026: language coverage, cleanup safeguards and controlled
acquisition/scoring tests pass. The [public read-speech baseline](../eval/asr/results/2026-11-14-public-read/README.md)
is complete: four hundred unique clips across twenty languages (81.41 minutes),
500 model cases, twenty observed zero native exits, and independently verified
audio/reference/source/model hashes and score totals. This is a small baseline;
language-quality acceptance and evidence-backed improvements remain open.
Bengali, Tamil and Telugu show substantial recognition errors. A separate three-clip
[Bengali decoder diagnostic](spikes/bengali-decoder.md) confirms native output
capping and rejects an internal 8-second-window candidate because character
errors worsen. This development finding is not broad language acceptance.
Owner-recording acceptance remains deferred. The isolated Pro latency run has
finished and its [failed median gate is retained](LATENCY_MATRIX.md).

## Evaluation scope

Evaluate the requested Thai, Mandarin Chinese, Korean, Japanese, Hindi, Urdu,
Indonesian, Malay, Spanish and Brazilian Portuguese choices, plus the approved
Vietnamese, Filipino / Tagalog, Tamil, Telugu, Persian, French and German
additions. Include existing English, Bengali and Arabic as regression baselines.
Extend the coverage ledger to every supported language; unavailable or untested
speech must remain explicitly unmeasured.

Use [Google FLEURS](https://huggingface.co/datasets/google/fleurs), CC-BY-4.0,
with independent reference transcripts, source attribution and per-clip hashes.
The inspected dataset revision is
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`. Its public configurations include
`pt_br`, `es_419`, `th_th`, `cmn_hans_cn`, `ko_kr`, `ja_jp`, `hi_in`, `ur_pk`,
`id_id`, `ms_my`, `vi_vn`, `fil_ph`, `ta_in`, `te_in`, `fa_ir`, `fr_fr` and
`de_de`. These locale labels describe this test source, not all accents or
everyday dictation conditions.

Freeze sample selection before inference. Keep original and normalized reference
text, dataset/split/utterance identity, source filename and license separate from
model output. Use the same clips for a model comparison. Do not remove difficult
or empty results from the denominator. Do not choose samples after seeing errors.

The dataset viewer currently refuses the Thai row query because its Parquet
scan exceeds the service's 300 MB limit. A direct, pinned TSV plus a bounded
stream of the published test-audio archive is the implemented fallback. Do not
silently replace this with generated voices or an unreferenced audio sample.
The `tools.fetch_asr_corpus` helper implements that fallback, with
separate raw/normalized TSV references, pinned URLs, per-file SHA-256, license
attribution, byte/deadline/member limits and no filesystem archive extraction.
It takes the first eligible unique 1–60 second utterances in pinned archive order
before any inference; this is a small deterministic sample, not a representative
accent corpus. It records that the full archive checksum is not verified when
the transfer stops after enough clips. Both original audio and the full TSV are
retained. Existing output directories are refused; a failed partial remains
without a completed corpus manifest. This helper and its in-memory archive tests
pass their eighteen controlled acquisition/scoring tests. Actual acquisition is
complete for all twenty requested/approved and baseline languages; Telugu and
Persian initially timed out and succeeded in separately retained retry folders.

After verification, an explicit developer invocation is:

```powershell
python -m tools.fetch_asr_corpus --language th --samples 20 --output D:\saydraft-eval\fleurs-th-r1
```

Choose a new directory outside the repository. This command downloads public
evaluation data only; it opens no microphone and runs no recognition model.
Archive identity, transfer receipts and sample manifests must be checked before
an accuracy result can be trusted. The native multilingual scoring runner
in `tools.asr_accuracy` passes its controlled tests; the existing `bench_languages`
tool remains a script-only smoke. The first combined native run stopped after
86 of 500 cases when its execution session disappeared. Process inspection found
no scorer or coordinator; no native-exit receipt or final hashes were written.
That partial is retained and does not establish a completed result. Fresh
per-language runs use the same frozen clean source, clips and selection order,
with an observed child exit and post-run hashes for each language. All twenty
now finish: Whisper scores all 400 clips, while Parakeet scores the same 100
English, Portuguese, Spanish, French and German clips. The original partial is
not merged into that result. The retained record includes every raw output,
per-language corpus manifest, original report, process receipt and a portable
offline verifier that independently recomputes all 500 WER/CER pairs.

The scoring runner validates frozen TSV/reference/audio hashes before inference,
loads only explicitly supplied model directories, caches compatible engines, and
scores the same clips through ASR and deterministic cleanup. It writes an
incremental raw journal and per-language/model summaries. Empty or failed
recognition remains in the denominator. Chinese/Japanese/Thai use CER as their
primary diagnostic; all languages retain both metrics. Model hashes are checked
before/after and the source receipt must remain clean and unchanged for the
measurement-integrity flag. That flag is not an accuracy acceptance threshold.
AI cleanup, VAD trimming and OS firewall enforcement are outside this runner's
stated scope. Native scoring must use a clean, unchanged source checkout.

## Measurements and decisions

The [baseline table and full summaries](../eval/asr/results/2026-11-14-public-read/README.md)
keep each language/model separate. Bengali WER/CER is 84.95%/39.02%, Tamil
78.13%/38.44%, and Telugu 83.62%/42.01%; these failures need further decoder/model
investigation and untouched confirmation. The rejected Bengali 8-second-window
candidate is not promoted. English Parakeet has one empty output, retained in
the denominator. Brazilian Portuguese ties at 4.38% WER for both models on this
sample, which does not justify a regional model-default change. No production
decoder or routing default changes follow from this baseline alone.

All non-English transcripts pass through deterministic cleanup unchanged.
Three English model cases have worse literal scores after intended numeric or
ordinal formatting (`Twentieth` → `20th`, `two` → `2`, `three` → `3`). The raw
reference scores remain unchanged and the surface differences are disclosed;
no semantic-equivalence oracle replaces them. The global unmeasured list covers
80 remaining language codes, computed after combining all measured languages.

- Report each language's sample count, duration, empty-output rate, WER and CER
  separately. Use CER as the primary diagnostic for languages without dependable
  whitespace word boundaries, including Chinese, Japanese and Thai; retain both
  metrics with the exact normalization method disclosed.
- Preserve combining marks and native script distinctions. Accent/tone marks,
  negation, numbers, names and repeated words need regression coverage.
- Measure recognized text before cleanup, then score the final rules output on
  the same references. Record any cleanup regression separately from ASR error.
  Optional AI cleanup needs a distinct run and must retain the source on refusal.
- Compare Parakeet and Whisper for shared languages, especially Brazilian
  Portuguese. NVIDIA's [model notes](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
  describe European Portuguese training. A Portuguese language code alone cannot
  establish which model is best for Brazilian speech.
- Check language hints, mixed-language routing, unknown language evidence and
  pinned-language changes. A synthetic router test establishes configuration,
  not recognition accuracy. Add silence/noise checks without inventing transcripts.
- Retain mistakes, raw scores, manifests and model/source fingerprints. Choose
  improvements on a development set and confirm on untouched reference clips.
  Do not weaken acceptance thresholds or tune references to improve scores.

Public read speech can reveal regressions and compare candidates. It cannot
guarantee every accent, dialect, microphone, conversational pattern or noisy
environment. Publish measured scope rather than a blanket accuracy claim.

## Current implementation checkpoints

- Language choices use native engine codes and existing shared weights; selecting
  a language does not download anything.
- Non-English cleanup guards preserve words such as Portuguese `um`,
  German `er`, Polish `i` and meaningful native repetition.
- Production language evidence preserves `und`/`mul` for unknown/mixed
  speech, rather than assuming English. Background segments retain their own
  language evidence and join CJK/Thai boundaries without forced spaces. Multiple
  Parakeet pins can use the installed language detector for cleanup decisions,
  without enabling multilingual model fallback on an explicit route. English
  live-preview text cannot replace a primary mixed/unknown-language transcript.
- Regression cases span all registered non-English codes plus authored
  examples in the requested/approved language set. They are not native accuracy
  evidence. The focused app and scorer tests pass, alongside the existing rules
  and adversarial checks.
- Local UI/browser checks and public corpus acquisition pass. Clean source
  `e442880` passes global CI (4,000 tests / 12 explicit skips), rules 556/556 and
  adversarial 100/100. The separate clean `1b7e7ea` native accuracy baseline is
  complete. Quality improvements, untouched confirmation, mixed/noisy speech,
  other catalog languages and deferred owner accuracy remain open under P3.10.
