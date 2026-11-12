# Backtracks and restatements

`cleanup/backtrack.py` replaces equal-word-count tail deletion with bounded
clause/phrase alignment. The existing `dictation.rules.apply_self_corrections`
entry point masks literal quotes, code, addresses, abbreviations and reserved
tokens before delegating. Corrections delete source ranges and retain every
unaffected source slice, including Unicode marks, case and punctuation.

| Dictation | Rules result |
| --- | --- |
| `send it to John Smith actually Jane` | `Send it to Jane` |
| `use old endpoint actually new production endpoint` | `Use new production endpoint` |
| `call John actually Jane actually Priya` | `Call Priya` |
| `I can attend no actually I cannot attend` | `I cannot attend` |
| `I bought it as a gift… as a present` | `I bought it as a present` |
| `I would like blue… I would like red` | `I would like red` |
| `I actually agree` | `I actually agree` |

Explicit cues are actually, scratch that, never mind, no wait, I mean, sorry,
no actually and no sorry. Repeated phrase prefixes, proper-name tails and finite
English verb/preposition slots align replacements of different lengths. A
shared internal frame handles `Friday at two → Monday at three`. Continuations
after the replacement remain intact; the whole remaining transcript is no
longer treated as a six-word replacement. Multiple cues are processed in order,
with overlapping deletions merged before reconstruction. Strong cues can
restart a clause with a new subject/action, including an explicit negation.

Natural restatements require an ellipsis or dash pause plus a repeated
preposition/article frame or repeated subject/clause prefix. Ordinary comma
lists, conjunctions, unpaused roles and incomplete restarts stay literal.
No acoustic pause is inferred from text: if ASR supplies no pause/command, this
natural-restatement path does not guess one. English spoken `ellipsis` is
rendered by the existing command stage before this pass.

Adverb, apology, literal phrase and sentence/paragraph guards preserve examples
such as `The app actually responds quickly`, `I am sorry I missed the meeting`,
`I mean well`, and `please scratch that itch`. Unknown capitalized clause openers
stay literal when name/verb alignment is ambiguous. This is a finite grammar,
not semantic understanding or a claim of general multilingual correction.
Cross-script names retain their exact text; English cue words can occur beside
Bengali/Arabic and other language text. The original ASR remains in History.

As before, the current Aggressive mode enables backtracks; Balanced retains
its legacy behavior until the P5.7/P6 styles migration. Raw and Code bypass
prose repair. Bounded 64-token windows and a 12-token old-fragment cap for
natural restatements limit ambiguous scope and scanning cost. Long text and
thousands of independent corrections have regression coverage.

There are 54 new authored golden examples (326 → 380), including a long
paragraph, must-keep profanity, script mixing, and literal/Raw/Code exclusions.
CI requires all 380 and the separate 100 adversarial refusals. Opt-in trailing
Enter is now integrated in `docs/VOICE_ENTER.md`; P4.7 still needs final model
bake-off acceptance.

Validation: 1185 tests pass, four optional native tests skip, with real local
Silero/preview/language-ID fixtures enabled; rules 380/380; adversarial 100/100;
Ruff and diff checks pass. A 2000-correction/30,000-word regression has a generous
three-second bound. No microphone, OS insertion, network or owner profile was
used for this change.
