# Full large-v3/alignment confirmation protocol

Completed at clean `6cf5fc0`: all120 cases/121 Job exits and independent
original-input/portable verification pass, but the candidate fails its frozen
quality gate. Bengali CER worsens898→899/2204; bn1929, te1867 and te1937 add
replacement characters absent from their controls. All60 recordings are consumed.
[Full result and retained records](../../eval/asr/results/2026-11-15-full-alignment-confirmation/README.md).
The protocol below stays unchanged; no model/default promotion follows.

The [combined candidate](../../eval/asr/results/2026-11-15-full-alignment/README.md)
passes development; the production model and decoder remain unchanged. This
protocol admits exactly the previously reserved 20 public FLEURS test clips per
language for Bengali, Tamil and Telugu. It never selects clips by their outputs.
Owner speech, broader multilingual quality, licensing, latency and release
acceptance remain separate open requirements.

Before inference, the freezer checks all retained development records, independently
recomputes its scores/gates and exact control repeat, verifies both actual pinned
model caches and all original reserved corpus/audio/reference bytes, and requires
unchanged ASR source fingerprints and native runtime. The acquired first 20 clips
must reproduce the observed baseline. The next 20 IDs/audio hashes must match
the committed reservation, without duplicate or overlapping audio. The complete
60-clip suffix is mandatory.

Control: pinned production turbo with original default temperatures. Candidate:
the exact previously admitted full large-v3 cache, temperature zero, word timestamps.
Both retain language pins, beam five, no VAD/previous-text conditioning, normal
30-second padding and native maximum 448. Each arm/clip uses a fresh owned native
process with seed 1729 before model construction. Alternating arm order is fixed.
The final Tamil control repeats in a separate process outside the denominator.

The frozen gate requires **all three languages** to have non-worsening aggregate
WER and strictly lower CER, no new empty or replacement-character output per
clip, all 60 verified pairs, and an exact control repeat (text, scores, native
tokens and segments). Errors and missing results cannot disappear from the gate.
No aggregate across languages, revised reference or easier threshold can substitute.
Completion and integrity are distinct from passing the quality gate.

The 600-second per-child timeout is a process containment limit, not a latency
target. A timeout preserves partial outputs, terminates its owned Job tree and
requires observed whole-tree exit. Native cases run serially. The development
comparison took about 18 minutes for 19 fresh processes; the 121-process
confirmation is expected to take roughly two hours on the same CPU.

Before the first child starts, an exclusive consumption claim is written beside
the original public acquisition state. Its hash is retained in the parent report.
This claims all 60 clips for this single frozen test, including after a partial
or failed run. A new output folder cannot reclaim them as untouched. Original
acquisition records remain unchanged. Preserve failures and actual observed
cases; do not tune a replacement on these clips and call it confirmation.

With the exact guarded pinned runtime, clean committed source, original explicit
public caches and a new output directory outside the checkout:

```powershell
python -m tools.confirm_whisper_alignment --reserved-state D:\QA\reserved\state.json --output D:\QA\confirmation-new
python -m tools.probe_whisper_alignment run --plan D:\QA\confirmation-new\plan.json
```

The first command performs no inference. The second registers consumption before
the first native process. Both require the original committed reservation and
the existing model caches; neither downloads models or adds them to the app.
Public-file guards bar owner audio/device/input/clipboard/foreground services.
Python/local-only network protection is retained; native firewall enforcement
is unmeasured. No app promotion or release follows automatically from a pass.
