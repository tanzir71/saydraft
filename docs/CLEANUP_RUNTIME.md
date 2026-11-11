# Local cleanup runtime

The app's future sidecar uses the Windows x64 llama.cpp build referenced by
[stable release v0.9.0](https://github.com/ggml-org/llama.cpp/releases/tag/v0.9.0):
binary release **b12110**, source commit
`cd959bae99ff4bed22bef2604f45241c09bbb8c8`. Both archives and every selected
payload are SHA-256 pinned in `saydraft/models/manifest.json`.

| Package | GitHub asset | Download bytes | Installed bytes |
|---|---:|---:|---:|
| CPU x64 | 709507579 | 24,708,445 | 46,872,915 |
| Vulkan x64 | 709511274 | 37,661,146 | 88,861,523 |

Both catalog entries require Windows x64 and an AVX2 CPU. They contain the server
executable, its implementation/common/model DLLs, the CPU dispatch backends,
OpenMP and the full OpenMP license notice. Vulkan additionally contains the
graphics backend. The complete pinned ggml MIT license is copied before
publication. The CPU and Vulkan binary report matches build 12110/commit cd959bae9.

Only required server dependencies are selected. A static PE import audit found
that `llama-server.exe` depends on `llama-server-impl.dll`, whose closure includes
`llama-common.dll`, `llama.dll`, `mtmd.dll`, `ggml.dll`, `ggml-base.dll` and
`libomp.dll`. The archive's command-line utilities, RPC backend/server and tunnel
helper are omitted. The system still needs the Microsoft Visual C++ x64 runtime;
clean-machine packaging validation and actionable missing-runtime handling remain
part of the sidecar/installer work.

`download_cleanup_runtime(backend)` is an explicit setup helper. It accepts only
the pinned CPU/Vulkan choices, uses the existing staged archive installer,
supports pause/resume and preserves old versions and partial work. It writes to
the per-user `models/runtime/<catalog-id>` directory. Runtime packages never
appear in the speech-model picker. There is no automatic download or new app
startup behavior in this foundation change; controls and lifecycle follow.

Actual cached installations verified all payloads and notices with **zero network
calls**. Both installed executables ran `--offline --version` in hidden processes
and exited successfully without opening a server or loading a model. This checks
the installed dependency closure on the development machine, not clean-machine
deployment, GPU inference, request deadlines or process ownership.

Validation: 571 tests pass, four optional native skips with real preview/Silero/LID
enabled; cleanup evaluation 42/42; Ruff and diff checks pass.

`cleanup.llm.windows_process.WindowsJobProcess` now supplies native process
ownership. It uses Windows 10's creation-time `PROC_THREAD_ATTRIBUTE_JOB_LIST`
with kill-on-close limits, closing the suspended-create/assign orphan window
described by [Microsoft](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812/).
An explicit handle list inherits only NUL standard I/O. The job handle is never
inherited, no breakaway is enabled, no shell runs and no console window opens.
Arguments preserve literal Unicode/quotes and the environment must be explicit.

Native tests verify exact Job membership, literal arguments, NUL stdin, polling,
finite wait deadlines, valid exit code 259, termination of descendants, explicit
close and abrupt owner exit via `os._exit` without Python cleanup. Repeated native
creation failures show no additional owner-handle growth after loader warmup.
Both pinned binaries launch through this wrapper and exit successfully on the
offline version check. The helper releases native handles on failure and closes
idempotently. Imports still start no process.

`cleanup.llm.loopback.LoopbackClient` supplies bounded authenticated JSON to a
fixed `127.0.0.1` address. Endpoint allowlists reject arbitrary URLs and redirects;
proxy environment variables are ignored. Request/response bodies are capped at
1 MiB and JSON/content types are checked. Exceptions contain only failure
metadata, never prompts, response bodies or keys. It works under NetworkGuard
without opening a download scope.

An absolute deadline watchdog shuts down a duplicate of the connected socket.
This interrupts trickled headers and bodies even when ordinary per-read socket
timeouts would keep resetting, including Connection: close responses whose body
outlives HTTPConnection's socket reference. Local server tests cover Unicode,
authentication failure, redirects, invalid/nonfinite JSON, wrong content types,
declared/streamed size overflow and slow headers/bodies. No app requests start
from construction or imports; manager integration follows.

A real pinned CPU server also passes this path under NetworkGuard, inside the
owned hidden process wrapper: health becomes ready, `/v1/models` reports the
configured alias, a completion returns sixteen tokens, and a wrong key on
`/tokenize` receives HTTP 401. This uses a developer-only 1,185,376-byte
`stories260K.gguf` from
[`ggml-org/tiny-llamas` revision 99dd1a73](https://huggingface.co/ggml-org/tiny-llamas/tree/99dd1a73db5a37100bd4ae633f4cfce6560e1567),
SHA-256 `047bf46455a544931cff6fef14d7910154c56afbc23ab1c5e56a72e69912c04b`.
The [original tinyllamas card](https://huggingface.co/karpathy/tinyllamas) identifies
MIT licensing. The fixture is excluded from app choices and distributed assets;
it tests API/lifecycle behavior and supplies no cleanup-quality evidence.

`cleanup.llm.sidecar.SidecarManager` now owns one server with explicit preparation
or background warming. It verifies installed runtime hashes and hardware before
launching, uses a fresh port/key and a minimal child environment, authenticates
readiness through `/tokenize`, and serializes requests without queuing a second
one. Requests made before readiness return fallback control immediately while
warming installed files. Nothing downloads. CPU uses zero GPU layers; Vulkan
uses the documented automatic layer selection. The optional prompt cache is
disabled with `--cache-ram 0`; idle-slot caching and context shifting are disabled.

Request failure/timeout stops the process and retries with bounded exponential
backoff, capped at three restarts by default. A new process never starts before
the previous main process's exit is observed. A successful request resets the
failure count. The fifteen-minute idle default unloads without restarting; the
next warmup can reload. Close cancels timers, kills the owned job, prevents late
preparation from spawning and rejects responses arriving after closure. Errors
return static metadata and no result, allowing the caller to keep rules output.

Deterministic tests cover reuse, late-result rejection, key replacement, backoff
and restart caps, missing/corrupt installations, a slow-to-exit old process, idle
reload, stale timers, concurrent requests and closure during verification/I/O.
Native CPU probes additionally verify completion/idle/reload, interruption and
absolute deadlines. Killing an active request returned fallback control in
**0.028 s**; an **0.080 s** deadline returned in **0.091 s**. Vulkan preparation
and a sixteen-token completion also pass. These are control-flow observations,
not cleanup-quality or general latency measurements. App/prompt integration is
still pending, so P4.1 remains unchecked.

The interruption fixture is a separate developer-only `stories15M-q4_0.gguf`,
19,077,344 bytes, from the same pinned ggml-org revision, SHA-256
`6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04`.
The original 260K fixture stopped at its token/context limit before the timed kill
could exercise interruption. Both unsuccessful probe notes are retained; the
larger fixture supplies the passing interruption check. Neither is an app model.

The sidecar manager must additionally use an absolute verified binary/model
path, loopback binding, `--offline`, a fresh authentication key and a sanitized
child environment. It must disable the web UI/tools/tunnel,
keep one process, health-check with a deadline, stop on failure/timeout and unload
after idle. Those behaviors require their own tests before P4.1 is checked off.
The [pinned server documentation](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/tools/server/README.md)
documents offline mode, `LLAMA_API_KEY`, web UI controls and idle sleeping.
