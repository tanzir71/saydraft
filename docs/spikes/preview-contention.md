# Preview alongside final recognition, 2026-11-12

Both recognizers ran simultaneously on CPU using four threads each, with
Parakeet v3 Auto routing and the local Whisper tiny language detector. All weights
were verified and prepared before the real-time feed. NetworkGuard was active;
native telemetry was disabled. No microphone, History write or insertion occurred.

The bundled eight-second toy fixture repeats to the requested duration. Capture
feeds owned 100 ms chunks into independent final-ASR and bounded preview queues.
Only native decode/result callbacks during capture contribute to cadence; text
changes are counted separately. The first and last one-second windows are omitted
from the steady-window minimum. These are fixture checks, not accuracy results.

| Measurement | 8 s, default final ASR | 60 s, streaming flush requested |
|---|---:|---:|
| Preview result callbacks | 49 | 374 |
| Callback rate | 6.12/s | 6.23/s |
| Minimum callbacks per steady second | 5 | 5 |
| Actual text changes | 6 | 89 |
| Final-ASR segments | 3 | 16 |
| Preview / final-ASR failures | 0 / 0 | 0 / 0 |
| Release → available raw results | 0.291 s | 0.622 s |

Default mode discards preview at release, skipping its padding/flush. The second
run requests the complete streaming result while final recognition finishes in
parallel. Normal final output remains nonempty in both. Release timing excludes
cleanup, History and insertion, and does not establish a latency distribution or
parity on other hardware. The machine has six physical/twelve logical CPU cores;
the GPU was not used by these recognizers.

An earlier minute-long run overlapped a separate native regression test on the
same machine. Preview stopped after approximately thirteen seconds; final ASR
still completed sixteen segments and returned text. Its original report is kept
as a failed stress result, not substituted with the passing one. Failure-reason
metadata was subsequently added. The isolated rerun above passes without changing
the two-second backlog limit. Synthetic tests separately prove the overflow
reason, suppressed late callbacks and preserved incomplete preview words.

Run the performance probe without concurrent native tests for comparable results:

```powershell
python -m tools.bench_preview --preview-dir C:\qa\verified-preview --parakeet-dir C:\qa\verified-parakeet --lid-dir C:\qa\verified-lid --seconds 60 --streaming-result --output build/qa/new-preview-contention.json
```

The helper closes both queues on success or interruption. It requires explicit
installed model directories and never downloads. Omit `--streaming-result` to
measure default release behavior. Final adapter/unit validation remains 494 pass,
four optional native skips with real preview/Silero/LID enabled; cleanup eval
42/42 and Ruff pass. P3.7 still awaits the opt-in app/Bar integration.
