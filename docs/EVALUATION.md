# Cleanup golden evaluation

The deterministic rules and authored validator commands are:

```powershell
python -m saydraft.eval --min-pass-rate 100 --min-cases 556
python -m saydraft.cleanup.llm.eval_validation --min-catch-rate 100 --min-cases 100
```

CI requires all 556 unique examples to pass, exceeding P4.7's 300-case minimum.
Eighty-four cover the complete app-group/tone/intensity matrix; see [styles](STYLES.md).
Forty authored caret cases cover P5.4; see [caret formatting](CARET_FORMATTING.md).
P4.5's deterministic behaviors and snippet/Enter coverage are complete. P4.7
remains unchecked until the model bake-off establishes §11's rules+LLM threshold
and zero must-keep regressions. The separate
adversarial command requires at least 100 refusals and a 100% catch rate.

These authored checks are separate from native model generation. The current
pipeline also enforces [post-rules content-word preservation](VALIDATOR_V2.md)
at intensities 1–3. The retained
[2026-11-13 baseline](../eval/cleanup/results/2026-11-13-baseline/README.md)
predates that fix; replacement forced-model and production-policy reports must
meet the current [source/corpus evidence contract](CLEANUP_EVIDENCE.md).

Each JSONL row requires nonblank `id` and string `input`/`expected`. Empty text is
allowed for intentional empty/verbatim cases. Optional fields are `mode`,
`profile`, `intensity`, `tone` (formal/casual/very_casual), `app_title`, `app_group`, `before_caret`, `language`,
`voice_enter_enabled`, `expected_enter`, a string-to-string `snippets` object,
`before_caret_known`, `selection`, `selection_known`, `selection_truncated`,
`after_caret` (at most one complete Unicode character) and `after_caret_known`.
Defaults match `DictationContext`; every context field reaches the actual
pipeline. For example:

```json
{"id":"delivery","input":"sig press enter","expected":"Thanks.","voice_enter_enabled":true,"expected_enter":true,"snippets":{"sig":"Thanks."}}
```

The loader rejects unknown fields rather than silently ignoring a misspelled
context key. It also rejects invalid modes/profiles/intensities, duplicate JSON
fields, duplicate IDs, duplicate input/expected/context examples, and empty
corpora. Action fields require actual booleans; invalid snippet values and aliases
that collide after case/whitespace normalization are rejected. Context differences
can intentionally create distinct examples. Raw can
declare intensity 0; other modes accept explicit intensities 1–4. Small custom
corpora remain available by omitting the CI minimum or setting `--min-cases`.

The runner uses the actual transcript processor: source intent → protected
cleanup → snippet expansion/final formatting → in-memory History → simulated
insertion. It compares both exact text and the observed Enter flag; output text
alone cannot satisfy an action case. The injected insertion port acknowledges
requested delivery without issuing any real key. Native event shape, focus,
failure and cancellation are verified separately by integration tests. It opens
no microphone, database or live OS insertion port. A context-forwarding test both
observes the complete context and proves the real Code-group path is exercised. Further
tests prove malformed/duplicate/shrunk datasets cannot claim passing acceptance.
Passing a context does not prove a future formatter implements its behavior;
the corresponding authored expected-output cases still have to pass.

Retained 432/472-case native model reports are historical evidence. They cannot
satisfy current-corpus acceptance; the checker rejects mismatched corpus hashes
and stale source. Its unit tests generate explicitly synthetic metadata/counts
inside temporary folders and never rewrite retained reports or earn model credit.

The optional injected pipeline and shared `execute_case` also support native model
evaluation. Output pass rate alone does not prove a model was used: the
[candidate runner](CLEANUP_CANDIDATES.md#reproducible-native-measurements) separately
records calls, token counts, refusals, timeouts and rules fallback. Accepted-model
exact passes are reported independently; fallback receives no model credit.
This makes no model-quality or owner-ASR accuracy claim.

Messaging adds 40 authored examples (286 → 326), covering app/profile guards,
abbreviations, literals, Unicode punctuation and multi-sentence boundaries.
Final policy also runs after snippet expansion in the actual processor, before
History and insertion; those paths have separate integration checks. Details:
`docs/MESSAGE_PUNCTUATION.md`.

Backtracks add 54 authored examples (326 → 380) for changed-length replacements,
chained cues, natural restatements, literal/adverb guards, mixed scripts and a
long paragraph. See `docs/BACKTRACKS.md` for supported frames and ambiguity
limits. These rules-only results do not establish model bake-off acceptance.

Delivery/snippets add 52 authored examples (380 → 432), covering default-off,
Email/Docs, Raw/Code, literal/quoted questions, mixed scripts, nonrecursive opaque
snippets and protected/final punctuation ordering. Validation: 1268 tests pass
with four optional native skips and local fixtures; golden 432/432; adversarial
100/100; Ruff/diff and Settings visual checks pass. See `docs/VOICE_ENTER.md`.
