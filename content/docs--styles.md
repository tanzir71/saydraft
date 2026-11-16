# Saydraft Styles — Tone and Local Dictation Cleanup

Canonical: https://tanzir71.github.io/saydraft/docs/styles/

Choose Formal, Casual or Very casual tone per app, adjust cleanup intensity, preview dictionary edits and understand rules versus optional local AI.

Facts checked: 2026-11-14

## Choose tone for the place you write

 

Hub → Style has seven app groups, three tones and four cleanup levels. Choose Formal, Casual or Very casual for a group, then save your staged changes. Per-app profiles can override the group’s choices. Code keeps its literal-oriented path instead of applying prose tone.

 

A recording keeps the style captured when it starts. Changing preferences while it runs does not change that recording’s style.

 

## Choose how much to tidy

 

| Level | What it does |
| --- | --- |
| 1 · Verbatim-ish | Preserve words, repetitions and spoken numbers; normalize spacing |
| 2 · Light | Remove hesitation fillers, normalize casing/numbers and allow supported list layout |
| 3 · Balanced | Also remove accidental repetition |
| 4 · Polished | Also handle stronger filler removal, explicit self-corrections and spoken punctuation |

 

Level one skips the prose model. At the other levels, optional AI remains subject to its preparation, time budget and preservation checks. Raw and Code have their own bypasses. A style choice does not make an unavailable AI model load or download.

 

## Preview before saving

 

Type a sample in the Style preview. The rules preview uses the same transcript processor as normal dictation, including staged Dictionary terms, replacements and supported snippets. Pending forms are previewed without saving them or creating persistent History. Invalid drafts show their error rather than an old result. The preview accepts up to 4,096 characters without silently truncating.

 

Preview language is independent of speech-model selection. Choose a language to simulate resolved recognition; use [Languages](https://tanzir71.github.io/saydraft/docs/languages/) for the real speech pins and model requirements.

 

## Rules and optional local AI

 

Rules work without a text model. Preview with current AI uses an already installed, prepared cleaner and its normal budget. Busy, warming, unavailable or rejected AI keeps a labelled rules result. Apply model-setting changes before trying the current-AI preview.

 

Cleanup can still be imperfect. It does not establish that the recognizer heard every name, number or word correctly. Compare raw and cleaned text in History, and keep [names and specialist terms](https://tanzir71.github.io/saydraft/docs/dictionary/) in your dictionary where useful.

 

## Translation is an independent choice

 

Translate while speaking is a separate Pro/Labs feature with an explicitly installed editing model and an output target per supported non-code app group. Current targets are English, Spanish and Arabic, or Keep recognized language. The text-cleanup preview does not run spoken translation. Raw and Code bypass it.

## A few useful answers.

### Does changing preview language change speech recognition?

No. Preview language simulates the recognizer's resolved language for text cleanup. It does not change speech-language pins, download a model or translate the sample.

### Does a rejected AI edit lose my transcript?

The cleanup path retains its rules result when the model is unavailable, out of budget or rejected by preservation checks. Review the raw and cleaned words in History.

## Sources and further reading

- [Shared styles engine and Hub preview ↗](https://github.com/tanzir71/saydraft/blob/main/docs/STYLES.md)

- [Cleanup preservation checks ↗](https://github.com/tanzir71/saydraft/blob/main/docs/VALIDATOR_V2.md)
