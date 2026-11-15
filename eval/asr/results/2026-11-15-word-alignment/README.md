# Word-alignment development verification — 15 November 2026

**Reject the candidate; production remains unchanged.** The corrected native
comparison source is `7f3c288`; current QA/process-accounting source is `119fb49`.
The [investigation](../../../../docs/spikes/whisper-word-alignment.md) has the full
method, raw denominators, source links and limitations.

Nine already-observed public FLEURS clips (three each for bn/ta/te) produce
eighteen paired cases plus a nineteenth fresh-process control repeat. Seed1729
is set before model construction; the repeat matches transcript, scores, native
token sequences and segments exactly and stays outside the accuracy denominator.
Original model/audio/reference/source/runtime/journal/criteria checks pass.
Bengali word/character errors fall53→51/63 and134→108/341; Tamil word errors
increase28→30/37; Telugu word/character errors increase33→37/47 and53→56/284.
Every language had to avoid worse WER and strictly improve CER; the gate fails.

The earlier `a2cf1b7` shared-worker experiment is byte-preserved in comparison-r3.
Its scores verify but seed calls do not reset an existing CTranslate2 thread's
generator, so it does not isolate the alignment effect. Comparison-r4 corrects
the initialization with fresh processes and adds the stricter repeat requirement.
Two zero-case pre-inference DLL-import refusals and the original guard/verification
findings remain. No failed record or reference has been repaired or substituted.

Original r4 process receipts identify the venv launcher as native_pid; the actual
executing PID is independently in each child report/guard. Raw receipts remain
unchanged. actual-worker-exits.json confirms all19actual workers absent after
completion. The CPython3.13.17 source and exact-interpreter normal-return probe
explain exit propagation. Current QA code separately records launcher/actual IDs
and waits for the whole owned Job Object tree. Three held-handle lifecycle probes
verify normal return, terminate and Job closure. Final47focused tests/2explicit
native integrations deselected and Ruff pass. The current Job parent has separate
denominator/timeout contract checks; it is not falsely labelled as the r4 producer.

The public data is Google FLEURS, CC-BY-4.0, revision
70bb2e84b976b7e960aa89f1c648e09c59f894dd. Corpus manifests retain attribution,
raw/normalized references and audio hashes; no audio/weights or profiles are
copied. Inputs are public files only, with audio SDK/device/input/clipboard/profile
guards before app imports. No microphone, foreground, capture or physical input
is used. The60reserved confirmation clips remain uninferred. No owner/broad
accuracy, AI cleanup, release latency, native firewall or full-goal acceptance.
No app/model/default/route, package, release, PR, Actions or hosting change.

Portable replay needs this Git history, not original audio/models:

```powershell
python eval/asr/results/2026-11-15-word-alignment/scripts/verify_whisper_alignment_fresh_20261115.py.txt --run eval/asr/results/2026-11-15-word-alignment --repo .
```

Add --original-inputs only on the original QA machine with the explicit public
cache paths retained in the plan. That separately rehashes actual model/audio/TSV
and prior-inference bytes. Source and retained-record hashes are checked without
altering historical evidence. Measurement completion is distinct from the failed
quality gate. P3.10 and the full original implementation goal remain open.
