# Policy replay after deadline changes — 2026-11-13

Immutable source `1486b091f6a0af6bffbb306a615b05eae82c0d1d` applies the
absolute budget to every socket read/write and avoids per-request watchdog/idle
timer creation. Both serial policy jobs completed all 556 golden and 100
adversarial cases with the production need/budget gate and 800 ms cap enabled.
Weights/cards/licenses and CPU/Vulkan b12110 runtime payloads were rehashed before
loading. Four CPU threads, context 4096 and temperature zero were fixed. All owned
native exits were independently observed before the next job.

| Recipe | Golden exact | Accepted golden replies / token-counted replies | Decode median tok/s | Slowest timed case | Timeouts |
|---|---:|---:|---:|---:|---:|
| Qwen3.5 0.8B CPU | 556/556 | 0/0 | 20.74 | 53.6 ms | 0 |
| Qwen3.5 2B RTX 3060 Vulkan1 | 556/556 | 269/278 | 114.80 | 315.6 ms | 0 |

Both runs have zero golden regressions and no finite preservation failures.
All 100 adversarial policy inputs per recipe skipped for low need; actual
adversarial generation remains established separately by the unchanged
[forced matrix](../2026-11-13-word-guard/README.md).

CPU calibration samples were 20.10, 20.74 and 20.75 tok/s. Its 279 budget skips,
125 low-need skips, 132 bypasses and 20 Verbatim skips keep deterministic rules.
The CPU result cannot earn hybrid-quality credit or the 25 tok/s Standard tier.
RTX samples were 117.56, 114.80 and 111.83 tok/s; prediction uses the minimum,
not the median. Nine token-counted golden replies were rejected; only 269
accepted replies earn model credit. The combined checker intentionally refuses
the pair with `Rules fallback cannot earn accepted model credit`.

Case timing excludes explicit background startup, decoder calibration and static
prefix preparation. These maxima describe synthetic processor cases with stub
delivery, without ASR or physical insertion. They do not establish cold/warm
release latency, owner accuracy, a hardware tier or a model default. The original
[failed CPU policy run](../2026-11-13-policy/README.md) remains unchanged.

Two additional owned CPU fault probes retain their original JSON bytes:

- `faults-initial.json`: an 80 ms deadline returned fallback control in 85.3 ms
  without output. The initial interruption setup then timed out after 828.0 ms
  before observing a generated token; that command failed and does not prove
  mid-generation interruption. Both native exits were observed.
- `faults-cached.json`: the exact public synthetic input was primed outside timing.
  The timed request retained its 800 ms cap. After an actual nonempty generated
  delta, the probe killed its owned sidecar. Fallback control returned 9.6 ms
  after termination began, 101.3 ms after the request began. No partial text was
  published and native exit was observed. This is a cached-input fault check.

`idle-reload.json` additionally verifies activity across repeated native requests,
quiet-period unload, observed old-process exit before reload, and fresh generation
and credentials. Its explicit probe interval is 250 ms; production remains 900 s.
Twenty requests keep the reloaded model active for 695 ms; only five timers start
across the complete two-load check. Both native exits are observed.

`app-soak-100.json` retains 100 synthetic SessionWorker/processor cycles with
100 History rows and 100 checked stub insertions. It exercises 34 ordinary
length-limited streams, 16 deadline fallbacks and 50 injected terminations after
tokenization. All 66 owned sidecars exit after shutdown. The pinned developer-only
15M fixture uses its explicit context override and makes no cleanup-quality claim.
The slowest release-to-stub cycle was 1.134 s, including processor/History work;
that timing scope differs from the policy case and fault measurements above.
`app-soak-source.json` retains the source/exit receipt. This check does not establish
the separate §11 200-cycle RSS/clipboard gate.

`index.json` pins unchanged reports, private case-journal hashes and command
outcomes. Source and prompt fingerprints match this implementation;
preservation guards/prompts still match the separately retained forced reports.
No microphone, clipboard, owner recordings or OS input was used. The full
200-cycle RSS/clipboard gate, CPU hybrid credit and broad release/tier acceptance
remain open; no requirement was lowered to turn fallback into model credit.
