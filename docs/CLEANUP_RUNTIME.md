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

Validation: 550 tests pass, four optional native skips with real preview/Silero/LID
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

The sidecar manager must additionally use an absolute verified binary/model
path, loopback binding, `--offline`, a fresh authentication key and a sanitized
child environment. It must disable the web UI/tools/tunnel,
keep one process, health-check with a deadline, stop on failure/timeout and unload
after idle. Those behaviors require their own tests before P4.1 is checked off.
The [pinned server documentation](https://github.com/ggml-org/llama.cpp/blob/cd959bae99ff4bed22bef2604f45241c09bbb8c8/tools/server/README.md)
documents offline mode, `LLAMA_API_KEY`, web UI controls and idle sleeping.
