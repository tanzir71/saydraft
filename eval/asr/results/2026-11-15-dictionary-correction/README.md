# Frozen dictionary correction development protocol

Confirmation is complete: source `e44b93a`, 96 native decodes and 192 records,
exit 0 after 123.26 seconds. Both admitted variants raise matches **15→22/43
(+46.67%)**, with seven edits, word errors 234→227, character errors 917→908,
zero false positives and no per-clip regressions. The frozen tie-break selects
phonetic-only, with no additional ASR pass. Exact output/source/process/guard
and independent actual-payload verification are in `confirmation/`. Recording
sets share prompts; speaker independence and owner accuracy remain unverified.
The 60 Bengali/Tamil/Telugu confirmation clips remain unused.

Application integration uses the selected kernel in normal resolved-English
cleanup, preserving raw ASR History, literal/protected content and Verbatim/code
behavior. Its scalable glossary index replays all 96 qualified outputs exactly
and checks ambiguity beyond 40 entries. Metaphone 0.6 is now a pinned runtime
dependency with its complete license collected from the actual wheel. The
earlier isolated-install recipe remains hash locked. Full-pipeline/package
qualification results follow when complete.

Development source `604b5556c423c3edf2ed9961365e6f9c3316167c` completes all 384
text-processing records, exit 0 after 5.06 seconds, with unchanged source/plan/
inputs/package hashes. Phonetic correction raises Parakeet matches **15→20/43**
(33.33% relative) with five edits, no false positives and no per-clip regressions.
The combined path produces the same scores. Both pass the frozen development
gate; transfer alone gains 6.67%, while Whisper variants gain at most 18.18%.
The independent scorer replays every edit and verifies metrics, common-word
filter, true Damerau distance, pinned phonetic codes, source and input hashes.
The expanded prototype suite passes **300 tests**. At that development checkpoint
no production path had been activated.

`confirmation-plan.json` freezes a separate 48-recording test before decoding:
the original second recordings, unchanged dictionary/correction/package/wordlist,
Parakeet greedy plus the same beam/hotword provider, and both development-passing
variants. It requires the same ≥30%/no-regression gates and retains every case.
Equal accuracy favors the phonetic-only path because it needs no extra ASR pass.
These are separate audio files with shared prompts and unverified speaker
independence, not new text or owner acceptance.

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

The original `604b555` candidate was not connected to dictation; application
integration follows confirmation. `eval/asr/dictionary-correction-requirements.txt`
locks the same Metaphone 0.6 source SHA-256 for isolated evaluation installs.
The [upstream package](https://pypi.org/project/Metaphone/0.6/) is BSD licensed;
the unchanged license, source metadata and installation provenance are retained.
No model downloads, audio capture/playback, clipboard, hooks or owner profile
are used. Local tests and direct main pushes remain the delivery path.

See the [investigation](../../../../docs/spikes/biasing.md) for previous results
and the [original names corpus](../2026-11-14-dictionary-names/) for Google FLEURS
CC-BY-4.0 attribution and the separately verified native inputs.
