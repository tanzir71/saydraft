# Session service refactor

`saydraft/core/session.py` owns lifecycle transitions and session generations.
`worker.py` runs capture and final processing through one serial executor, with
injected audio, recognition, cleanup, formatting, context, history and insertion
ports from `interfaces.py`. `container.py` constructs the default adapters.
The Qt shell forwards signals; the retired worker module has been removed.

Context is captured when recording starts. Repeated dictations are retained.
Cleanup failures use raw words; formatting failures keep available cleaned words.
History precedes insertion. A history failure refuses insertion and retains both
versions in a pending recovery list, including across settings reloads. Cancellation
checks the session generation immediately before insertion. An in-flight ASR may
finish and save its transcript after cancellation or shutdown, but cannot paste.

Configuration changes wait for the active session. A microphone startup failure
resets the hotkey state. Esc cancels capture or processing; short recordings are
discarded. The old configurable warning/cap and three-second history-only shortcut
remain. Native keyboard hook replacement and the final shortcut defaults follow P5.

The synthetic soak now uses the session worker, actual temporary SQLite storage,
cleanup and insertion service with injected devices. Its 200-cycle run passed
with no failures, no freezes and no measured RSS increase. This is not a physical
microphone or foreground-app soak.

## Windows boundary verification (2026-11-12)

A temporary fixture harness ran cached faster-whisper base under NetworkGuard,
fed the bundled three-second WAV through the session worker, persisted one real
history row, and inserted into a fresh Notepad tab using the typing fallback.
The screen showed the complete recognized sentence, `Hello from Voice Tree.`
(22 characters); the worker reached `Done`, reported `inserted`, and exited 0.
The clipboard was untouched. The fixture harness/profile are retained under the
ignored `build/qa/` tree. This checks recorded-fixture processing and native input;
live microphone capture remains part of the manual checklist.

The original keyboard-library typing path dropped a character during the first
run. The fallback now sends batched UTF-16 key-down/up pairs using Windows
SendInput and rejects partial OS delivery. Encoder tests cover Bengali, Arabic,
surrogate pairs and partial delivery. All-format clipboard support and UI
Automation context still follow P5.2–P5.3.
