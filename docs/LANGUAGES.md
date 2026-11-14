# Speech recognition languages

Saydraft offers Thai, Mandarin Chinese, Korean, Japanese, Hindi, Urdu, Indonesian,
Malay, Spanish and Portuguese (including Brazilian Portuguese). The owner also
approved highlighting Vietnamese, Filipino / Tagalog, Tamil, Telugu, Persian,
French and German. These join Bengali, Arabic and the other languages in
the installed speech model. These are dictation choices, separate from app UI
localization and the experimental [Translate output targets](TRANSLATE.md).

## Choose a compatible model

| Language | Choice in Languages | Decoder code | Automatic route |
|---|---|---|---|
| Thai | Thai | `th` | All languages |
| Chinese, Mandarin | Chinese (Mandarin) | `zh` | All languages |
| Korean | Korean | `ko` | All languages |
| Portuguese, including Brazil | Portuguese (including Brazilian Portuguese) | `pt` | Parakeet v3 |
| Bengali | Bengali | `bn` | All languages |
| Arabic | Arabic | `ar` | All languages |
| Japanese | Japanese | `ja` | All languages |
| Hindi | Hindi | `hi` | All languages |
| Urdu | Urdu | `ur` | All languages |
| Indonesian | Indonesian | `id` | All languages |
| Malay | Malay | `ms` | All languages |
| Spanish | Spanish | `es` | Parakeet v3 |
| Vietnamese | Vietnamese | `vi` | All languages |
| Filipino / Tagalog | Filipino / Tagalog | `tl` | All languages |
| Tamil | Tamil | `ta` | All languages |
| Telugu | Telugu | `te` | All languages |
| Persian / Farsi | Persian (Farsi) | `fa` | All languages |
| French | French | `fr` | Parakeet v3 |
| German | German | `de` | Parakeet v3 |

The **All languages** package is the shared Whisper large-v3-turbo model,
approximately 1,621.7 MB. Install it once for Thai, Chinese, Korean, Bengali,
Arabic and other supported languages, including Japanese, Hindi, Vietnamese
and Indonesian. It also covers Urdu, Malay, Filipino / Tagalog, Tamil, Telugu
and Persian. Selecting another language reuses the model's weights;
there are no separate language packs or download buttons.

Portuguese belongs to Parakeet v3's 25-language set and is also supported by
Whisper. Both engines use `pt`; neither exposes a Brazil-only `pt-BR` decoder
setting. The app's Portuguese label explicitly includes Brazil. **`br` is Breton,
not Brazilian Portuguese.** This does not promise accent-specific accuracy or
conversion between European and Brazilian Portuguese vocabulary.
NVIDIA specifically notes European Portuguese training in its model card.
Brazilian reference clips must therefore compare Parakeet and Whisper before
claiming a preferred model for Brazil; the current route is coverage-based.

Chinese (Mandarin) uses `zh`. Chinese (Cantonese), `yue`, is a separate menu choice
using the same multilingual weights. The app does not currently expose a
Simplified/Traditional conversion preference or guarantee every Chinese dialect.

## Setup and use

1. Open Hub → Settings → Models. Review the model's size and license, then choose
   **Download / Resume** if it is missing. Pause is available.
2. In **Languages**, enable **Choose the speech model automatically**, then pin
   one to three languages. Save the settings.
3. With compatible files installed, dictate into an editable Windows app using
   your configured shortcut. Installed files are reused offline.

A single Whisper pin passes its exact decoder code. Multiple pins select a
compatible model and leave its language detection enabled. For example, Thai +
Korean + Portuguese selects All languages; Portuguese alone selects Parakeet v3.
Per-app model overrides take priority. See [routing](ASR_ROUTING.md) for retry,
language detection and cache limits.

Selecting a language never starts a download. Existing profiles can retain manual
model selection; pins do not override it until automatic model choice is enabled.
For direct Thai/Chinese/Korean/Bengali/Arabic recognition, choose All languages
manually or pin the language with automatic routing. Auto's default Parakeet
recognition is not a substitute for installing the multilingual model.

Use Raw mode when you want to retain recognized wording without prose cleanup.
Review names, punctuation, spacing and mixed-language output before sending.

## Evidence and limits

The owner requested stronger accuracy checks across the language set. The
follow-up evaluation uses licensed public reference speech in addition to the
existing bundled smokes, without requiring owner recordings or changing the
deferred owner-acceptance decision. Every language needs its own result and
sample count; a global average cannot certify a weak or unmeasured language.
See [accuracy evaluation scope](ASR_ACCURACY.md).

The cleanup audit found English word rules were applied across languages:
Portuguese **um** could be deleted as an English filler, and meaningful repeated
words could be collapsed. The drafted correction disables English lexical,
number, command, casing and punctuation heuristics for known non-English
language contexts. Ordinary AI cleanup must preserve the native word sequence;
English article/agreement exceptions do not apply there, including Polished.
The foreign-language word check preserves NFC spelling and case, allowing native
punctuation boundaries while retaining spaced loanword boundaries and avoiding lossy
case folding such as German `Maße` versus `Masse`.
Unicode word and combining-mark checks preserve recognized wording rather than
claiming to prove semantic equivalence. Boundary spacing remains available.
Legacy text-only `auto` contexts retain their previous English rule policy.
Production resolves missing language evidence to `und` and mixed background
segments to `mul`, while preserving explicit language hints. Multiple Parakeet
pins can identify cleanup language using the installed detector. Native accuracy
of that evidence still needs evaluation. These
changes pass the controlled language/worker/practice checks. The final focused
suite passes 513 tests; subsequent validator/translation follow-ups also pass,
with rules 556/556 and adversarial 100/100 unchanged. Clean-commit CI remains
pending before checklist acceptance.

The pinned [faster-whisper 1.2.1 language vocabulary](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/tokenizer.py)
contains `th`, `zh`, `ko` and `pt`. NVIDIA's [Parakeet v3 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
includes Portuguese in its supported language set. Saydraft's pinned catalog and
`saydraft/asr/languages.py` record those model choices.

This establishes model coverage, not a measured accuracy result for each
language, region or accent. Owner accuracy acceptance remains deferred; the
bundled English/Bengali/Arabic fixtures remain the earlier native speech-smoke
scope. The new public evaluation corpus now has 400 verified clips across twenty
languages; expanded native scoring remains pending. Routing and offscreen UI checks can verify language selection, decoder
hints, persistence and shared model reuse without claiming new speech accuracy.

The [language overview](https://tanzir71.github.io/saydraft/languages/) and seventeen
language-specific pages expose this setup guidance as static, crawlable HTML.
They have unique titles, descriptions and canonical URLs, internal links and
sitemap entries. They are English guides, so no translated-page `hreflang`
alternates or app-menu locale claims are added. Search indexing and rankings
depend on the search engine; no ranking guarantee is made.

Offscreen Qt renders pass 37 states at each of 1x and 2x. Seventeen native-script
samples have zero missing glyphs after the probe registers the existing public
Windows fallback fonts. Qt’s offscreen platform initially exposes zero system
font families; this probe correction installs and redistributes no fonts. The
app retains its bundled fonts and normal Windows font fallback.
