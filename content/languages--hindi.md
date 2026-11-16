# Hindi Voice Typing for Windows, Offline | Saydraft

Canonical: https://tanzir71.github.io/saydraft/languages/hindi/

Free, open-source Hindi voice typing on Windows. Dictate offline with Saydraft using a shared local multilingual speech model.

Free, open-source dictation

# Hindi voice typing for Windows.

हिन्दी / हिंदी

Turn spoken Hindi into text on your Windows PC. Saydraft uses the installed All languages model for local Hindi speech recognition, with no cloud transcription account.

Select Hindi, language code hi, in Languages. Hindi and Urdu are separate recognition choices, even though their model files are shared. Pin Hindi alone to give the decoder a direct language hint, or pin it with English for a multilingual workflow.

Requires the shared All languages speech model (Whisper large-v3-turbo, approximately 1,621.7 MB). Download once in setup or Models, then reuse it offline.

## How to set up Hindi dictation

- Follow the [current download and source setup instructions](https://tanzir71.github.io/saydraft/download/). Saydraft is a development preview for Windows 10 and 11.

- In Hub → Settings → Models, review the required model’s size and license. Choose Download / Resume if it is missing; Pause is available.

- Open Languages, enable automatic model choice, and select Hindi. Save your settings. A single language pin uses code `hi`.

- Put the cursor in an editable app field, hold Ctrl + Win, speak, then release. Review the transcript before sending it.

Language selection starts no transfer. If automatic routing is off, the model selected on Models remains in use; select a compatible model there. For more detail, see the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/).

## Use your voice in everyday Windows apps

Draft Hindi messages, notes and documents in an editable app field. Review Devanagari spelling, names and English loanwords before sending. The current language choice does not provide a separate Romanized-Hindi output or transliteration setting.

Speech recognition and text cleanup run locally. There is no account or cloud transcription fallback. With compatible models installed, you can dictate without an internet connection. Optional AI cleanup has its own model requirements; rules-only cleanup needs no text model.

## Can I dictate Hindi and English with one model?

Yes. All languages supports both. You can pin Hindi and English together, which leaves language detection enabled in that model. Short clips and code-switching can affect recognition; a single Hindi pin is useful when you know the language you will speak.

## What does language support mean here?

This page describes speech-model coverage and app configuration. It does not claim a measured accuracy score for Hindi. Accent, microphone, background noise and mixed speech affect results. The language choice does not translate the app interface or add Translate-mode output targets.

[Get Saydraft for Windows](https://tanzir71.github.io/saydraft/download/) · [See how dictation stays local](https://tanzir71.github.io/saydraft/privacy/)
