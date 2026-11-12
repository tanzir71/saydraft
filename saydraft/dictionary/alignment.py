"""Conservative correction evidence from two already-scoped insertion spans."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import islice

from saydraft.dictation.protect import literal_ranges
from .frequency import is_common, language_code, normalize_word

MAX_SPAN = 4096
MAX_TOKENS = 512
MAX_WORD = 64
_JOINERS = "'-’"
_SCRIPTS = {"LATIN", "CYRILLIC", "GREEK", "ARABIC", "BENGALI", "DEVANAGARI", "HEBREW", "TAMIL"}
_UNSEGMENTED = {"ja", "zh", "ko", "th", "lo", "km", "my"}
_PROPER_SPELLINGS = {"iPhone", "iPad", "iOS", "macOS", "eBay", "YouTube",
    "GitHub", "GitLab", "OpenAI", "WhatsApp"}
_SOUND_GROUPS = {letter: str(i) for i, group in enumerate(
    ("BFPV", "CGJKQSXZ", "DT", "L", "MN", "R"), 1) for letter in group}


@dataclass(frozen=True)
class CorrectionCandidate:
    original: str
    term: str
    original_start: int
    original_end: int
    current_start: int
    current_end: int
    reason: str


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


def _tokens(text):
    result, i = [], 0
    while i < len(text):
        if not unicodedata.category(text[i]).startswith("L"):
            i += 1
            continue
        start = i
        i += 1
        while i < len(text):
            if unicodedata.category(text[i])[0] in "LM":
                i += 1
            elif (text[i] in _JOINERS and i + 1 < len(text)
                    and unicodedata.category(text[i + 1]).startswith("L")):
                i += 1
            else:
                break
        result.append(_Token(text[start:i], start, i))
        if len(result) > MAX_TOKENS:
            return []
    return result


def _script(word):
    scripts = {unicodedata.name(c, "").split(" ", 1)[0] for c in word
        if unicodedata.category(c).startswith("L")}
    return next(iter(scripts)) if len(scripts) == 1 and scripts <= _SCRIPTS else None


def _isolated(text, token):
    if any(token.start < end and token.end > start for start, end in literal_ranges(text)):
        return False
    for c in (text[token.start - 1:token.start] if token.start else "", text[token.end:token.end + 1]):
        if c and (c.isalnum() or unicodedata.category(c)[0] in "MC" or c in "_/@#\\$'’-"):
            return False
    return True


def _distance(a, b, limit):
    """Bounded-length optimal string alignment, including adjacent transposition."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous, older = list(range(len(b) + 1)), None
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            value = min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (x != y))
            if older is not None and i > 1 and j > 1 and x == b[j - 2] and a[i - 2] == y:
                value = min(value, older[j - 2] + 1)
            row.append(value)
        older, previous = previous, row
    return min(previous[-1], limit + 1)


def _soundex(word):
    # National Archives coding rules; English ASCII names only. H/W do not
    # separate equal consonant codes; vowels/Y do. This is not a speech model.
    if not word.isascii() or not word.isalpha() or len(word) < 4:
        return ""
    word = word.upper()
    last, digits = _SOUND_GROUPS.get(word[0], ""), ""
    for c in word[1:]:
        if c in "HW":
            continue
        code = _SOUND_GROUPS.get(c, "")
        if code and code != last:
            digits += code
        last = code
        if len(digits) == 3:
            break
    return word[0] + digits.ljust(3, "0") if len(digits) >= 2 else ""


def _brand_case(letters):
    return any(a.islower() and b.isupper() and c.islower()
        for a, b, c in zip(letters, letters[1:], letters[2:]))


def _name_case(term, known):
    if known:
        return True
    letters = "".join(c for c in term if c.isalpha())
    return letters.istitle() or _brand_case(letters)


def suggest_correction(inserted: str, current: str, language: str, *,
        known_terms: Iterable[str] = (),
        common_check: Callable[[str, str], bool | None] = is_common) -> CorrectionCandidate | None:
    """No I/O except the bundled word filter; offsets index the original Python strings.

    The caller must prove both spans belong to the same non-password insertion.
    This function cannot establish field identity or authorize reading a field.
    """
    code = language_code(language)
    if (not isinstance(inserted, str) or not isinstance(current, str)
            or not inserted or not current or max(len(inserted), len(current)) > MAX_SPAN
            or code is None or code in _UNSEGMENTED):
        return None
    before, after = _tokens(inserted), _tokens(current)
    if not before or len(before) != len(after):
        return None
    changed = [(a, b) for a, b in zip(before, after)
        if unicodedata.normalize("NFC", a.text) != unicodedata.normalize("NFC", b.text)]
    if len(changed) != 1:
        return None
    a, b = changed[0]
    if (inserted[:a.start] != current[:b.start] or inserted[a.end:] != current[b.end:]
            or not _isolated(inserted, a) or not _isolated(current, b)):
        return None
    original, term = (unicodedata.normalize("NFC", token.text) for token in (a, b))
    if not 3 <= min(len(original), len(term)) <= max(len(original), len(term)) <= MAX_WORD:
        return None
    script = _script(original)
    if script is None or script != _script(term):
        return None
    common = common_check(term, language)
    if common is None:
        return None
    old, new = original.casefold(), term.casefold()
    if old == new:
        known = term in _PROPER_SPELLINGS or any(isinstance(word, str) and len(word) <= MAX_WORD
            and unicodedata.normalize("NFC", word) == term for word in islice(known_terms, 1024))
        if original.lower() != term.lower() or not _name_case(term, known):
            return None
        # Casing alone cannot establish that a common word is a proper noun.
        if common and not known:
            return None
        reason = "capitalization"
    else:
        if common or normalize_word(original) == normalize_word(term):
            return None
        distance = _distance(old, new, 3)
        if distance <= (2 if min(len(old), len(new)) >= 6 else 1):
            reason = "spelling"
        elif (code == "en" and distance <= 3 and abs(len(old) - len(new)) <= 2
                and _soundex(old) and _soundex(old) == _soundex(new)):
            reason = "phonetic"
        else:
            return None
    return CorrectionCandidate(original, term, a.start, a.end, b.start, b.end, reason)
