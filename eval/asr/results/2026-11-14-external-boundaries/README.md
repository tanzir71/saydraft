# External Whisper segmentation · rejected development candidate

Frozen clean `1b7e7ea` and the installed pinned turbo model score nine
already-observed FLEURS clips: the first three each for Bengali, Tamil
and Telugu. This is development evidence, not an untouched acceptance set.
Public references are [Google FLEURS](https://huggingface.co/datasets/google/fleurs),
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`. Original reference text, model
outputs, raw error counts and sample identities are retained unchanged.

The candidate chooses quieter boundaries between three and six seconds,
preferring a quiet point close to five seconds. If none meets the frozen
RMS threshold, it chooses the lowest-energy point in that interval.
It retains every sample exactly once, uses the production transcript
joiner and normal 30-second feature padding, and changes no decoder/token
limit. The plan and complete probe bytes were frozen before inference.

| Language (3 clips each) | Baseline WER % | Candidate WER % | Baseline CER % | Candidate CER % |
| --- | ---: | ---: | ---: | ---: |
| Bengali | 84.13 | 90.48 | 39.30 | 35.78 |
| Tamil | 75.68 | 105.41 | 46.03 | 71.85 |
| Telugu | 70.21 | 85.11 | 18.66 | 39.44 |

**Reject the candidate.** Combined development word errors increase from
114 to 136 and character errors from 326 to 451. Bengali CER improves
slightly while its WER worsens; Tamil and Telugu regress on both metrics.
WER can exceed 100% when insertions outnumber reference words. No global
cross-language accuracy percentage or latency qualification is inferred.
Production decoder/model/routing defaults remain unchanged.

The child exits zero and all original source, script, plan, corpus/audio,
reference, baseline journal, model pin and score hashes pass independent
verification. Every recomputed boundary and actual sample round-trip is
verified on the original machine. Native calls retain the standard
448 maximum and 224 per-call generated-token ceiling; this does not
establish that the ceiling explains all recognition errors.

Run `python verify-scores.py.txt` in this directory for the portable
stdlib-only hash/score/sample-range replay. It does not contain audio or
recheck the original model/audio bytes; the original-machine receipt and
verifier document those separate checks.

The separate acquisition snapshot in `holdout/` contains 40 verified
clips per language: the original 20 reproduce the baseline audio/IDs,
and the next 20 are disjoint. All 120 audio/reference/TSV hashes and the
acquisition child exit are independently verified. The 60 newly acquired
confirmation clips have no model inference at this snapshot. They are
reserved for a candidate that passes development; any future evaluation
must record their consumption and stop calling them untouched.

Proof-only commit `26dd660` also exposed a legacy-source scanner false
positive: its unchanged historical ASR source snapshot contains a generic
scope label matching an old package name. The [failed CI](26dd660-ci.json)
and [original failure output](26dd660-ci-failure.txt) are retained.
Commit `3e1620c` prunes only `eval/**/results` evidence from that scan.
Seven local checks still detect injected legacy imports in runtime,
tools, actual evaluation sources, requirements and an app results folder.
No historical source bytes or app dependencies are changed. Fresh global
verification is separate from this ASR development result.
