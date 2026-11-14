# Japanese Voice Typing for Windows, Offline | Saydraft

Canonical: https://tanzir71.github.io/saydraft/languages/japanese/

Dictate Japanese on Windows with local speech recognition. Saydraft is free, open-source offline voice typing through a shared multilingual model.

Free, open-source dictation

# Japanese voice typing for Windows.

日本語

Use your voice to draft Japanese messages, notes and documents on Windows. Saydraft recognizes speech locally with the shared All languages model after an explicit installation.

Choose Japanese, code ja, in Languages for direct recognition. Japanese is separate from the Chinese and Korean choices even though all three share the same multilingual model files. Pin Japanese alongside English if you use both in your workflow.

Requires the shared All languages speech model (Whisper large-v3-turbo, approximately 1,621.7 MB). Download once in setup or Models, then reuse it offline.

## How to set up Japanese dictation

- Follow the [current download and source setup instructions](https://tanzir71.github.io/saydraft/download/). Saydraft is a development preview for Windows 10 and 11.

- In Hub → Settings → Models, review the required model’s size and license. Choose Download / Resume if it is missing; Pause is available.

- Open Languages, enable automatic model choice, and select Japanese. Save your settings. A single language pin uses code `ja`.

- Put the cursor in an editable app field, hold Ctrl + Win, speak, then release. Review the transcript before sending it.

Language selection starts no transfer. If automatic routing is off, the model selected on Models remains in use; select a compatible model there. For more detail, see the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/).

## Use your voice in everyday Windows apps

Review the model’s kanji, kana, names and punctuation before sending a Japanese draft. Recognition depends on the recording and speaker. The app does not provide a separate kanji-reading or script-conversion preference. Raw mode keeps the recognized wording without prose cleanup.

Speech recognition and text cleanup run locally. There is no account or cloud transcription fallback. With compatible models installed, you can dictate without an internet connection. Optional AI cleanup has its own model requirements; rules-only cleanup needs no text model.

## Do I need a separate Japanese model or IME?

There is no separate Japanese model download. The installed All languages model produces Unicode text that Saydraft delivers into an editable field. A Japanese IME can help with manual corrections, but it does not choose the speech recognition language.

## What does language support mean here?

This page describes speech-model coverage and app configuration. It does not claim a measured accuracy score for Japanese. Accent, microphone, background noise and mixed speech affect results. The language choice does not translate the app interface or add Translate-mode output targets.

[Get Saydraft for Windows](https://tanzir71.github.io/saydraft/download/) · [See how dictation stays local](https://tanzir71.github.io/saydraft/privacy/)
