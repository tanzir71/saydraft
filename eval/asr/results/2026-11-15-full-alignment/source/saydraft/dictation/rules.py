from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from saydraft.cleanup.commands import render_commands
from saydraft.cleanup.commands import SPOKEN_PUNCTUATION as SPOKEN_PUNCTUATION
from saydraft.cleanup.itn import normalize_addresses, normalize_itn
from saydraft.cleanup.backtrack import repair_backtracks
from .protect import protect_spans, restore_spans

FILLER_PHRASES_CONSERVATIVE: Tuple[str, ...] = (
    "um",
    "umm",
    "uh",
    "uhm",
    "erm",
    "er",
    "ah",
    "hmm",
    "mm",
    "mmm",
    "mhm",
)

FILLER_PHRASES_AGGRESSIVE: Tuple[str, ...] = (
    "like",
    "you know",
    "basically",
    "sort of",
    "kind of",
)


@dataclass(frozen=True)
class RuleOptions:
    remove_fillers: bool = True
    aggressive_fillers: bool = False
    remove_repetitions: bool = True
    handle_self_corrections: bool = True
    normalize_punctuation: bool = True
    normalize_capitalization: bool = True
    normalize_whitespace: bool = True
    enable_list_formatting: bool = False
    convert_spoken_punctuation: bool = True
    convert_spoken_newlines: bool = False
    final_period: bool = False
    normalize_itn: bool = False
    intensity: int = 3
    number_style: str = "prose"


def normalize_whitespace(text: str) -> str:
    if not text:
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_spoken_punctuation(
    text: str,
    convert_newlines: bool,
    convert_punctuation: bool = True,
) -> str:
    return render_commands(text, convert_newlines=convert_newlines, convert_punctuation=convert_punctuation)


def remove_fillers(text: str, aggressive: bool) -> str:
    if not text:
        return text
    out = text

    for phrase in sorted(FILLER_PHRASES_CONSERVATIVE, key=len, reverse=True):
        out = _remove_high_confidence_filler(out, phrase)

    if aggressive:
        for phrase in sorted(FILLER_PHRASES_AGGRESSIVE, key=len, reverse=True):
            out = _remove_ambiguous_filler(out, phrase)

    return _normalize_filler_spacing(out)


def _remove_high_confidence_filler(text: str, phrase: str) -> str:
    pattern = _phrase_pattern(phrase, consume_trailing_comma=True)
    return re.sub(pattern, " ", text, flags=re.IGNORECASE)


def _remove_ambiguous_filler(text: str, phrase: str) -> str:
    pattern = _phrase_pattern(phrase, consume_trailing_comma=True)

    def replace(match: re.Match[str]) -> str:
        before_word = _last_word(text[: match.start()])
        after_word = _first_word(text[match.end() :])
        at_start = before_word is None
        if _should_remove_ambiguous_filler(phrase, before_word, after_word, at_start):
            return " "
        return match.group(0)

    return re.sub(pattern, replace, text, flags=re.IGNORECASE)


def _phrase_pattern(phrase: str, *, consume_trailing_comma: bool = False) -> str:
    words = [re.escape(part) for part in phrase.split()]
    pattern = r"(?<!\w)" + r"[\s,]+".join(words) + r"(?!\w)"
    if consume_trailing_comma:
        pattern += r"\s*,?"
    return pattern


def _should_remove_ambiguous_filler(
    phrase: str,
    before_word: str | None,
    after_word: str | None,
    at_start: bool,
) -> bool:
    before = before_word.lower() if before_word else None
    after = after_word.lower() if after_word else None

    if phrase == "basically":
        return True

    if phrase == "like":
        return at_start or before in {"is", "are", "was", "were", "be", "been", "being"}

    if phrase == "you know":
        return after not in {
            "a",
            "an",
            "the",
            "this",
            "that",
            "these",
            "those",
            "what",
            "when",
            "where",
            "why",
            "how",
            "my",
            "your",
            "his",
            "her",
            "our",
            "their",
        }

    if phrase in {"sort of", "kind of"}:
        return before not in {"a", "an", "the", "this", "that", "these", "those", "some", "any"}

    return False


def _last_word(text: str) -> str | None:
    matches = list(WORD_RE.finditer(text))
    if not matches:
        return None
    return matches[-1].group(0)


def _first_word(text: str) -> str | None:
    match = WORD_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _normalize_filler_spacing(text: str) -> str:
    out = re.sub(r"\s+([,.!?;:])", r"\1", text)
    out = re.sub(r"[ \t\f\v]+", " ", out)
    out = re.sub(r"[ \t]*\n[ \t]*", "\n", out)
    return out.strip(" ,")


