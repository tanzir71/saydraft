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

`InsertionResult.enter_sent` reports a fully accepted Return press/release pair. A post-insert
focus/cancellation/check failure returns `inserted` plus `enter_<reason>`, and
an Enter injection failure returns `inserted`/`enter_failed`; text is not pasted
again. Failures before paste remain uninserted. Typing fallback uses the same
post-delivery gate. Windows Return is one `SendInput` virtual-key press/release
pair. Partial native delivery attempts key-up only, never a second key-down.

Settings → Cleanup → Voice command enables `dictation.voice_enter_enabled`,
which defaults off and survives config reload/service reconstruction. The
processor reads source intent before rules/LLM/snippets, retains the complete
raw transcript and saves `voice_enter` requested metadata before insertion.
History-only Notes/retries do not parse a delivery command. A worker cancellation
signal is set before taking the insertion lock, so Esc during paste suppresses
the trailing Return; the next recording clears the signal. Password/unknown
targets, failed History and stale generations still refuse insertion.

Snippet triggers are masked through cleanup and expanded once afterward;
expansions cannot generate an Enter action. They retain fillers, numbers,
backslashes, code and literal case. Final punctuation is deferred until after
expansion, with one duplicate external full stop coalesced when the snippet
already supplies a terminal stop. Literal ellipses stay untouched. Accepted model
punctuation cannot duplicate a signature's final stop. No snippet expansion is
sent to the model as part of this replacement path.

When native delivery fails after text insertion, the notice says Enter delivery
could not be confirmed: a partially accepted key-down cannot be undone. There is
no automatic retry. All checks use injected keyboard/clipboard/focus/cancellation
ports or a native-input sender stub; no live key/application action is issued.

Foundation validation: 1239 tests pass with four optional native skips and real
local Silero/preview/language-ID fixtures enabled; golden 380/380, adversarial
100/100, Ruff and diff checks pass.

Integration validation: 1268 tests pass, four optional native skips, with those
same local fixtures; golden 432/432 compares text and action flags through the
actual processor; adversarial 100/100; Ruff/diff pass. Settings was rendered and
visually checked at `build/qa/voice-enter-ui-20261112/cleanup-settings.png` with
Segoe UI fonts. Automatic app classification/UIA and richer clipboard behavior
remain P5.2/P5.3; Email/Docs exclusions use the captured group or legacy profile.
