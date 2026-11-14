# Saydraft Languages — Offline Speech Models and Pins

Canonical: https://tanzir71.github.io/saydraft/docs/languages/

Choose Saydraft speech languages for Arabic, Bengali, Chinese, Hindi, Japanese, Korean, Thai, Spanish, Brazilian Portuguese and more, with shared models.

Facts checked: 2026-11-14

## Choose a model that covers your language

 

Parakeet v3 covers 25 European languages. The optional shared All languages package uses Whisper turbo for additional supported speech languages. These choices describe recognition coverage, not translated app UI or a guarantee for every accent, dialect or mixed-language passage.

 

The nineteen linked language guides are listed alphabetically by English display name. Settings includes the model’s other available language choices as well.

 

| Language guide | Code | Compatible setup |
| --- | --- | --- |
| [Arabic](https://tanzir71.github.io/saydraft/languages/arabic/) | `ar` | All languages |
| [Bengali](https://tanzir71.github.io/saydraft/languages/bengali/) | `bn` | All languages |
| [Brazilian Portuguese](https://tanzir71.github.io/saydraft/languages/brazilian-portuguese/) | `pt` | Parakeet v3 or All languages |
| [Chinese (Mandarin)](https://tanzir71.github.io/saydraft/languages/chinese/) | `zh` | All languages |
| [Filipino / Tagalog](https://tanzir71.github.io/saydraft/languages/filipino-tagalog/) | `tl` | All languages |
| [French](https://tanzir71.github.io/saydraft/languages/french/) | `fr` | Parakeet v3 or All languages |
| [German](https://tanzir71.github.io/saydraft/languages/german/) | `de` | Parakeet v3 or All languages |
| [Hindi](https://tanzir71.github.io/saydraft/languages/hindi/) | `hi` | All languages |
| [Indonesian](https://tanzir71.github.io/saydraft/languages/indonesian/) | `id` | All languages |
| [Japanese](https://tanzir71.github.io/saydraft/languages/japanese/) | `ja` | All languages |
| [Korean](https://tanzir71.github.io/saydraft/languages/korean/) | `ko` | All languages |
| [Malay](https://tanzir71.github.io/saydraft/languages/malay/) | `ms` | All languages |
| [Persian (Farsi)](https://tanzir71.github.io/saydraft/languages/persian/) | `fa` | All languages |
| [Spanish](https://tanzir71.github.io/saydraft/languages/spanish/) | `es` | Parakeet v3 or All languages |
| [Tamil](https://tanzir71.github.io/saydraft/languages/tamil/) | `ta` | All languages |
| [Telugu](https://tanzir71.github.io/saydraft/languages/telugu/) | `te` | All languages |
| [Thai](https://tanzir71.github.io/saydraft/languages/thai/) | `th` | All languages |
| [Urdu](https://tanzir71.github.io/saydraft/languages/urdu/) | `ur` | All languages |
| [Vietnamese](https://tanzir71.github.io/saydraft/languages/vietnamese/) | `vi` | All languages |

 

## Auto or one to three pins

 

In Settings → Languages, use Auto or pin up to three languages. Enable automatic model choice to route those pins to a compatible installed model, or explicitly select a compatible model yourself. The controls do not start a download.

 

A single Whisper pin supplies its decoder language; multiple pins leave language detection enabled. Parakeet does not accept that same explicit decoder hint. Automatic model routing and language detection can be imperfect, especially for short, quiet or mixed-language speech. Review your results and language choice.

 

## One shared multilingual download

 

Arabic, Bengali, Chinese, Filipino / Tagalog, Hindi, Indonesian, Japanese, Korean, Malay, Persian, Tamil, Telugu, Thai, Urdu and Vietnamese use the shared All languages route. French, German, Portuguese and Spanish are also in Parakeet v3’s coverage. Installing another language choice reuses the model’s weights; there are no per-language download buttons.

 

See [model sizes and explicit setup](https://tanzir71.github.io/saydraft/docs/models/).

 

## Portuguese and Chinese details

 

Portuguese uses pt, including Brazil. The current automatic route is based on coverage, not a verified preference for every Brazilian accent. NVIDIA notes European Portuguese training in its original model card. Compare representative speech before choosing a model for your workflow.

 

Mandarin Chinese uses zh. Cantonese, yue, is a separate menu choice using the multilingual weights. The app does not expose a Simplified/Traditional conversion setting or establish coverage of every Chinese dialect.

 

## Coverage and measured accuracy

 

The public 20-language evaluation reveals substantial errors in Bengali, Tamil and Telugu. Larger decoder candidates have not established a general improvement. Broad owner accuracy remains deferred. Review names, numbers and technical terms before sending a draft; text cleanup does not prove that recognition was correct.

 

Dictation language, the Style preview language and experimental Translate output targets are separate choices. Current spoken Translate targets are English, Spanish and Arabic. See [styles and translation](https://tanzir71.github.io/saydraft/docs/styles/).

## A few useful answers.

### Does each language need a separate pack?

No. Multiple language choices reuse the same installed model. The optional All languages package is shared; choosing or pinning another language never starts a download.

### Is Brazilian Portuguese a separate model or decoder?

No. Portuguese uses pt in Parakeet and Whisper, including Brazilian Portuguese. There is no Brazil-only pt-BR decoder here; br means Breton. Accent-specific accuracy still needs evaluation.

## Sources and further reading

- [App language codes, routing and limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/LANGUAGES.md)

- [Measured multilingual accuracy scope ↗](https://github.com/tanzir71/saydraft/blob/main/docs/ASR_ACCURACY.md)
