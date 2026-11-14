# Saydraft FAQ — Offline Dictation Questions Answered

Canonical: https://tanzir71.github.io/saydraft/docs/faq/

Answers about offline Windows dictation, local models, Spanish and Asian languages, privacy, cleanup, History and Saydraft's experimental tools.

Facts checked: 2026-11-14

## Start with a setup that fits

 

Use [Getting started](https://tanzir71.github.io/saydraft/docs/getting-started/) for the first run, then review [models](https://tanzir71.github.io/saydraft/docs/models/) and [language compatibility](https://tanzir71.github.io/saydraft/docs/languages/). Saydraft’s current app target is Windows 10 and 11, and it remains in development.

 

## Find more detail

 

For saved data, network exceptions and clipboard boundaries, read [Privacy](https://tanzir71.github.io/saydraft/privacy/). For input or delivery issues, use [Troubleshooting](https://tanzir71.github.io/saydraft/docs/troubleshooting/). The questions below summarize those guides; the linked source records contain the implementation and measured limits.

## A few useful answers.

### Is Saydraft free?

Yes. Saydraft's own code is free and open source under MIT. Models, fonts, libraries and adapted data retain their separate licenses.

### Do I need an account or subscription?

No. The app uses local models without an account. Lite, Standard and Pro describe local hardware/performance profiles, not paid plans.

### Can I dictate without internet?

Yes, with compatible models installed first. Download setup is explicit and optional update checks are off by default. Missing model files are not fetched during recognition.

### Are Spanish and Brazilian Portuguese included?

Both are covered by Parakeet v3 and the shared All languages model. Portuguese uses pt, including Brazil; this is coverage rather than a claim of verified accuracy for every accent.

### What about Arabic, Bengali, Chinese, Japanese, Korean and Thai?

They use the optional shared All languages model. Filipino/Tagalog, Hindi, Indonesian, Malay, Persian, Tamil, Telugu, Urdu and Vietnamese also use that shared route. There are no per-language packs.

### Will it get every word right?

No. Accuracy varies by language, model, accent and recording conditions. The public baseline exposes substantial Bengali, Tamil and Telugu errors. Review names, numbers and technical terms before using a draft.

### Do I need an AI cleanup model?

No. Deterministic cleanup rules work without a text model. Optional local AI needs its own model/runtime and can retain the rules result when unready, out of budget or rejected.

### Is Whisper mode a different speech model?

No. The experimental Microphone setting boosts quiet speech with gain, AGC and optional local enhancement. It works before the selected recognizer; its whispered-speech accuracy target remains unmeasured.

### Are recordings kept?

Audio retention is off by default. History stores recognized and processed text locally; choosing to retain audio is separate. Practice in setup stays in memory and creates no History entry.

### Does the website listen to me?

No. Its examples are canned visual simulations with no microphone access, tracking analytics or third-party font requests.

## Sources and further reading

- [Current feature and release status ↗](https://github.com/tanzir71/saydraft/blob/main/readme.md)

- [Speech language coverage and accuracy limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/LANGUAGES.md)

- [Privacy and explicit network actions ↗](https://github.com/tanzir71/saydraft/blob/main/docs/PRIVACY.md)