def remove_repetitions(text: str) -> str:
    if not text:
        return text
    if "\n" in text:
        parts = re.split(r"(\n+)", text)
        return "".join(part if part.startswith("\n") else remove_repetitions(part) for part in parts)

    words = text.split()
    if len(words) <= 1:
        return text

    cleaned_words = [words[0]]
    for i in range(1, len(words)):
        if words[i].lower() != words[i - 1].lower():
            cleaned_words.append(words[i])

    final_text = " ".join(cleaned_words)

    for phrase_len in [3, 2]:
        words = final_text.split()
        if len(words) < phrase_len * 2:
            continue
        cleaned: List[str] = []
        i = 0
        while i < len(words):
            if i + phrase_len * 2 <= len(words):
                phrase1 = " ".join(words[i : i + phrase_len])
                phrase2 = " ".join(words[i + phrase_len : i + phrase_len * 2])
                if phrase1.lower() == phrase2.lower():
                    cleaned.extend(words[i : i + phrase_len])
                    i += phrase_len * 2
                    continue
            cleaned.append(words[i])
            i += 1
        final_text = " ".join(cleaned)

    return final_text


def basic_grammar(text: str) -> str:
    if not text:
        return text
    text = text.strip()
    if not text:
        return text

    text = re.sub(
        r"(^|[.!?]\s+|\n+[ \t]*)([([“]*)([a-z][\w'’]*)",
        lambda match: match[1] + match[2] + _capitalize_item(match[3]),
        text,
    )
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"[ \t\f\v]+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])([a-zA-Z])", r"\1 \2", text)

    corrections = {
        r"\bi\b": "I",
        r"\bim\b": "I'm",
        r"\bive\b": "I've",
        r"\bill\b": "I'll",
        r"\bwont\b": "won't",
        r"\bcant\b": "can't",
        r"\bdont\b": "don't",
        r"\bisnt\b": "isn't",
        r"\barent\b": "aren't",
        r"\bwasnt\b": "wasn't",
        r"\bwerent\b": "weren't",
        r"\bhasnt\b": "hasn't",
        r"\bhavent\b": "haven't",
        r"\bhadnt\b": "hadn't",
        r"\bwouldnt\b": "wouldn't",
        r"\bcouldnt\b": "couldn't",
        r"\bshouldnt\b": "shouldn't",
    }

    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")


def apply_self_corrections(text: str) -> str:
    reserved = re.findall(r"__(?:GLOSSARY|SPAN)_\d+__", text)
    protected, mapping = protect_spans(text, protected_tokens=reserved)
    return restore_spans(repair_backtracks(protected), mapping)


def maybe_format_list(text: str, *, capitalize_items: bool = True) -> str:
    if not text:
        return text
    lowered = text.lower()
    bullet_pattern = r"\b(?:new\s+)?bullet(?:\s+point)?\b"
    bullet = re.search(bullet_pattern, lowered, flags=re.IGNORECASE)
    if bullet:
        prefix = text[:bullet.start()].strip()
        if not prefix or prefix.endswith(":"):
            parts = re.split(bullet_pattern, text[bullet.start():], flags=re.IGNORECASE)
            items = [p.strip(" ,.-\n\t") for p in parts if p.strip(" ,.-\n\t")]
            if items:
                header = prefix + "\n" if prefix else ""
                return header + "\n".join(f"- {_capitalize_item(i) if capitalize_items else i}" for i in items)

    numbered = _format_numbered_list(text, capitalize_items=capitalize_items)
    return numbered if numbered is not None else text


NUMBER_MARKERS = {
    "1": 1,
    "one": 1,
    "first": 1,
    "2": 2,
    "two": 2,
    "second": 2,
    "3": 3,
    "three": 3,
    "third": 3,
    "4": 4,
    "four": 4,
    "fourth": 4,
    "5": 5,
    "five": 5,
    "fifth": 5,
    "6": 6,
    "six": 6,
    "sixth": 6,
    "7": 7,
    "seven": 7,
    "seventh": 7,
    "8": 8,
    "eight": 8,
    "eighth": 8,
    "9": 9,
    "nine": 9,
    "ninth": 9,
    "10": 10,
    "ten": 10,
    "tenth": 10,
}

NUMBER_MARKER_RE = re.compile(
    r"(?<!\w)(?:number\s+)?("
    + "|".join(sorted((re.escape(marker) for marker in NUMBER_MARKERS), key=len, reverse=True))
    + r")\.?(?!\w)",
    flags=re.IGNORECASE,
)


