# Brazilian Portuguese Voice Typing for Windows | Saydraft

Canonical: https://tanzir71.github.io/saydraft/languages/brazilian-portuguese/

Offline Brazilian Portuguese voice typing on Windows. Saydraft is free and open source, with local Portuguese speech recognition and no account.

Free, open-source dictation

# Brazilian Portuguese voice typing for Windows.

Português do Brasil

Write in Portuguese with your voice, including Portuguese spoken in Brazil. Saydraft provides local speech recognition for Windows without an account or cloud transcription.

In Languages, choose Portuguese (including Brazilian Portuguese). The speech engines use the shared Portuguese code pt. There is no Brazil-only model or pt-BR decoder setting. Do not choose br for Brazil: in Whisper, br is the code for Breton.

Portuguese, including Brazil, is included in Parakeet v3, the default speech model. All languages is also compatible. No separate language pack is required.

## How to set up Brazilian Portuguese dictation

- Follow the [current download and source setup instructions](https://tanzir71.github.io/saydraft/download/). Saydraft is a development preview for Windows 10 and 11.

- In Hub → Settings → Models, review the required model’s size and license. Choose Download / Resume if it is missing; Pause is available.

- Open Languages, enable automatic model choice, and select Portuguese (including Brazilian Portuguese). Save your settings. A single language pin uses code `pt`.

- Put the cursor in an editable app field, hold Ctrl + Win, speak, then release. Review the transcript before sending it.

Language selection starts no transfer. If automatic routing is off, the model selected on Models remains in use; select a compatible model there. For more detail, see the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/).

## Use your voice in everyday Windows apps

Portuguese is included in the default Parakeet v3 model’s language set. You can also use Portuguese with All languages. If you pin Portuguese alongside Thai, Chinese or Korean, automatic routing uses that shared multilingual model for the combination.

Speech recognition and text cleanup run locally. There is no account or cloud transcription fallback. With compatible models installed, you can dictate without an internet connection. Optional AI cleanup has its own model requirements; rules-only cleanup needs no text model.

## Is there a separate Brazilian Portuguese language pack?

No. Choose Portuguese in Languages and use an installed compatible speech model. Both the default model and All languages cover Portuguese. NVIDIA notes that Parakeet’s training uses European Portuguese, so a separate Brazilian reference evaluation is needed before recommending it over Whisper for Brazil. Saydraft does not claim a separate Brazilian-accent accuracy score or convert European Portuguese wording into Brazilian Portuguese.

## What does language support mean here?

This page describes speech-model coverage and app configuration. It does not claim a measured accuracy score for Brazilian Portuguese. Accent, microphone, background noise and mixed speech affect results. The language choice does not translate the app interface or add Translate-mode output targets.

[Get Saydraft for Windows](https://tanzir71.github.io/saydraft/download/) · [See how dictation stays local](https://tanzir71.github.io/saydraft/privacy/)
