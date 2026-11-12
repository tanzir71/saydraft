# Code mode

Select `code/comments` under Settings → Cleanup → Default profile to use the
code renderer. The Code app-group context uses the same path; executable/site
classification follows in P5.3. Raw mode bypasses command rendering.

| Spoken text | Output |
|---|---|
| camel case user name | `userName` |
| snake case user name | `user_name` |
| kebab case user name | `user-name` |
| pascal case user name | `UserName` |
| constant case user name | `USER_NAME` |
| git dash dash version | `git --version` |
| at file src slash app dot py | `@src/app.py` |
| items open bracket number zero close bracket | `items[0]` |

One-word case aliases such as `camelcase` are accepted. A naming command consumes
its words up to the next symbol/command or typed delimiter. Symbols include
parentheses/brackets/braces, quotes, assignment/comparison/arithmetic/logical
operators, comma/colon/semicolon, dot/slash/backslash, and new lines. `number`
explicitly introduces a complete numeric literal. File mentions consume a name
and spoken path joins; a following CLI flag stays a separate argument.

The renderer applies no prose capitalization, filler deletion, repetition
collapse or final-period insertion. Both Code profile and Code app-group paths
bypass the cleanup LLM. Existing typed strings (including escaped single/double
quotes), fenced/inline code, comments, addresses/dotted names and protected
dictionary terms are masked and restored. Clear typed-syntax lines without an
explicit multiword dictation command stay literal. Identifier contexts preserve
operator names in declarations/imports/returns and file names. Existing
indentation and line endings are retained; command-adjacent spacing is rendered
for code syntax. Generated line/literal masks restore in order without collisions.

This is a finite explicit grammar, not a compiler or code-generation model.
Reserved command words are interpreted in Code context; Raw and literal spans
provide verbatim text. Empty/unsupported naming or number operands retain their
cue instead of dropping words. Protected literal operands are not renamed. The
renderer produces text only; the existing History/focus/insertion path owns any
later paste. No command is executed by rendering.

The golden set grows from 192 to 286 with 94 authored Code cases covering both
entry paths, Raw override, Unicode names, literal code and combined commands.
Three legacy code expectations intentionally change: repeated words remain,
and an explicit spoken comma becomes punctuation. CI's minimum rises to 286;
P4.7 remains unchecked until 300 and remaining behavior coverage are complete.

Validation: 1044 tests pass with four optional native skips and real
preview/Silero/LID fixtures enabled; rules 286/286; adversarial 100/100; Ruff/diff
checks pass. A development text probe preserves 50,000 literal characters in
7 ms, renders 26,000 symbol-command characters in 14 ms and 15,000 naming-command
characters in 9 ms. These observations are not tier or ASR-accuracy claims.
Messaging-period behavior, broader restatements and opt-in Enter still remain
before P4.5 is checked off.
