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

The parser has 106 focused cases covering supported forms, refusal/literal
examples, Unicode preservation, low-intensity prose and malformed long tokens.
A long-token probe exposed quadratic restart matching in the original address
patterns: 10,000 dotted characters took 1.416 s. Boundary-aware patterns reduce
that to 0.028 s; 50,000 dotted/hyphenated characters take 0.147/0.121 s in this
development probe. A generous two-second regression check covers the long dotted
case. These observations are not hardware-tier or general release-latency claims.

This is a finite deterministic grammar. Unsupported or ambiguous forms can stay
literal; it does not claim spoken-detail normalization for Bengali/Arabic or all
languages. Existing Unicode text remains unchanged. Full pipeline integration,
ordering around repetition/list/command cleanup and sentence-level golden
acceptance follow in the next change; this parser foundation alone changes no
running-app behavior. P4.5 remains unchecked.
