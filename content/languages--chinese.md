# Chinese Voice Typing for Windows, Offline | Saydraft

Canonical: https://tanzir71.github.io/saydraft/languages/chinese/

Dictate Mandarin Chinese on Windows with Saydraft. Free, open-source offline voice typing using a shared multilingual speech model.

Free, open-source dictation

# Chinese (Mandarin) voice typing for Windows.

中文（普通话）

Turn spoken Mandarin Chinese into text without a cloud transcription service. Saydraft runs its multilingual speech model on your own Windows PC.

Choose Chinese (Mandarin), language code zh. Cantonese is listed separately as Chinese (Cantonese), code yue. Both use the shared All languages model, but they are separate language choices; a Mandarin pin is not a promise of recognition for every Chinese dialect.

Requires the shared All languages speech model (Whisper large-v3-turbo, approximately 1,621.7 MB). Download once in setup or Models, then reuse it offline.

## How to set up Chinese (Mandarin) dictation

- Follow the [current download and source setup instructions](https://tanzir71.github.io/saydraft/download/). Saydraft is a development preview for Windows 10 and 11.

- In Hub → Settings → Models, review the required model’s size and license. Choose Download / Resume if it is missing; Pause is available.

- Open Languages, enable automatic model choice, and select Chinese (Mandarin). Save your settings. A single language pin uses code `zh`.

- Put the cursor in an editable app field, hold Ctrl + Win, speak, then release. Review the transcript before sending it.

Language selection starts no transfer. If automatic routing is off, the model selected on Models remains in use; select a compatible model there. For more detail, see the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/).

## Use your voice in everyday Windows apps

Draft a Chinese message, collect thoughts in a note or dictate into an editable document. The current language choice supplies a recognition hint. It does not offer a Simplified/Traditional conversion setting, so review the characters and punctuation before sending.

Speech recognition and text cleanup run locally. There is no account or cloud transcription fallback. With compatible models installed, you can dictate without an internet connection. Optional AI cleanup has its own model requirements; rules-only cleanup needs no text model.

## Can I choose Simplified or Traditional Chinese output?

Saydraft currently exposes the model’s language choice, rather than a separate Chinese script converter. Its Chinese setting uses zh. If your document requires a particular script, review and convert the result with a tool you trust.

## What does language support mean here?

This page describes speech-model coverage and app configuration. It does not claim a measured accuracy score for Chinese (Mandarin). Accent, microphone, background noise and mixed speech affect results. The language choice does not translate the app interface or add Translate-mode output targets.

[Get Saydraft for Windows](https://tanzir71.github.io/saydraft/download/) · [See how dictation stays local](https://tanzir71.github.io/saydraft/privacy/)