def _format_numbered_list(text: str, *, capitalize_items: bool = True) -> str | None:
    matches = list(NUMBER_MARKER_RE.finditer(text))
    if not matches:
        return None

    first = matches[0]
    explicit = first[0].casefold().startswith("number ")
    ordinals = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"}
    if explicit:
        markers = NUMBER_MARKERS
        prefix = r"number\s+"
    else:
        prefix = ""
        token = first[1].casefold()
        markers = {key: value for key, value in NUMBER_MARKERS.items()
                   if (key in ordinals if token in ordinals else key.isdecimal() if token.isdecimal()
                       else not key.isdecimal() and key not in ordinals)}
    pattern = re.compile(r"(?<!\w)" + prefix + "(" + "|".join(sorted(markers, key=len, reverse=True))
                         + r")\.?(?!\w)", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if len(matches) < 2 and not explicit and not first[0].endswith("."):
        return None

    first_prefix = text[: matches[0].start()].strip(" ,:-\n\t")
    if first_prefix:
        return None

    numbers = [_marker_number(match) for match in matches]
    if numbers[0] != 1:
        return None
    if any(current != previous + 1 for previous, current in zip(numbers, numbers[1:])):
        return None

    items: List[str] = []
    for index, match in enumerate(matches):
        item_start = match.end()
        item_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item = text[item_start:item_end].strip(" ,.-:\n\t")
        if not item:
            return None
        items.append(item)

    return "\n".join(f"{number}. {_capitalize_item(item) if capitalize_items else item}" for number, item in zip(numbers, items))


def _marker_number(match: re.Match[str]) -> int:
    return NUMBER_MARKERS[match.group(1).lower()]


def _capitalize_item(item: str) -> str:
    if not item:
        return item
    initial = item[0].upper()
    first = item.split(maxsplit=1)[0]
    if len(initial) != 1 or any(char.isupper() for char in first[1:]):
        return item
    return initial + item[1:]


def normalize_punctuation(text: str, final_period: bool) -> str:
    if not text:
        return text
    out = re.sub(r"[ \t\f\v]+([,.!?;:])", r"\1", text)
    out = re.sub(r"([,.!?;:])([A-Za-z])", r"\1 \2", out)
    out = re.sub(r"[ \t\f\v]+", " ", out)
    out = re.sub(r"[ \t]*\n[ \t]*", "\n", out).strip()
    if final_period and out and not re.search(r"[.!?]\s*$", out):
        out = out + "."
    return out


def apply_rules(text: str, options: RuleOptions) -> str:
    out = text
    if options.normalize_whitespace:
        out = normalize_whitespace(out)
    addresses = {}
    if options.normalize_itn:
        out = normalize_addresses(out)
        out, addresses = protect_spans(out, entities_only=True)
    if options.remove_fillers:
        out = remove_fillers(out, aggressive=options.aggressive_fillers)
    structured_list = False
    if options.enable_list_formatting:
        formatted = maybe_format_list(out, capitalize_items=options.normalize_capitalization)
        structured_list, out = formatted != out, formatted
    entities = {}
    if options.normalize_itn:
        out = normalize_itn(out, intensity=options.intensity, style=options.number_style)
        out, entities = protect_spans(out, entities_only=True)
    if options.convert_spoken_punctuation or options.convert_spoken_newlines:
        out = convert_spoken_punctuation(
            out, convert_newlines=options.convert_spoken_newlines,
            convert_punctuation=options.convert_spoken_punctuation)
    if options.normalize_capitalization:
        out = re.sub(r"(^|[.!?]\s+|\n+[ \t]*)([([“]+)([a-z][\w'’]*)",
                     lambda match: match[1] + match[2] + _capitalize_item(match[3]), out)
    reserved = re.findall(r"__(?:GLOSSARY|SPAN)_\d+__", out)
    out, generated_spans = protect_spans(out, protected_tokens=reserved)
    if options.handle_self_corrections:
        out = apply_self_corrections(out)
    if options.remove_repetitions:
        out = remove_repetitions(out)
    if options.normalize_capitalization:
        out = basic_grammar(out)
    if options.normalize_punctuation:
        out = normalize_punctuation(out, final_period=options.final_period and not structured_list)
    if options.normalize_whitespace:
        out = normalize_whitespace(out)
    out = restore_spans(out, generated_spans)
    out = restore_spans(out, entities)
    return restore_spans(out, addresses)

