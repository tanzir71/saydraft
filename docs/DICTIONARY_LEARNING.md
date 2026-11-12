# Dictionary correction learning

P5.6 is in progress. The offline frequency filter is implemented; observing the
inserted field, alignment, suggestions, Auto-add and Undo still need integration.
Manual desktop acceptance remains deferred after Computer Use was stopped.

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
