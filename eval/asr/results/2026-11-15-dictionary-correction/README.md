# Frozen dictionary correction development protocol

This is a separate experiment on the **already observed** 40-name English
development set. The earlier five native arms and failed per-clip gates remain
unchanged. This experiment does not claim new or unseen speech. No reserved
English or Bengali/Tamil/Telugu recording is decoded by this tool.

`plan.json` freezes the correction source hashes, actual pinned Metaphone code,
bundled common-word list, 48 IDs, all original native input hashes, six candidate
arms and strict criteria before correction output is computed. The candidates
are phonetic correction, guarded context transfer, and transfer followed by
phonetic correction, each compared with its own Parakeet/Whisper baseline.
There are 384 output records including the two unmodified baseline arms.

Every change requires a unique Double Metaphone target and a small unrestricted
Damerau–Levenshtein distance. Common original words, ambiguous targets, existing
dictionary/protected terms, code/literals/addresses/identifiers and numbers are
preserved. The candidate handles bounded Latin names/phrases and possessives
in explicit English prose. Other languages, mixed scripts, code mode, missing
runtime/word lists or invalid bounds preserve the original text. Transfer uses
aligned dictionary spans from the hinted output and retains all other baseline
bytes. It has no reference transcript or utterance-ID input. All raw text and
edits with offsets relative to each stage input are retained.

The frozen gate requires at least 30% relative exact name-recall improvement,
no added false positives and no per-clip increase in word/character errors or
number/acronym surface errors, with every case complete. Passing development
only selects a candidate for a separate frozen confirmation run. It does not
qualify production integration, broad accuracy or owner acceptance.

`saydraft.asr.biasing` is not connected to the dictation path. Metaphone 0.6 is
pinned for development; `eval/asr/dictionary-correction-requirements.txt` locks
the source SHA-256 for an isolated install. It is not a shipping dependency.
The [upstream package](https://pypi.org/project/Metaphone/0.6/) is BSD licensed;
the unchanged license, source metadata and installation provenance are retained.
No model downloads, audio capture/playback, clipboard, hooks or owner profile
are used. Local tests and direct main pushes remain the delivery path.

See the [investigation](../../../../docs/spikes/biasing.md) for previous results
and the [original names corpus](../2026-11-14-dictionary-names/) for Google FLEURS
CC-BY-4.0 attribution and the separately verified native inputs.
