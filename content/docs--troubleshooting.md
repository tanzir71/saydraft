# Saydraft Troubleshooting — Input, Models and Delivery

Canonical: https://tanzir71.github.io/saydraft/docs/troubleshooting/

Troubleshoot Saydraft microphone input, interrupted model downloads, wrong language, slow cleanup, shortcut conflicts and text delivery on Windows.

Facts checked: 2026-11-14

## The microphone meter does not respond

 

Open Microphone in setup or Settings. Check the selected device, use Refresh inputs if it changed, and run the level-only Test input. Check microphone privacy reads Windows permission state without recording; follow its Windows settings link if desktop-app microphone access is blocked or unknown.

 

Start with a short practice sentence. Source setup and physical Windows behavior remain in development. The [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/) describes practice and its stop/recovery choices.

 

## A download stopped or files are not ready

 

Use the same model’s Download / Resume action. Setup checks pinned files before marking the package ready; partial transfers can resume, and complete verified files are reused. Check available disk space and the network message.

 

If you enabled a packaged Firewall block, review [its download restriction](https://tanzir71.github.io/saydraft/docs/privacy/verify-offline/) and explicitly remove Saydraft’s own rule before resuming. Keep unrelated and organizational rules intact. Recognition and language selection do not fetch missing weights in the background.

 

## The words or language are wrong

 

Compare raw and cleaned text in History: raw text shows recognized words; cleaned text shows what formatting or cleanup changed. Check the recording conditions, selected speech model and [language pins](https://tanzir71.github.io/saydraft/docs/languages/).

 

Use a compatible model for your language. The shared All languages route is needed for Arabic, Bengali, Chinese, Japanese, Korean, Thai and other supported languages outside Parakeet’s set. Dictionaries can help within their supported scope, but neither a larger model nor cleanup guarantees correct recognition. Review [names and replacements](https://tanzir71.github.io/saydraft/docs/dictionary/).

 

## Recognition or cleanup feels slow

 

Check model performance with the installed model and bundled audio. A provisional PC recommendation is separate from a timed model check. First preparation, hardware, recording length and model size affect delay; broader release-latency qualification remains open.

 

Rules-only cleanup works without a text model. Optional AI that is unavailable, unprepared, out of budget or rejected by preservation checks can keep the rules result. Review [styles and cleanup](https://tanzir71.github.io/saydraft/docs/styles/) before treating that fallback as a failure.

 

## The shortcut or paste did not work

 

Review [shortcut bindings and conflicts](https://tanzir71.github.io/saydraft/docs/shortcuts/). Start in an ordinary, non-elevated editable text field. Password, protected, changed and some elevated targets can prevent delivery. A saved result remains in History; use its explicit recovery actions rather than forcing a changed field.

 

A recognition retry requires the row’s retained audio. Without it, recover the saved text or make a new recording. Experimental Command results have their own Copy path and do not use ordinary dictation paste-last.

 

## Report a reproducible problem

 

Include your source/version, Windows version, selected model, language choice, and the smallest steps that reproduce the issue in [GitHub Issues](https://github.com/tanzir71/saydraft/issues). Use redacted logs and examples. Keep private recordings, transcripts, passwords and document text out of public reports.

## A few useful answers.

### The model is missing. Should I keep recording?

Finish the explicit model setup and verification first. Recognition never downloads missing weights automatically, and a changed or incomplete installation can refuse preparation.

### Can I retry recognition from a History row?

A History recognition retry needs retained audio. Audio retention is off by default. Without the row's audio, recover its saved text or make a new recording.

## Sources and further reading

- [Current troubleshooting and supported source launch ↗](https://github.com/tanzir71/saydraft/blob/main/readme.md)

- [Microphone and permission behavior ↗](https://github.com/tanzir71/saydraft/blob/main/docs/MICROPHONE.md)

- [Delivery, protected fields and recovery ↗](https://github.com/tanzir71/saydraft/blob/main/docs/DELIVERY.md)
