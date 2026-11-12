# Caret-aware final formatting

Final formatting runs after accepted cleanup, literal restoration and snippet
expansion, before raw/cleaned History persistence and insertion. Messaging's
existing single-sentence period rule runs first. The pipeline's standalone entry
point uses the same formatter; the transcript processor defers it until snippets
have been restored, so boundary spaces are added once.

Layout requires verified replacement boundaries from the focused field. A known
empty prefix means the beginning of the field; an unavailable prefix does not.
An unknown selection or a truncated selection disables layout. An independently
unknown prefix/suffix disables edits on that side. Raw and Code bypass layout.
The formatter never changes the surrounding field or moves its selection.

| Existing field before / after selection | Dictated text | Inserted text |
| --- | --- | --- |
| `Please` / empty | `send the file` | ` send the file` |
| `Done. ` / empty | `next item` | `Next item` |
| `the ` / `fox` | `quick` | `quick ` |
| `pre` / `e`, selecting `fix` | `new` | `new` |
| `Tasks` / empty, Notes profile | `bullet point ready` | newline + `- Ready` |
| `أنا` / empty | `بخير` | ` بخير` |

The initial word is capitalized at a known sentence/line start. Inline prose
recovers a lowercase initial from the source when cleanup introduced its capital;
otherwise only a finite set of common function words/starters is lowercased.
Ambiguous names, acronyms, `I`, mixed-case brands, title-case name pairs, glossary
terms, quotes, URLs, emails, code literals and snippet payloads retain their
case. An explicit spoken `cap` command wins. Turkish/Azeri `i` uses `İ` at a
sentence start; casing never expands one character into several.

Boundary spaces avoid duplicating existing whitespace and respect punctuation,
opening brackets/quotes, currency, decimals, paths, hashtags, word fragments and
Unicode combining/joiner characters. Bengali and Arabic use word gaps; Han,
Japanese, Thai, Lao, Myanmar and Khmer boundaries do not gain English-style gaps.
This is conservative Unicode/script handling, not language segmentation. A list
starts on a new line when preceding text is on the same line.

Snippet casing is literal, while the established messaging punctuation policy
still applies: a `Thanks.` snippet in Messages becomes `Thanks`, and a
multi-sentence snippet retains its final period. No surrounding field text or
selection enters History. Casing recovery retains only one source character in
ephemeral context.

The authored golden corpus includes 40 caret cases (472 total). CI requires 100%
exact output, plus 100/100 adversarial refusals. Availability flags, selection,
truncation and the one-character suffix are explicit validated corpus fields;
unknown keys, malformed flags and broken surrogate suffixes are rejected.
Additional focused tests cover protected text, ambiguous casing, explicit case
commands, partial availability and forwarding through the actual processor.

The own-control native test checks an empty selection at the beginning of its
fixed plain field: `Public dictation fixture `, including its required suffix
space, is saved exactly before memory delivery. Password refusal remains intact.
It uses invisible owned controls, authored transcript/recorder stubs and memory
delivery; it supplies no active-field, microphone, ASR or OS-paste acceptance.
Desktop testing remains stopped at the owner's request.

Validation: ordinary GC-enabled full suite 1861 pass, five explicit native/model
skips; golden 472/472; adversarial 100/100; Ruff/diff pass. The final local log is
`build/qa/caret-formatting-optimized-full.stdout.log`. Earlier full-run Qt
processEvents access violations, UI-only passes and a GC-disabled diagnostic are
retained separately. The exact Qt lifetime cause remains unproven; production GC
is unchanged and this change claims no Qt crash fix. P6 should review widget/test
lifetimes. Historical native cleanup reports remain unchanged and cannot earn
current 472-case model acceptance.
