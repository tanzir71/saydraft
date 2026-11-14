"""Bounded dictionary correction kernel for explicit English prose.

Only explicit English prose is eligible. Double Metaphone is an approximate
match, so every correction also needs a small unrestricted Damerau-Levenshtein
distance, a unique dictionary target and a non-common original spelling.
Hint transfer changes baseline dictionary spans only; it never adopts the rest
of a hinted transcript. Raw text and exact offsets accompany every edit.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from itertools import islice
import re
import unicodedata

from saydraft.dictionary.frequency import common_words, language_code, normalize_word
from saydraft.dictation.protect import literal_ranges
from saydraft.text_boundaries import whole_word_match

MAX_TEXT = 4096
MAX_TOKENS = 512
MAX_TERMS = 40
MAX_TERM = 64
MAX_WORDS = 6
MAX_EDITS = 16
_JOIN = "-'’"
_LITERALS = re.compile(r"```[\s\S]*?(?:```|\Z)|`[^`\n]*(?:`|\n|\Z)|(?<!\w)'[^'\n]*'(?!\w)")
_OPEN_QUOTE = re.compile(r'["“][^"”\n]*(?:["”]|\n|\Z)')


def _normal(text):
    return unicodedata.normalize('NFKC', text).casefold().replace('’', "'")


def damerau_levenshtein(left: str, right: str) -> int:
    """Unrestricted edit distance, including repeated/non-adjacent transpositions."""
    if max(len(left), len(right)) > MAX_TERM:
        raise ValueError('Distance operands exceed the fixed word/phrase bound')
    size = len(left) + len(right)
    matrix = [[0] * (len(right) + 2) for _ in range(len(left) + 2)]
    matrix[0][0] = size
    for i in range(len(left) + 1):
        matrix[i + 1][0], matrix[i + 1][1] = size, i
    for j in range(len(right) + 1):
        matrix[0][j + 1], matrix[1][j + 1] = size, j
    last = {}
    for i, a in enumerate(left, 1):
        match_column = 0
        for j, b in enumerate(right, 1):
            previous_row, previous_column = last.get(b, 0), match_column
            cost = int(a != b)
            if cost == 0:
                match_column = j
            matrix[i + 1][j + 1] = min(
                matrix[i][j] + cost, matrix[i + 1][j] + 1, matrix[i][j + 1] + 1,
                matrix[previous_row][previous_column] + i - previous_row - 1 + 1 + j - previous_column - 1)
        last[a] = i
    return matrix[-1][-1]


@dataclass(frozen=True)
class DictionaryEdit:
    start: int
    end: int
    before: str
    after: str
    term: str
    distance: int
    evidence: str


@dataclass(frozen=True)
class DictionaryResult:
    raw: str
    text: str
    edits: tuple[DictionaryEdit, ...] = ()
    reason: str = 'unchanged'


@dataclass(frozen=True)
class _Word:
    start: int
    end: int
    root_end: int
    root: str


def _tokens(text):
    words, i = [], 0
    while i < len(text):
        if unicodedata.category(text[i])[0] not in 'LN' and text[i] != '_':
            i += 1
            continue
        start = i
        i += 1
        while i < len(text):
            category = unicodedata.category(text[i])[0]
            if category in 'LMN' or text[i] == '_':
                i += 1
            elif text[i] in _JOIN and i + 1 < len(text) and text[i + 1].isalpha():
                i += 1
            else:
                break
        root_end = i - 2 if text[start:i].casefold().endswith(("'s", '’s')) else i
        words.append(_Word(start, i, root_end, text[start:root_end]))
        if len(words) > MAX_TOKENS:
            raise ValueError('Too many text tokens')
    return words


def _latin(root):
    letters = [char for char in root if unicodedata.category(char).startswith('L')]
    return bool(letters) and all('LATIN' in unicodedata.name(char, '') for char in letters) and all(
        unicodedata.category(char)[0] in 'LM' or char in _JOIN for char in root)


def _technical(root):
    pieces = re.split("[-'’]", root)
    return (root.isupper() or ('-' in root and not root.istitle()) or any(
        any(char.isupper() for char in piece[1:]) for piece in pieces))


def _letters(text):
    return ''.join(char for char in unicodedata.normalize('NFKD', text).casefold()
                   if char.isascii() and char.isalpha())


def _sequence(text, words):
    return bool(words) and all(text[a.end:b.start] and not text[a.end:b.start].strip(' \t')
                               for a, b in zip(words, words[1:]))


def _bounded(values, limit):
    if isinstance(values, (str, bytes)):
        raise ValueError('Pass a bounded sequence of terms')
    result = tuple(islice(values, limit + 1))
    if len(result) > limit or any(not isinstance(value, str) or not value or len(value) > MAX_TERM for value in result):
        raise ValueError('Invalid or excessive dictionary terms')
    return result


class DictionaryCorrector:
    """No model, profile, device, clipboard, network or OS input access.

    The Metaphone dependency is loaded lazily. Missing dependencies or
    corrupt/unavailable word lists preserve the whole original transcript.
    """

    def __init__(self, terms, *, protected_terms=(), phonetic=None):
        self.invalid = None
        self._phonetic = phonetic
        self._entries = []
        try:
            self.terms = _bounded(terms, MAX_TERMS)
            self.protected = _bounded(protected_terms, 256)
            forms = {}
            for term in self.terms:
                key = _normal(term)
                if key in forms and forms[key] != term:
                    raise ValueError('Conflicting canonical dictionary spellings')
                forms[key] = term
            for term in forms.values():
                words = _tokens(term)
                if (len(_normal(term)) > MAX_TERM or not 1 <= len(words) <= MAX_WORDS or not _sequence(term, words)
                        or words[0].start != 0 or words[-1].end != len(term)
                        or any(not _latin(word.root) or word.root_end != word.end for word in words)):
                    continue  # Unsupported entries are still protected exactly.
                self._entries.append((term, words, tuple(_normal(word.root) for word in words)))
        except (TypeError, ValueError):
            self.terms, self.protected = (), ()
            self.invalid = 'invalid_dictionary'

    def _protected_ranges(self, text, words):
        spans = list(literal_ranges(text)) + [match.span() for pattern in (_LITERALS, _OPEN_QUOTE)
                                             for match in pattern.finditer(text)]
        for term in (*self.terms, *self.protected):
            for form in {term, unicodedata.normalize('NFC', term), unicodedata.normalize('NFD', term)}:
                spans.extend(match.span() for match in re.finditer(re.escape(form), text, re.IGNORECASE)
                             if whole_word_match(text, match))
            signature = tuple(_normal(word.root) for word in _tokens(term))
            if not signature:
                continue
            for start in range(len(words) - len(signature) + 1):
                part = words[start:start + len(signature)]
                if _sequence(text, part) and tuple(_normal(word.root) for word in part) == signature:
                    spans.append((part[0].start, part[-1].end))
        return spans

    @staticmethod
    def _eligible(text, words, spans):
        if not _sequence(text, words) or any(not _latin(word.root) or _technical(word.root) for word in words):
            return False
        if any(word.root_end != word.end for word in words[:-1]):
            return False
        start, end = words[0].start, words[-1].end
        if any(start < right and end > left for left, right in spans):
            return False
        for side, char in enumerate((text[start - 1:start] if start else '', text[end:end + 1])):
            if char == '.' and side == 1 and (end + 1 == len(text) or not (
                    text[end + 1].isalnum() or text[end + 1] == '_')):
                continue
            if char and (char.isalnum() or unicodedata.category(char)[0] in 'MC' or char in "_./@#\\:$%='’+-"):
                return False
        return True

    def correct(self, text: str, *, language: str, hint: str | None = None,
                code_mode: bool = False, word_set: frozenset[str] | None = None) -> DictionaryResult:
        if not isinstance(text, str):
            raise TypeError('Transcript must be text')
        def unchanged(reason):
            return DictionaryResult(text, text, reason=reason)
        if self.invalid:
            return unchanged(self.invalid)
        if language_code(language) != 'en' or code_mode:
            return unchanged('unsupported_context')
        if not text or len(text) > MAX_TEXT or (hint is not None and (not isinstance(hint, str) or len(hint) > MAX_TEXT)):
            return unchanged('text_bounds')
        if any(char.isalpha() and 'LATIN' not in unicodedata.name(char, '') for char in text):
            return unchanged('mixed_or_unsupported_script')
        if not self._entries:
            return unchanged('no_eligible_terms')
        common = common_words('en') if word_set is None else word_set
        if not isinstance(common, frozenset):
            return unchanged('frequency_unavailable')
        try:
            encoder = self._phonetic
            if encoder is None:
                from metaphone import doublemetaphone
                encoder = doublemetaphone
            @lru_cache(maxsize=4096)
            def codes(value):
                result = encoder(_letters(value))
                if not isinstance(result, tuple) or len(result) != 2 or any(not isinstance(code, str) for code in result):
                    raise ValueError('Invalid phonetic encoder response')
                return frozenset(code for code in result if len(code) >= 2)
            index = defaultdict(set)
            for i, (term, _words, _signature) in enumerate(self._entries):
                for code in codes(term):
                    index[code].add(i)
            words = _tokens(text)
            spans = self._protected_ranges(text, words)
            windows = []
            if hint is None:
                for count in {len(entry[1]) for entry in self._entries}:
                    windows.extend((words[start:start + count], None) for start in range(len(words) - count + 1))
            else:
                hinted = _tokens(hint)
                matcher = SequenceMatcher(a=[_normal(word.root) for word in words],
                                          b=[_normal(word.root) for word in hinted], autojunk=False)
                for kind, a, b, c, d in matcher.get_opcodes():
                    if kind == 'replace' and 0 < b - a <= MAX_WORDS and 0 < d - c <= MAX_WORDS:
                        signature = tuple(_normal(word.root) for word in hinted[c:d])
                        windows.append((words[a:b], signature))
            edits = []
            for part, corroborated in windows:
                if not self._eligible(text, part, spans):
                    continue
                original = ' '.join(word.root for word in part)
                lexical = _normal(original)
                if len(lexical) > MAX_TERM or len(_letters(lexical)) < 4:
                    continue
                candidates = set().union(*(index[code] for code in codes(original)))
                if len(candidates) != 1:
                    continue  # Do not resolve phonetic ambiguity by a nearest-word tie-break.
                term, canonical, signature = self._entries[next(iter(candidates))]
                if corroborated is not None and corroborated != signature:
                    continue
                target = _normal(' '.join(word.root for word in canonical))
                distance = damerau_levenshtein(lexical, target)
                maximum = 2 if min(len(lexical), len(target)) >= 6 else 1
                if not 1 <= distance <= maximum:
                    continue
                pairs = list(zip(part, canonical, strict=True)) if len(part) == len(canonical) else None
                changed = [old for old, new in pairs if _normal(old.root) != _normal(new.root)] if pairs else part
                if any(normalize_word(word.root) in common for word in changed):
                    continue
                if pairs:
                    replacement = ''
                    for i, (old, new) in enumerate(pairs):
                        replacement += old.root if _normal(old.root) == _normal(new.root) else new.root
                        if i + 1 < len(pairs):
                            replacement += text[old.root_end:part[i + 1].start]
                else:
                    replacement = term
                start, end = part[0].start, part[-1].root_end
                edits.append(DictionaryEdit(start, end, text[start:end], replacement, term, distance,
                                            'phonetic' if hint is None else 'phonetic_context'))
            unique = {(edit.start, edit.end, edit.after): edit for edit in edits}
            edits = sorted(unique.values(), key=lambda edit: (edit.start, edit.end, edit.after))
            ambiguous = {i for i, edit in enumerate(edits) for j, other in enumerate(edits)
                         if i != j and edit.start < other.end and edit.end > other.start}
            edits = [edit for i, edit in enumerate(edits) if i not in ambiguous]
            if len(edits) > MAX_EDITS:
                return unchanged('edit_limit')
            output = text
            for edit in reversed(edits):
                output = output[:edit.start] + edit.after + output[edit.end:]
            return DictionaryResult(text, output, tuple(edits), 'corrected' if edits else 'no_unambiguous_match')
        except ImportError:
            return unchanged('phonetic_unavailable')
        except Exception:
            return unchanged('correction_unavailable')
