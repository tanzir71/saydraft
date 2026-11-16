# Offline Dictation for Windows: A Practical Guide | Saydraft

Canonical: https://tanzir71.github.io/saydraft/offline-dictation-windows/

Learn how offline dictation works on Windows: speech models, hardware, languages, local cleanup and privacy. A practical free, open-source setup guide.

Facts checked: 2026-11-14

Offline dictation turns microphone audio into text with a model stored on your computer. An optional second model can tidy the wording. Recognition and optional cleanup run on your PC and need memory, processor time, storage and careful review.

 

Saydraft is a free, open-source Windows project built around this workflow. An unsigned portable preview is available from the [download page](https://tanzir71.github.io/saydraft/download/), with source setup also available. Broader accuracy and native Windows acceptance remain in progress.

 

## What runs on your PC

 

Speech recognition produces the transcript. Deterministic rules can format it; optional local AI cleanup can make further edits when its quality and time guards allow. These are separate stages. Improving prose after recognition does not establish that the original names, numbers or words were heard correctly.

 

Raw and Code modes reduce prose processing. Keep them available for material where literal wording matters.

 

## Choose a compatible language model

 

The default Parakeet v3 choice covers 25 European languages. The optional shared All languages model is Whisper large-v3-turbo and covers the other supported Whisper language choices. Thai, Chinese, Korean, Japanese, Hindi, Urdu, Bengali and Arabic use that shared multilingual route.

 

With automatic model choice enabled, pin one to three languages. A single Whisper pin supplies its decoder language; multiple pins leave model language detection enabled. Parakeet does not accept that explicit decoder hint. Review the [language and model guide](https://tanzir71.github.io/saydraft/languages/); coverage does not guarantee accuracy for every accent, dialect or mixed-language passage.

 

## Plan for storage and hardware

 

The default speech bundle is approximately 773.4 MB including its language detector. All languages is approximately 1,621.7 MB. Optional editing models add their own downloads and memory needs. Setup shows the files, sizes and licenses before you explicitly choose Download / Resume.

 

Use the application’s model performance check to measure an installed model with bundled audio. It makes a provisional capability recommendation rather than a guarantee of everyday speed. Larger models and longer passages can add delay; broad release-latency qualification remains in progress.

 

## Check privacy as a workflow

 

Installed speech and cleanup run locally. Model downloads and optional update checks are separate network actions. History is local, audio retention is off by default, and your PC still controls who can access saved data.

 

Finish setup, disconnect your network and try a plain text editor. Read the [privacy page](https://tanzir71.github.io/saydraft/privacy/) and the linked verification guide for details of the network guard and optional Windows Firewall controls. The website itself has no microphone access or tracking analytics.

 

## Test the words you actually use

 

Try quiet speech, proper names, numbers and a longer paragraph. Review all results before sending them elsewhere. The public 20-language baseline exposes substantial Bengali, Tamil and Telugu errors, and broad owner accuracy remains deferred. Experimental decoder candidates are kept out when they regress.

 

Start with the [setup guide](https://tanzir71.github.io/saydraft/docs/getting-started/). For editor and terminal workflows, continue with [dictation for developers](https://tanzir71.github.io/saydraft/dictation-for-developers/).

## A few useful answers.

### Does offline dictation need internet during use?

Installed local models can recognize speech without internet. Saydraft's setup downloads are explicit, and optional GitHub update checks are off by default. Finish model setup before disconnecting.

### Does every language need its own download?

No. The shared multilingual speech model covers many language choices. Selecting or pinning a language does not start a download.

### Will a larger model always be more accurate?

No. Recognition varies by language, recording conditions and model. Compare measured results and your own representative speech; larger downloads alone do not establish better accuracy or speed.

## Sources and further reading

- [Saydraft models and measurement scope ↗](https://github.com/tanzir71/saydraft/blob/main/docs/MODELS.md)

- [Multilingual accuracy findings ↗](https://github.com/tanzir71/saydraft/blob/main/docs/ASR_ACCURACY.md)

- [Offline verification and its limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/VERIFY_OFFLINE.md)
