# Worker and native cleanup soak

`tools/soak.py` runs the actual SessionWorker, processor, private SQLite History
and Inserter with explicit in-memory capture/ASR, focus, keyboard and clipboard.
Every simulated paste checks that its matching raw/cleaned History row already
exists. Each cycle checks clipboard restoration; final counts must match.
It uses no microphone, foreground reads, global hooks or OS input.

The default is 200 synthetic cycles:

```powershell
.venv\Scripts\python -m tools.soak --cycles 200 --target synthetic --json
```

Synthetic success does not earn native-process credit. To exercise local cleanup
in the same process, add explicit installed model/runtime paths and a fresh QA
output directory. Full native runs require committed clean source and an
isolation declaration after stopping competing tests/builds/model transfers:

```powershell
.venv\Scripts\python -m tools.soak --cycles 200 --cleanup-model D:\Saydraft-QA\stories15M-q4_0.gguf --cleanup-runtime-dir D:\Saydraft-QA\llama-cpp-b12110-cpu-x64 --fixture-context-override --output D:\Saydraft-QA\native-soak-new --isolated --json
```

The context override is limited to the developer fixture with SHA-256
`6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04`.
Other local GGUF models use their normal context metadata; omit that flag.
No model/runtime is downloaded by either command. Native cleanup uses the pinned
runtime verification, hidden Job Object ownership and authenticated loopback API.
Vulkan recipes accept `--cleanup-backend vulkan --device Vulkan1` when appropriate
to the machine. The recipe uses one CPU thread, context 4096, temperature zero,
an 800 ms cap and a deliberate one-token output limit, without prompt preparation
or the interactive need/budget gate. It tests fallback/lifecycle, not model quality,
ASR, hardware tiers or release-to-text parity.

At least one ordinary cycle must provide genuine complete length-limited native
SSE evidence. Other ordinary cycles may hit the deadline; an ordinary protocol
failure is rejected. Missing/invalid streams cannot earn credit merely because
rules output survived.
Alternate cycles kill the owned model after tokenization. The requested kill
must actually occur. Cleaner replacement, normal deadline fallback, History
ordering and the real memory-clipboard insertion path run in one private profile.
No partial model output is published. Reports and a flushed metadata-only
`cycles.jsonl` remain in the output directory.

The RSS baseline follows initial model/service readiness and History schema
preparation. The end reading precedes shutdown, so teardown cannot hide memory
growth during the run. Both readings must be positive measured current-process
RSS, not a peak value or zero substituted for unavailable data. Model preparation
between cycles is recorded separately from worker cycle timing. `slow_cycles`
counts worker operations over the configured threshold; the legacy JSON field
`ui_freezes` is retained as an alias and does not measure GUI frame freezes.

Before success, runners shut down and every owned native exit must be independently
observed. Errors in preparation, cycles, measurement, reporting or teardown remain
failures. The native regression gate requires at least 200 completed cycles,
strictly less than 10% RSS growth, the original two-second slow-cycle threshold,
restored memory clipboard, complete matching History/insertion counts, genuine
native stream evidence and observed native shutdown. Debug subsets can complete
without earning this gate. Real Windows clipboard and physical input acceptance
remain separate owner checks.

`tools/probe_cleanup_app.py` delegates to this runner and retains its old path/
backend/fixture flags; its output now includes measured RSS and memory-clipboard
delivery rather than stub insertion alone. The old `--target notepad` only opened
a window while still using memory devices; it is rejected so it cannot imply
actual Windows insertion coverage. Use the explicit owned/manual Windows checks
in the [test checklist](TEST_CHECKLIST.md) for that scope.
