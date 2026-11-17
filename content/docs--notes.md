# Saydraft Notes — Local Scratchpad and Meeting Limits

Canonical: https://tanzir71.github.io/saydraft/docs/notes/

Press F10 to record a local voice note, or write in Saydraft Scratchpad. Learn offline saving, note review and the separate limits of meeting notes.

Facts checked: 2026-11-17

## Record a voice note

 

Press F10 to start, wait for Recording note, then press F10 again to stop. You can also use Record note in Hub → Notes. Esc cancels; the usual recording time limit applies. Change Record note in Settings → Shortcuts; the global binding works while listening is enabled.

 

The result saves to Notes and History without reading or inserting into the foreground app. Your open Scratchpad stays unchanged. Speech models must be installed; optional AI cleanup uses your chosen local model. If saving to Notes fails, recover your words from History.

 

## Open Scratchpad

 

Press Win + Alt + S, or choose New note in Hub → Notes. Scratchpad is a resizable plain-text window. Opening it starts no recording. You can type without an AI model, or dictate into its focused field using the normal shortcut and compatible installed speech models.

 

## Save a draft locally

 

A draft saves after a short typing pause. Closing the window or moving between notes waits for pending edits. An untouched blank draft creates no note. Reopening Scratchpad resumes its last saved draft, including after a later app launch. The draft and saved notes stay in the local app data.

 

If saving fails, the window keeps your unsaved text and offers recovery. A revision conflict refuses to overwrite another edit; Save as new preserves your draft separately. Review any discard confirmation before dropping text.

 

## Review saved Notes

 

Hub → Notes provides search and plain-text review. Scratchpad, Command, Ask and meeting results are independent note origins. Creating a meeting Note does not replace the active Scratchpad. Notes browsing does not record, inspect another app or need a network connection.

 

Copy uses the app’s Windows clipboard privacy handling. Windows clipboard history or sync can have separate behavior; read the [privacy boundaries](https://tanzir71.github.io/saydraft/privacy/) before copying sensitive text.

 

## Experimental meeting notes

 

Meeting notes are separate from ordinary Scratchpad. They require the Pro hardware profile, an explicit Labs opt-in, reviewed model downloads, selected inputs and participant permission. Enabling the feature or finishing a model download never starts recording.

 

The current source provides local recording/analysis controls and transcript review. Its complete live/frozen workflow, a 30-minute meeting and broad speech, speaker-label and summary accuracy are still unaccepted. Review names, decisions and task owners against the transcript. Do not treat generated notes as a verified record without that review.

 

See the linked implementation guide for current setup and recovery details, [model requirements](https://tanzir71.github.io/saydraft/docs/models/) for dependencies, and [shortcuts](https://tanzir71.github.io/saydraft/docs/shortcuts/) for rebinding.

## A few useful answers.

### What is the shortcut to record a voice note?

Press F10 to start and F10 again to stop while listening is enabled. The note saves locally in Notes and History without inserting into another app. You can change Record note in Settings → Shortcuts.

### Does opening Scratchpad start a recording?

No. Scratchpad is a local plain-text window. Type into it, or use your normal dictation shortcut while its field is focused. Dictation still needs compatible installed speech models.

### Are meeting notes fully qualified?

No. Meeting notes are an experimental Pro hardware-profile feature with explicit model setup, device selection and recording consent. Live and frozen workflows, a 30-minute meeting and broad speech, speaker and summary accuracy remain open acceptance work.

## Sources and further reading

- [Scratchpad, local saving and independent Notes ↗](https://github.com/tanzir71/saydraft/blob/main/docs/NOTES.md)

- [Experimental meeting setup and measured limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/MEETINGS.md)
