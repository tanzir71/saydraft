# Spoken text command foundation

`cleanup/commands.py` renders the existing spoken punctuation path and extends it
with parentheses, brackets, opening/closing quotes, em/en dashes, ellipsis,
hyphen joining, apostrophe-s, `cap <word>` and `all caps <word>`. Capitalization
applies to the next word. Common noun contexts such as “the cap on spending” and
“in all caps for headings” remain literal. Punctuation and paragraph/newline
switches remain independent.

The current Aggressive mode uses the extended punctuation path. Existing
Balanced/Raw choices keep their command behavior until the planned intensity
settings migration. No keyboard or app action is executed by this module.
“Press enter” remains transcript text; its explicit opt-in action is separate
remaining P4.5/Windows integration work.

The pipeline protects existing code, quotes, URLs, emails and glossary before
command rendering. Capitalization markers preceding a protected token are
consumed without changing its literal value. Curly quotes now receive the same
protection and validation as straight quotes. Newly spoken opening marks allow
sentence-initial capitalization; existing quoted text stays exact. Hyphen and
apostrophe-s join only the explicitly spoken marker's surrounding text.

The rules corpus grows from 42 to 90 examples with 48 authored sentence-level
cases: commands combined with fillers, email final punctuation, paragraphs,
protected text and literal noun uses. All original cases remain unchanged and
pass. Unit checks also cover command switches, word-boundary substrings,
protected-name/code behavior and the absence of app actions.

Validation: 809 tests pass with four optional native skips and real
preview/Silero/LID fixtures enabled; rules 90/90; adversarial validation 100/100;
Ruff and diff checks pass. This completes the command foundation, while ITN,
backtrack extensions, code mode, messaging formatting and opt-in Enter remain
before P4.5's 150-new-case acceptance. P4.7 still needs at least 300 golden cases.
