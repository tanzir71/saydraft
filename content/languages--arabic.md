# Arabic Voice Typing for Windows, Offline | Saydraft

Canonical: https://tanzir71.github.io/saydraft/languages/arabic/

Dictate Arabic offline on Windows with Saydraft. Free, open-source Arabic voice typing through a shared local multilingual speech model.

Free, open-source dictation

# Arabic voice typing for Windows.

العربية

Turn spoken Arabic into text on your Windows PC while keeping speech recognition local. Saydraft uses the installed All languages model for Arabic dictation, with no cloud transcription account.

Choose Arabic, language code ar, in Languages. Pin Arabic alone for a direct recognition hint, or pin it alongside English or another language for model language detection. The current choice does not expose a separate decoder for every Arabic dialect.

Requires the shared All languages speech model (Whisper large-v3-turbo, approximately 1,621.7 MB). Download once in setup or Models, then reuse it offline.

## How to set up Arabic dictation

- Follow the [current download and source setup instructions](https://tanzir71.github.io/saydraft/download/). Saydraft is a development preview for Windows 10 and 11.

- In Hub → Settings → Models, review the required model’s size and license. Choose Download / Resume if it is missing; Pause is available.

- Open Languages, enable automatic model choice, and select Arabic. Save your settings. A single language pin uses code `ar`.

- Put the cursor in an editable app field, hold Ctrl + Win, speak, then release. Review the transcript before sending it.

Language selection starts no transfer. If automatic routing is off, the model selected on Models remains in use; select a compatible model there. For more detail, see the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/).

## Use your voice in everyday Windows apps

Draft Arabic messages, notes and documents in an editable app that supports right-to-left text. Review spelling, names, numbers, punctuation and mixed Arabic/Latin text before sending. Dialect and recording conditions affect recognition; Raw mode keeps the recognized wording without prose cleanup.

Speech recognition and text cleanup run locally. There is no account or cloud transcription fallback. With compatible models installed, you can dictate without an internet connection. Optional AI cleanup has its own model requirements; rules-only cleanup needs no text model.

## Is Arabic dictation the same as translating into Arabic?

Arabic dictation transcribes Arabic speech using All languages. The separate experimental Pro/Labs Translate mode can produce Arabic from recognized speech using its explicitly installed local editing model. You do not need Translate mode or a separate Arabic language pack to dictate Arabic.

## What does language support mean here?

This page describes speech-model coverage and app configuration. It does not claim a measured accuracy score for Arabic. Accent, microphone, background noise and mixed speech affect results. The language choice does not translate the app interface or add Translate-mode output targets.

[Get Saydraft for Windows](https://tanzir71.github.io/saydraft/download/) · [See how dictation stays local](https://tanzir71.github.io/saydraft/privacy/)
