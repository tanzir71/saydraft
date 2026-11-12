# Cleanup golden evaluation

The rules-only command is:

```powershell
python -m saydraft.eval --min-pass-rate 100 --min-cases 192
```

CI currently requires all 192 unique examples to pass. The minimum will rise with
the corpus toward P4.7's 300-case acceptance; P4.7 remains unchecked. The separate
adversarial command requires at least 100 refusals and a 100% catch rate.

Each JSONL row requires nonblank `id` and string `input`/`expected`. Empty text is
allowed for intentional empty/verbatim cases. Optional fields are `mode`,
`profile`, `intensity`, `app_title`, `app_group`, `before_caret`, and `language`.
Defaults match `DictationContext`; every context field reaches the actual
pipeline. For example:

```json
{"id":"code-context","input":"two files","expected":"two files","app_group":"code","before_caret":"x = ","language":"en"}
```

The loader rejects unknown fields rather than silently ignoring a misspelled
context key. It also rejects invalid modes/profiles/intensities, duplicate JSON
fields, duplicate IDs, duplicate input/expected/context examples, and empty
corpora. Context differences can intentionally create distinct examples. Raw can
declare intensity 0; other modes accept explicit intensities 1–4. Small custom
corpora remain available by omitting the CI minimum or setting `--min-cases`.

The runner compares exact output strings through the cleaner pipeline. It opens
no microphone or insertion port. A context-forwarding test both observes the
complete context and proves that the real Code-group path is exercised. Further
tests prove malformed/duplicate/shrunk datasets cannot claim passing acceptance.
Passing a context does not prove a future formatter implements its behavior;
the corresponding authored expected-output cases still have to pass.

The optional injected pipeline supports future model evaluation, but an output
pass rate alone does not prove a model was used. The bake-off must separately
record actual model use, refusals, timeouts and rules fallback. This change makes
no model-quality or owner-ASR accuracy claim.

Validation: 952 tests pass with four optional native skips and real
preview/Silero/LID fixtures enabled; rules 192/192; adversarial 100/100; Ruff and
diff checks pass.
