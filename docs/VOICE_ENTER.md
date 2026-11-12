# Trailing Enter delivery

The P4.5 command is opt-in: an unquoted trailing `press enter` is stripped from
the original dictation, and Return follows successful text delivery. Email and
Docs groups are always excluded, as are their legacy Email/Notes profiles.
Raw and Code can use this separately enabled delivery command; prose cleanup
mode does not grant permission to send it.

The parser in `cleanup/delivery.py` is pure and defaults off. It accepts a final
ASR period/exclamation, supports Unicode content before the English cue, and
keeps literal mentions, questions, incomplete quotes/backticks, typed code
comments, standalone commands without text and non-trailing phrases. It removes
an ASR separator comma before the cue. It never reads model output or snippets.

`Inserter.insert_text(..., send_enter=True, enter_guard=...)` checks captured
foreground focus and cancellation before text delivery, again immediately
before paste, then after insertion and clipboard restoration before Return.
Unavailable/failed checks refuse the action. Normal insertion keeps its existing
behavior when no Enter is requested. Rich clipboard preservation and focused
control/UIA enrichment remain P5.2/P5.3.

`InsertionResult.enter_sent` reports successful Return delivery. A post-insert
focus/cancellation/check failure returns `inserted` plus `enter_<reason>`, and
an Enter injection failure returns `inserted`/`enter_failed`; text is not pasted
again. Failures before paste remain uninserted. Typing fallback uses the same
post-delivery gate. Windows Return is one `SendInput` virtual-key press/release
pair. Partial native delivery attempts key-up only, never a second key-down.

This foundation does not enable the feature or strip commands in the app yet.
Processor/Settings wiring, source-intent History metadata, worker cancellation
and golden action/snippet coverage follow in the next reviewable change. All
tests use injected keyboard/clipboard/focus/cancellation ports or a native-input
sender stub; no live key or application action is issued.

Foundation validation: 1239 tests pass with four optional native skips and real
local Silero/preview/language-ID fixtures enabled; golden 380/380, adversarial
100/100, Ruff and diff checks pass.
