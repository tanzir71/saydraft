# Cleanup validator v2

`saydraft/cleanup/llm/validate.py` now checks every complete cleanup candidate
before the pipeline restores protected text, saves History and inserts. Rejection
keeps the rules output and records `rejected:<reason>`. The old
`dictation.validation` imports remain compatible through explicit exports. The
validator never repairs a candidate or loads another model.

The checks preserve exact protected-token counts and order; code/quotes; URLs
and email addresses; signed digits and numeric sequences; currency/percentages;
dates and AM/PM/time zones; glossary occurrences; negation and profanity. Small
lexicons additionally guard spelled-out numbers, weekdays, relative dates and
currency words. They include English, Bengali and Arabic examples. Unicode word
scanning retains combining marks, and shared word-boundary checks prevent a
glossary term from matching just the base letters of a longer Bengali word.

For post-rules cleanup at intensities 1–3, the pipeline also checks content-word
identity and order. This closes a real native-model gap: `Envoyez` → `Envélez`
previously passed the overlap checks. Unknown substitutions, content deletion,
and reordered roles now fall back with `rejected:post_rules_words_changed`.
Bounded English agreement, articles/politeness and unambiguous conversational
expansions remain eligible; tense changes do not count as agreement. Unicode
combining marks remain part of words. Intensity 4 retains its broader rewording
contract, and explicit translation retains its separate similarity exemption;
all existing number/entity/negation/profanity guards still apply. This additional
check is conservative and does not establish semantic equivalence.

New controls or output wrappers are refused. Assistant/answer prefixes must
already be present in the source to be eligible. Dominant-script checks and
Unicode token overlap refuse translation and answering; content-word overlap
prevents common function words from hiding an invented answer. Similarity and
length checks remain conservative. Intensity controls the allowed length ratio:

| Intensity | Minimum | Maximum |
|---|---:|---:|
| 1 | 0.80 | 1.15 |
| 2 | 0.70 | 1.20 |
| 3 (current balanced mode) | 0.60 | 1.30 |
| 4 (current aggressive mode) | 0.50 | 1.30 |

Identical text takes a fast path. Candidates/sources above 64,000 characters
decline validation before similarity work. The future explicit Translate caller
can relax script/token similarity; the normal dictation path never does so.
Strict detail/lexical checks still apply to that optional validator argument.

The upstream protection helpers also needed correction. They now assign a
collision-free token per glossary occurrence, preserve each occurrence's original
casing, avoid larger-word matches and restore in one pass. Span protection covers
code, quotes, URLs, emails and literal token-looking text without colliding with
existing/generated tokens. URL sentence punctuation stays outside the mask so
email formatting does not append a second final period.

`tests/cleanup_adversarial.jsonl` contains 100 authored candidate refusals in ten
categories: numbers, protected tokens, entities, code, assistant output, language,
length, profanity, dates/amounts/times and negation. All 100 are refused; the prior
committed validator (`2b264a4`) refused 47 of the same examples. The evaluator
reports category/reason counts and missed IDs without printing transcript text.
CI requires a 100% catch rate and at least 100 cases; empty corpora and duplicate
IDs cannot inflate acceptance. Per-rule unit tests and conservative positive
examples complement this refusal set, including English/Bengali/Arabic,
dictated questions/requests, meaningful “actually” and profanity preservation.

This is acceptance on the checked-in examples, not proof of semantic equivalence
or resistance to every unseen model output. Script detection is a deterministic
heuristic, not full language identification. The detail/profanity lexicons are
finite; unknown forms and near-identical semantic changes need more cases and
model evaluation. Strict checks may decline harmless grammar/style changes,
which intentionally leaves the available rules output. No app model is promoted
from these results. The golden set now has 556 cases; fresh native hybrid quality,
model selection and tier/latency acceptance remain under P4.7/P4.4/P4.6.

Original validator checkpoint: 769 tests pass with four optional native skips and real
preview/Silero/LID fixtures enabled; rules evaluation 42/42; adversarial 100/100;
Ruff and diff checks pass. A synthetic repeated 1700-word punctuation edit takes
25.6 ms median / 32.8 ms maximum in thirty runs concurrent with the suite. This
bounded observation is not a hardware-tier or general latency claim.
