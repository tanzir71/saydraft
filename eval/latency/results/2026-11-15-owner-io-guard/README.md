# Guarded worker latency producer: controlled checks pass

Clean source `dc67cccdcaca97568df2fc3b5a1472e8a14b87a6` passes all 58 related
checks without skips in 8.49 seconds. Original pre-commit 58-pass results are
retained separately. These verify the producer and its refusal policy; they do
not measure model inference, release latency, physical input or native firewall.

The public-file guard installs before worker imports. A fixed fixture supplies
the immutable selected-context value and a foreground class whose construction
always raises. Seven actual fresh children verify a clean worker import, four
audio/input SDK import refusals before module bodies execute, and two refused
foreground constructors. The six negative receipts intentionally contain refused
attempts and cannot qualify a native measurement. The clean child and parent
receipts contain no attempts or imported audio SDKs.

Every latency child now enters through the guard. Parent validation requires
matching actual Python PIDs, clean terminal guard/fixture receipts and their
hashes. Full-matrix qualification also requires all those receipts. Tests retain
the original sample counts, exact nearest-rank thresholds, source/runtime/model
identity, model-use, History-before-paste and restoration checks; missing guard
evidence cannot earn acceptance. No current-source performance pass is claimed.

The actual `saydraft` Git tree matches current portable source `625c987` exactly;
the change is developer QA tools/tests/docs. The existing portable keeps its
original qualification and does not need rebuilding for these tools.

`manifest.json` binds 36 original logs, XML, receipts, source witnesses, runner
and summary records. Profiles, audio, databases and model binaries are excluded.
The scoped checks overlapped the separate frozen accuracy-only comparison;
its timings remain diagnostic. No performance benchmark ran concurrently.
All original accuracy inputs/options/seed/criteria and its separate checkout
remain unchanged. P4.6 and full Standard/Pro/native Windows acceptance remain open.

Portable, stdlib-only replay with Git history and no inference:

```powershell
python eval/latency/results/2026-11-15-owner-io-guard/verify.py.txt --repo .
```

For actual measurements use the guarded commands in
[the latency guide](../../../../docs/LATENCY_MATRIX.md), a clean source checkout,
the explicit installed models and a fresh output. Run performance recipes serially.
