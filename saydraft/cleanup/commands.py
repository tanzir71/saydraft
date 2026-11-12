"""Render explicit spoken text commands; never execute keyboard/app actions."""

import re

SPOKEN_PUNCTUATION = (
    ("exclamation point", "!"), ("exclamation mark", "!"), ("question mark", "?"),
    ("open parenthesis", "("), ("close parenthesis", ")"),
    ("open paren", "("), ("close paren", ")"),
    ("open bracket", "["), ("close bracket", "]"),
    ("open quote", "“"), ("close quote", "”"),
    ("full stop", "."), ("em dash", "—"), ("en dash", "–"),
    ("semicolon", ";"), ("ellipsis", "…"), ("comma", ","),
    ("period", "."), ("colon", ":"), ("dash", "—"),
)
_PUNCTUATION = dict(SPOKEN_PUNCTUATION)
_PHRASES = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(phrase) for phrase, _ in SPOKEN_PUNCTUATION)
                      + r")(?!\w)", re.IGNORECASE)
_WORD = r"[^\W\d_][\w’'-]*"
_CAPS = re.compile(rf"(?<!\w)(all caps|cap)[ \t]+(__(?:SPAN|GLOSSARY)_\d+__|{_WORD})(?!\w)", re.IGNORECASE)
_CAP_NOUNS = frozenset(("the", "a", "an", "spending", "budget", "price", "salary", "market", "in", "using"))
_CAP_FOLLOWING = frozenset(("on", "of", "for", "and", "is", "was", "will", "table", "style"))


def _capitalize(text):
    def replace(match):
        before = re.findall(_WORD, text[:match.start()])
        if (before and before[-1].casefold() in _CAP_NOUNS) or match[2].casefold() in _CAP_FOLLOWING:
            return match[0]
        word = match[2]
        if word.startswith("__"):
            return word  # The command never changes a protected literal/name.
        return word.upper() if match[1].casefold() == "all caps" else word[0].upper() + word[1:]

    return _CAPS.sub(replace, text)


def render_commands(text, *, convert_newlines=False, convert_punctuation=True):
    if not text:
        return text
    out = text
    if convert_newlines:
        out = re.sub(r"(?<!\w)new paragraph(?!\w)", "\n\n", out, flags=re.IGNORECASE)
        out = re.sub(r"(?<!\w)(?:new line|newline)(?!\w)", "\n", out, flags=re.IGNORECASE)
    if convert_punctuation:
        out = _capitalize(out)
        # These joiners consume surrounding spaces only when explicitly spoken.
        out = re.sub(r"[ \t]+hyphen[ \t]+", "-", out, flags=re.IGNORECASE)
        out = re.sub(r"(?<!\w)hyphen(?!\w)", "-", out, flags=re.IGNORECASE)
        out = re.sub(r"[ \t]+apostrophe[ -]+s(?!\w)", "'s", out, flags=re.IGNORECASE)
        out = _PHRASES.sub(lambda match: _PUNCTUATION[match[0].casefold()], out)
        out = re.sub(r"([([“])[ \t]+", r"\1", out)
        out = re.sub(r"[ \t]+([)\]”])", r"\1", out)
        out = re.sub(r"[ \t]*([—–])[ \t]*", r" \1 ", out)
        out = re.sub(r"[ \t]+…", "…", out)
    out = re.sub(r"[ \t\f\v]+([,.!?;:])", r"\1", out)
    out = re.sub(r"([,.!?;:])([A-Za-z])", r"\1 \2", out)
    out = re.sub(r"[ \t]*\n[ \t]*", "\n", out)
    return out.strip()
