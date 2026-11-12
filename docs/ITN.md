# Inverse text normalization

`cleanup/itn.py` supplies deterministic English spoken-detail formatting without
loading a model. It parses complete cardinals/ordinals (including lakh/crore and
scales through trillion), signed values, decimals, AM/PM times, named-month
dates, currencies, percentages, digit-sequence phone fields, emails, URLs and
versions. Examples include `three thirty pm` → `3:30 PM`, `two dollars and fifty
cents` → `$2.50`, `john at example dot com` → `john@example.com`, and
`v two point one` → `v2.1`.

The whole-phrase parser declines malformed adjacent values rather than summing
them. It keeps conjunctions outside valid numeric phrases, existing typed digits
and leading zeros, and quoted/code/protected text. At intensities 1–2, small
numbers stay words in prose; intensity 3–4 or compact notes uses digits. Unit and
fraction uses such as “a second” and “a hundredth” stay literal. Month/verb and
pounds/weight guards avoid several common ambiguous readings. No missing year,
AM/PM, country code, currency or rounding is inferred.

Literal address protection is shared in `text_entities.py`, including bare
domains/dotted technical names, Unicode email shapes and local hosts. This is
preservation, not delivery/SMTP validation. Spoken address conversion requires a
recognized suffix. `normalize_addresses` provides an address-only pass so an
app can protect labels such as `um` before filler cleanup. Generated values are
restored once from collision-free internal placeholders.

The parser has 107 focused cases covering supported forms, refusal/literal
examples, Unicode preservation, low-intensity prose and malformed long tokens.
A long-token probe exposed quadratic restart matching in the original address
patterns: 10,000 dotted characters took 1.416 s. Boundary-aware patterns reduce
that to 0.028 s; 50,000 dotted/hyphenated characters take 0.147/0.121 s in this
development probe. A generous two-second regression check covers the long dotted
case. These observations are not hardware-tier or general release-latency claims.

This is a finite deterministic grammar. Unsupported or ambiguous forms can stay
literal; it does not claim spoken-detail normalization for Bengali/Arabic or all
languages. Existing Unicode text remains unchanged. Full pipeline integration,
ordering and golden coverage are described below. P4.5 remains unchecked while
opt-in Enter remains. Code, messaging and backtrack details are in their separate
feature documents.

The isolated parser-foundation snapshot passed 916 tests with four optional native skips
and real preview/Silero/LID fixtures enabled; rules 90/90; adversarial 100/100;
Ruff and diff checks pass. The review worktree is retained in QA.

## App integration and ordering

The running rules pipeline now normalizes spoken addresses before filler removal
and protects the resulting fields. Thus `um at example dot com` remains an
address instead of losing its local label. List detection separates ordinal,
explicit-number and cardinal marker families before ordinary number conversion,
so item counts do not become extra list markers. Explicit single-item bullets
and numbered commands work; literal “there is a bullet point…” stays prose.

ITN runs before repetition cleanup, preserving every repeated/leading-zero phone
digit. Generated addresses, versions and quoted details are protected through
commands, backtracks and punctuation. Restoration unwinds quote and entity layers
in order. Backtracks retain unaffected original slices and protected/Unicode
tokens instead of reconstructing text from ASCII words. “I actually agree”,
several pronoun/adverb contexts and quoted content remain meaningful; “never
mind” with a replacement is recognized. Broader clause/phrase alignment and
pause-marked natural restatements are now in `docs/BACKTRACKS.md`.

Default prose intensities match the existing prompt/validator policy: balanced 3,
aggressive 4. An explicit context intensity controls ITN, prompt hints, validation
and new History metadata consistently; raw remains 0. The eval corpus can specify
intensity. Small-number preservation at intensities 1–2 and compact-note behavior
are tested. The planned full intensity/settings migration remains separate.
Raw and code paths bypass ITN; Raw plus the legacy code profile now also retains
repeated words. Existing History rows are not rewritten.

The authored golden corpus grows by 102 cases from 90 to 192, reaching 150 new
cases across the command/ITN work. Two existing expectations intentionally adopt
the specified high-intensity numeric style: `three` → `3`, and `first note` →
`1st note`. Contact fields, dates/times/amounts, list counts, quotes, Native
Bengali/Arabic text, meaningful adverbs and lower-intensity prose are covered.
Currency-sign checks now also refuse a dropped sign before a currency symbol or
separated from its digits; bare-domain/email protection shares the same patterns
with validation.

Integrated validation: 938 tests pass with four optional native skips and real
preview/Silero/LID fixtures enabled; rules 192/192; adversarial 100/100; Ruff and
diff checks pass. There is no new download, cloud request or model-quality claim.
