# Whisper word alignment: rejected development candidate

15 November 2026. **Keep the production decoder unchanged.** The frozen
word-alignment candidate improves Bengali, but increases Tamil and Telugu word
errors and Telugu character errors. It fails the pre-inference admission gate.
No reserved recording, model default, language route or app setting is changed.

The [retained records](../../eval/asr/results/2026-11-15-word-alignment/README.md)
cover nine already-observed development clips: the first three each for Bengali,
Tamil and Telugu from the [public baseline](../../eval/asr/results/2026-11-14-public-read/README.md).
They are Google FLEURS test speech, CC-BY-4.0, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`. These selected development cases are
neither representative language acceptance nor untouched confirmation. The
separate sixty Bengali/Tamil/Telugu confirmation recordings remain uninferred.

## Corrected paired result

| Three clips per language | Control WER | Alignment WER | Control CER | Alignment CER |
| --- | ---: | ---: | ---: | ---: |
| Bengali | 53/63 · 84.13% | 51/63 · 80.95% | 134/341 · 39.30% | 108/341 · 31.67% |
| Tamil | 28/37 · 75.68% | 30/37 · 81.08% | 106/302 · 35.10% | 88/302 · 29.14% |
| Telugu | 33/47 · 70.21% | 37/47 · 78.72% | 53/284 · 18.66% | 56/284 · 19.72% |

The gate required non-worsening aggregate WER and strictly better CER **for every
language**, with no new empty or replacement-character output per clip. It also
required complete verified pairs and an exact fresh-process control repeat.
No threshold, reference, normalization or difficult clip was changed afterward.
Tamil's lower CER does not override its failed WER gate. Telugu fails both.

## Intervention and reproducibility

The pinned faster-whisper 1.2.1 / CTranslate2 4.9.0 CPU int8 model is the existing
shared turbo model. Both arms retain language pins, beam five, default temperature
fallback, no VAD/previous-text conditioning, normal 30-second feature padding and
the 448 maximum passed to native generation. The candidate adds only
`word_timestamps=True`. The reviewed [alignment implementation](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
can change the next audio seek point; the experiment tests that behavior as a
possible missing-tail recovery. It changes no token ceiling or model weights.

Measured source `7f3c288` gives each arm/clip a fresh Python/native process, setting
seed 1729 before model construction. Eighteen cases form nine pairs. A nineteenth
case repeats the third Tamil control in another fresh process; its transcript,
score, native token sequences and segments match exactly. It stays outside the
accuracy denominator. Source, model, corpus, references, runtime, journals and
frozen criteria verify independently against the actual original bytes.

The earlier `a2cf1b7` shared-model run is retained separately. Its counts verify,
but it does not isolate alignment's effect: calling the seed API repeatedly does
not reset an existing worker's generator in the [pinned random implementation](https://github.com/OpenNMT/CTranslate2/blob/v4.9.0/src/random.cc).
The corrected experiment preserves all original criteria and adds the explicit
repeat requirement. The earlier failed counts are not substituted for its control.

## Process accounting and scope

The original fresh-run process receipts name the Windows venv redirector in their
`native_pid` field. Each executing interpreter independently identifies itself in
its report and guard receipt. Those original records stay byte-preserved; a
separate post-run observation confirms all nineteen actual worker PIDs absent.
The exact [CPython 3.13.17 redirector source](https://github.com/python/cpython/blob/v3.13.17/PC/venvlauncher.c)
waits for its child and propagates its result. Future probe runs distinguish the
launcher/actual PIDs and use the existing owned Job Object's whole-tree wait.
Three disposable-child checks, holding actual native process handles, verify
normal return, termination and Job closure with the same interpreter hash.

The current tool's 47 focused checks cover selection/prior-inference admission,
frozen gates, missing/duplicate pairs, native-result equality, import guards,
separate repeat counting and timeout/tree teardown. Native child profiles and
audio/weights are excluded from the committed evidence. No owner microphone,
device enumeration, clipboard, foreground or physical input is used. No AI
cleanup, native firewall, release latency or broad/owner accuracy is qualified.

## Reproduce the developer comparison

Use Windows 10/11, a clean committed checkout, the explicit verified turbo cache
and the prior observed-development selection plan. Choose a fresh output folder
outside the checkout; these commands perform no downloads.

```powershell
python -m tools.probe_whisper_alignment freeze --selection-plan D:\QA\observed-development\frozen-plan.json --model-dir D:\QA\turbo --output D:\QA\alignment-new
python -m tools.probe_whisper_alignment run --plan D:\QA\alignment-new\plan.json
```

The selection must match actual prior baseline inference records; merely labelling
unseen clips as development does not admit them. Each child receives an isolated
profile and bars owner audio SDK/input/clipboard services before app imports.
Timeouts preserve partial evidence and terminate the owned process tree.
Completed measurement is distinct from passing the quality gate. P3.10 remains open.

## Full large-v3 combination follow-up

A separate [frozen comparison](../../eval/asr/results/2026-11-15-full-alignment/README.md)
on clean `5825c03` combines the pinned QA-only full model, temperature zero and
alignment, retaining the same nine already-observed examples, control, criteria,
seed-before-construction and fresh process per arm/clip. Bengali word/character
errors fall 53→42/63 and 134→97/341; Tamil 28→14/37 and 106→25/302;
Telugu 33→26/47 and 53→48/284. Unlike the turbo-only alignment above,
all three pass. Nineteen whole owned Job trees exit, exact control reproduction
and independent original-input/score verification pass; 53 related tests pass.
This supports a frozen confirmation test, not broad accuracy or a production
change. The 60 reserved recordings remain uninferred at this snapshot. Full
model licensing and release performance remain separate gates.
