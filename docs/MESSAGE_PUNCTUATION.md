# Final punctuation

The default omits one external final period from a single-sentence message in
the `messages` or `work_chat` group. For the current app-profile editor, `chat`
also enables it when the captured group is `general` or empty. Executable/site
classification remains P5.3. Settings → Cleanup → Messaging switches it off;
`dictation.drop_message_period` is saved in the existing configuration. Missing
keys use `true`; an explicit `false` survives reload and service reconstruction.

Examples:

| Context/input | Final output |
| --- | --- |
| Work-chat: `The build is ready.` | `The build is ready` |
| Messages: `Thanks. Talk soon.` | `Thanks. Talk soon.` |
| Messages: `Call Dr. Smith.` | `Call Dr. Smith` |
| Messages: `I live in the U.S.` | `I live in the U.S.` |
| Messages: `হয়ে গেছে।` | `হয়ে গেছে` |
| Email: `"Hello."` | `"Hello."` |

Questions, exclamations, ellipses, structured lists, multiline text, literal
quotes/code and protected glossary values retain their punctuation. Decimal,
version, URL/email and finite English abbreviation shapes do not become sentence
boundaries. Ambiguous abbreviation boundaries before a capitalized word retain
the final period. Full stops `.`, `。`, `।` and `۔` are supported; sentence stops
also include Arabic `؟` and fullwidth question/exclamation marks. This is a
conservative finite detector, not semantic sentence understanding. Unknown
abbreviations can leave a period in place. Raw, Code, Notes, Email and Docs are
excluded from messaging edits.

The final policy runs after literal restoration and accepted LLM output. Email
gets a missing terminal period at that same stage, so a protected quote,
abbreviation or Unicode stop does not acquire a duplicate period. Generated
lists retain their layout. Ordinary command/ITN handling still runs earlier;
`a.m.`/`p.m.` remain visible for time conversion.

The actual transcript processor repeats the idempotent policy after snippets
and its formatter, then writes raw/cleaned History before insertion. Snippets
that expand to multiple sentences keep the final period. A formatting failure
preserves available text; a History failure still prevents insertion. No model
download, network call or Enter action is introduced.

Caret-aware joining now follows this punctuation policy; see
[caret formatting](CARET_FORMATTING.md) for its 40-case acceptance. Broader
restatements and opt-in Enter were completed separately in P4.5. The initial
punctuation change's 40 authored golden rows brought the corpus to 326; that
change required all 326 plus the separate 100 adversarial
refusals. Focused cases cover accepted model output, protected terms, config
persistence, service wiring and the actual snippet/History/insertion ordering.

Validation: 1110 tests pass, four optional native tests skip, with real local
Silero/preview/language-ID fixtures enabled; rules 326/326; adversarial 100/100;
Ruff and diff checks pass. Offscreen Settings was rendered and visually checked
at `build/qa/message-period-ui-20261112/cleanup-settings.png` using Windows Segoe
UI fonts. No owner profile or live application was edited.
The 50,001-character non-abbreviation regression stays under a generous two
second cap; matching cannot restart after every dot in that token.
