# Saydraft Windows Shortcuts — Dictation and Hands-Free

Canonical: https://tanzir71.github.io/saydraft/docs/shortcuts/

Learn Saydraft's hold-to-talk, hands-free, cancel, paste-last, Scratchpad and History shortcuts, with custom bindings and conflict checks.

Facts checked: 2026-11-14

## Everyday defaults

 

| Keys | Action |
| --- | --- |
| Ctrl + Win | Hold to speak; release to finish |
| F9 | Alternate hold-to-speak shortcut |
| Ctrl + Win + Space | Toggle hands-free recording |
| Escape | Cancel the current recording or pending action |
| Shift + Alt + Z | Paste the last saved dictation |
| Win + Alt + S | Open Scratchpad |
| Ctrl + Win + D | Open the latest History diff |

 

The native app is still in development, including physical Windows shortcut acceptance. Start in an ordinary editable text field and review the result.

 

## Hold, toggle or double-tap

 

For a short draft, hold the dictation shortcut and release when finished. For hands-free use, toggle with Ctrl + Win + Space, then use the same toggle to stop. Double-tapping the same hold shortcut can also lock recording; its interval can be changed or disabled in Settings. A single short tap does not lock recording.

 

The default recording cap is twenty minutes, with a warning at nineteen minutes. Saved custom limits remain respected. Escape cancels; a very short accidental recording can be discarded rather than inserted.

 

## Change a binding

 

Use Settings → General, or the Shortcut page during first-run setup. Learn shortcut captures keys only while setup stays focused and times out after ten seconds. Escape cancels learning. You can also enter a supported chord manually and check for conflicts before saving.

 

The app checks conflicts among its own shortcuts. The Wispr Flow advisory is separate and does not inventory every application’s shortcuts. Windows or an elevated app may reserve a combination; choose another binding if needed.

 

## Editing shortcuts are separate

 

Experimental Command Mode uses Ctrl + Win + Alt when enabled in Labs with the Pro profile and editing model. Hold it for an instruction and wait for the Command label before speaking. It does not use hands-free or double-tap behavior. See [Command Mode](https://tanzir71.github.io/saydraft/docs/command-mode/).

 

Paste-last is for saved dictations. It does not replay a selected-text Command or Ask result into a new field. Use the appropriate result’s explicit Copy action.

 

## If the destination changed

 

Delivery checks the target again. A changed, protected or elevated field may prevent insertion; use History to recover the saved words. Troubleshoot with [delivery and shortcut checks](https://tanzir71.github.io/saydraft/docs/troubleshooting/) rather than repeatedly triggering a recording in an unknown field.

## A few useful answers.

### Will an upgrade overwrite my custom shortcut?

Existing custom bindings are preserved. Settings provides conflict checks and explicit disable/reset choices; a conflicting new default is not silently forced onto an existing profile.

### Does paste-last run recognition again?

No. Shift + Alt + Z replays the last saved dictation through the guarded delivery path, without a new recording or cleanup request.

## Sources and further reading

- [Native shortcuts and current Windows acceptance scope ↗](https://github.com/tanzir71/saydraft/blob/main/docs/HOTKEYS.md)

- [Recording cap and warning behavior ↗](https://github.com/tanzir71/saydraft/blob/main/docs/RECORDING_LIMITS.md)
