# Dictionary correction learning

P5.6 is in progress. Offline frequency filtering and pure span alignment are
implemented; observing the inserted field, suggestions, Auto-add and Undo still
need integration.
Manual desktop acceptance remains deferred after Computer Use was stopped.

## Alignment policy

`suggest_correction(inserted, current, language)` accepts two already-scoped
insertion spans. It does not read a field, prove field identity or modify the
dictionary. Exactly one word may change; every character outside that word must
stay identical, including punctuation and whitespace. Returned offsets index the
original Python strings, while the candidate spelling is NFC. The future UIA
observer must handle UTF-16 conversion separately and prove the original field
is still the same non-password element before reading its retained range.

Words include Unicode letters/marks and internal apostrophes/hyphens. Input is
limited to 4096 characters, 512 words, and 3–64 characters per changed word. A
candidate must be uncommon and within one edit (two for words of at least six
characters), counting adjacent transposition. English ASCII names also have a
bounded [Soundex](https://www.archives.gov/research/census/soundex) route: matching
codes with at least two consonant digits, at most three edits and a length
difference of at most two. Independent National Archives examples verify the
coding rules. This heuristic is correction evidence, not pronunciation proof.

Case-only edits require name-like casing. Common words require an explicitly
known proper term or an exact built-in proper spelling (iPhone, iPad, iOS, macOS,
eBay, YouTube, GitHub, GitLab, OpenAI, WhatsApp). Arbitrary mixed casing such as
`tHe` is insufficient. Uppercase emphasis and casefold
expansions are skipped. The known-term scan is capped at 1024 entries. Unicode
normalization, Arabic vowel/tatweel and apostrophe-presentation changes alone
never create a word.

Known double-quoted/backtick literals, address shapes, numbers, identifier fragments, format-control
boundaries, mixed scripts, additions/deletions and broader rewrites are skipped.
Only single-script spaced alphabetic words are eligible; Chinese, Japanese,
Korean and other languages needing segmentation currently skip learning. Their
dictation support is unchanged. Unknown/Auto or unavailable frequency data also
skips. The tests include exact Kubernetes evidence with bundled data, Bengali and
Arabic corrections, raw Unicode offsets and the refusal cases above. No desktop
field observation is enabled by this foundation.

## Common-word filter

`saydraft/dictionary/frequency.py` reads bundled membership sets derived from
[wordfreq 3.1.1](https://pypi.org/project/wordfreq/3.1.1/), by **Robyn Speer**.
The 42 small lists contain entries occurring at least once per million words in
wordfreq's source data. They include English, Bengali and Arabic. This is a
conservative common-word filter, not a spell checker or a measure of whether a
correction is right. An absent word alone must never trigger learning.

Lookup normalizes Unicode compatibility forms and case, straightens curly
apostrophes, and removes Arabic vowel marks/tatweel. Bengali vowel marks remain.
Learned spelling must retain the user's original NFC form. Region tags resolve to
the base language; Norwegian, Serbo-Croatian and Filipino aliases share lists.
An unknown language, missing list or failed size/hash/decompression check returns
unavailable; callers must skip suggestions. Auto without a resolved language
must also skip. The loader caches at most four language sets and never writes to
the user's profile or accesses the network. No wordfreq runtime dependency or
extra model download is needed. The existing bundle includes the entire assets
directory.

## Dataset provenance and reproduction

`assets/dictionary/frequency/manifest.json` pins the source wheel URL, size and
SHA-256, original member names, all output hashes/counts and retained notices.
The adapted membership data remains **CC-BY-SA-4.0**; Saydraft's own Python code
remains MIT. The generator flattens frequency bins, omits empty/whitespace keys,
normalizes/deduplicates/sorts
lookup keys and writes gzip with a zero timestamp. Original wordfreq license and
all credits/citations following its published License section are retained,
including Marc Brysbaert and the other SUBTLEX authors. SUBTLEX is freely
available data. Google Books, Leeds, Wikipedia, ParaCrawl and OpenSubtitles
attribution remains in the retained notice. Full Apache-2.0 and CC-BY-SA-4.0 texts
are bundled.

Use development requirements (including msgpack 1.1.1), a local verified source
wheel and the complete CC license text. The generator performs no downloads,
does not import/install wordfreq, and refuses an existing output directory:

```powershell
python -m tools.build_frequency_lists --wheel <local-wheel> --license <local-CC-BY-SA-4.0.txt> --output <fresh-directory>
```

The CC text was retrieved from Creative Commons' own pinned
[source revision](https://github.com/creativecommons/cc-legal-tools-data/blob/a0dac18d1a773b4cdb7d8dd5d9bf4efab7901030/docs/licenses/by-sa/4.0/legalcode.txt)
because direct HTTP retrieval of the canonical text returned 403. Its canonical
[license URL](https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt) and
complete byte hash remain in the manifest. Tests verify all 42 distributed
language sets and notice hashes offline, common words in English/Bengali/Arabic,
unknown/corrupt-data refusal, bounded caching and unpinned-source rejection.
