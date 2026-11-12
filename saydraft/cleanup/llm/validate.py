"""Conservative deterministic checks before a cleanup candidate can be inserted.

These guards are fallbacks, not a proof of semantic equivalence. Rejection keeps
the already available rules text; no input is silently repaired by the validator.
"""

from __future__ import annotations

import re
import unicodedata as ud
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from saydraft.text_boundaries import whole_word_match
from saydraft.text_entities import BARE_DOMAIN_PATTERN, EMAIL
TOKENS = re.compile(r"__(?:GLOSSARY|SPAN)_\d+__|⟦T\d+⟧")
CODE = re.compile(r"```[\s\S]*?```|`[^`]*`|\"[^\"\n]*\"|“[^”\n]*”")
URLS = re.compile(r"https?://[^\s<>\"'\])]+|" + BARE_DOMAIN_PATTERN, re.IGNORECASE)
EMAILS = EMAIL
NUMBER = r"(?:[+−-]\s*)?\d+(?:[.,\u066b\u066c]\d+)*"
AMOUNTS = re.compile(rf"(?:[+−-]\s*)?[$€£¥₹৳]\s*{NUMBER}|{NUMBER}\s*(?:%|٪|(?:USD|EUR|GBP|BDT|dollars?|euros?|pounds?|taka)\b)",
                     re.IGNORECASE)
MONTH = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
         r"sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|"
         r"জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর|"
         r"يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر")
DATES = re.compile(rf"\d{{1,4}}[/-]\d{{1,2}}[/-]\d{{1,4}}|"
                   rf"\d{{1,2}}\s+(?:{MONTH})(?:\s+\d{{2,4}})?|"
                   rf"(?:{MONTH})\s+\d{{1,2}}(?:,?\s+\d{{2,4}})?", re.IGNORECASE)
TIMES = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:[ap]\.?m\.?|UTC|GMT))?|"
                   r"\d{1,2}\s*[ap]\.?m\.?", re.IGNORECASE)
NEGATIONS = frozenset(("no", "not", "never", "without", "cannot", "can't", "don't", "doesn't", "didn't",
    "won't", "wouldn't", "shouldn't", "couldn't", "isn't", "aren't", "wasn't", "weren't", "haven't", "hasn't",
    "না", "নেই", "নয়", "لا", "ليس", "لم", "لن", "بدون"))
PROFANITY = frozenset(("fuck", "fucking", "fucked", "fucker", "motherfucker", "shit", "shitty", "bullshit",
    "damn", "damned", "bitch", "bastard", "asshole", "crap", "শালা", "বাল", "চোদা", "খানকি",
    "خرا", "كس", "شرموطة", "تباً", "اللعنة"))
NUMBER_WORDS = frozenset(("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
    "hundred thousand million billion trillion first second third fourth fifth sixth seventh eighth ninth tenth once twice "
    "এক দুই তিন চার পাঁচ ছয় সাত আট নয় দশ শত হাজার লাখ কোটি "
    "واحد اثنان اثنين ثلاثة أربعة خمسة ستة سبعة ثمانية تسعة عشرة مئة مائة ألف مليون مليار").split())
DATE_WORDS = frozenset(("january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep oct nov dec monday tuesday wednesday thursday friday saturday sunday "
    "today tomorrow yesterday tonight "
    "জানুয়ারি ফেব্রুয়ারি মার্চ এপ্রিল মে জুন জুলাই আগস্ট সেপ্টেম্বর অক্টোবর নভেম্বর ডিসেম্বর "
    "আজ কাল গতকাল আগামীকাল "
    "يناير فبراير مارس أبريل مايو يونيو يوليو أغسطس سبتمبر أكتوبر نوفمبر ديسمبر اليوم غدًا غدا أمس البارحة").split())
AMOUNT_WORDS = frozenset(("dollar dollars euro euros pound pounds taka percent percentage "
    "USD EUR GBP BDT টাকা শতাংশ دولار يورو جنيه").casefold().split())
STOPWORDS = frozenset("a an the is are was were be been being am i you he she it we they my your his her our their "
                     "this that these those to of for from in on at as by and or but so with do does did "
                     "what where when who how please".split())
ANSWER_PREFIXES = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"^(?:sure|certainly|of course)\b", r"^here(?:'s| is| are)\b", r"^the answer (?:is|to)\b",
    r"^as an? (?:ai|assistant|language model)\b", r"^i (?:can|cannot|can't|am unable to)\b",
    r"^(?:assistant|system|answer|translation|cleaned (?:text|transcript))\s*:",
    r'^\{\s*"(?:text|cleaned_text)"\s*:',
))
MARKUP = re.compile(r"</?(?:think|analysis|out|transcript|assistant|system)\b[^>]*>", re.IGNORECASE)
MAX_VALIDATION_CHARS = 64000


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str


def _bare(text):
    return TOKENS.sub(" ", text or "")


def extract_numbers(text):
    return [re.sub(r"\s+", "", value) for value in re.findall(NUMBER, _bare(text))]


def extract_urls(text):
    return [match[0].rstrip(".,!?:;") for match in URLS.finditer(text or "")]


def extract_words(text):
    """Keep Unicode combining marks within their word, including Bengali/Arabic."""
    words, current = [], []
    text = ud.normalize("NFC", _bare(text)).replace("’", "'")
    for index, char in enumerate(text):
        letter = ud.category(char)[0] in "LM"
        apostrophe = char == "'" and current and index + 1 < len(text) and ud.category(text[index + 1])[0] in "LM"
        if letter or apostrophe:
            current.append(char)
        elif current:
            words.append("".join(current))
            current.clear()
    if current:
        words.append("".join(current))
    return words


def has_same_placeholders(a, b):
    return TOKENS.findall(a or "") == TOKENS.findall(b or "")


def _normalized_matches(pattern, text):
    return [re.sub(r"\s+", " ", match[0]).casefold() for match in pattern.finditer(text)]


def _scripts(text):
    counts = Counter()
    text = EMAILS.sub(" ", URLS.sub(" ", CODE.sub(" ", _bare(text))))
    for char in text:
        if ud.category(char).startswith("L"):
            script = ud.name(char, "UNKNOWN").split(" ", 1)[0]
            counts[script] += 1
    return counts


def _language_changed(a, b):
    source, candidate = _scripts(a), _scripts(b)
    if sum(source.values()) < 3:
        return False
    dominant, count = source.most_common(1)[0]
    if count / source.total() < 0.6:
        return False  # Mixed scripts still have the Unicode content-overlap guard.
    return not candidate or candidate[dominant] / candidate.total() < 0.7


def _coverage(source, candidate):
    common = (source & candidate).total()
    return common / max(1, source.total()), common / max(1, candidate.total())


def validate_llm_output(rule_text, llm_text, mode="balanced", *, glossary=(), intensity=None, translate=False):
    if not isinstance(rule_text, str) or not isinstance(llm_text, str) or not llm_text.strip():
        return ValidationResult(False, "empty")
    a, b = rule_text.strip(), llm_text.strip()
    level = intensity if intensity is not None else (4 if mode == "aggressive" else 3)
    if type(level) is not int or not 1 <= level <= 4:
        return ValidationResult(False, "invalid_intensity")
    if not a:
        return ValidationResult(False, "empty_source")
    if max(len(a), len(b)) > MAX_VALIDATION_CHARS:
        return ValidationResult(False, "too_large")
    if a == b:
        return ValidationResult(True, "ok")
    if not has_same_placeholders(a, b):
        return ValidationResult(False, "glossary_changed")
    if CODE.findall(a) != CODE.findall(b):
        return ValidationResult(False, "code_changed")
    if extract_urls(a) != extract_urls(b):
        return ValidationResult(False, "urls_changed")
    if EMAILS.findall(a) != EMAILS.findall(b):
        return ValidationResult(False, "emails_changed")
    if extract_numbers(a) != extract_numbers(b):
        return ValidationResult(False, "numbers_changed")
    if _normalized_matches(AMOUNTS, a) != _normalized_matches(AMOUNTS, b):
        return ValidationResult(False, "amounts_changed")
    if _normalized_matches(DATES, a) != _normalized_matches(DATES, b):
        return ValidationResult(False, "dates_changed")
    if _normalized_matches(TIMES, a) != _normalized_matches(TIMES, b):
        return ValidationResult(False, "times_changed")
    for term in glossary:
        if isinstance(term, str) and term.strip():
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            source_count = sum(whole_word_match(a, match) for match in pattern.finditer(a))
            candidate_count = sum(whole_word_match(b, match) for match in pattern.finditer(b))
            if source_count != candidate_count:
                return ValidationResult(False, "glossary_changed")
    tokens_a = [word.casefold() for word in extract_words(a)]
    tokens_b = [word.casefold() for word in extract_words(b)]
    words_a, words_b = Counter(tokens_a), Counter(tokens_b)
    for terms, reason in ((NUMBER_WORDS, "number_words_changed"), (DATE_WORDS, "dates_changed"),
                          (AMOUNT_WORDS, "amounts_changed")):
        sequence_a = [word for word in tokens_a if word in terms]
        sequence_b = [word for word in tokens_b if word in terms]
        if sequence_a != sequence_b:
            return ValidationResult(False, reason)
    for terms, reason in ((NEGATIONS, "negation_changed"), (PROFANITY, "profanity_changed")):
        if any(words_a[term] != words_b[term] for term in terms):
            return ValidationResult(False, reason)
    if Counter(char for char in a if ud.category(char) in ("Cf", "Cc") and not char.isspace()) != Counter(
            char for char in b if ud.category(char) in ("Cf", "Cc") and not char.isspace()):
        return ValidationResult(False, "controls_changed")
    if Counter(MARKUP.findall(a)) != Counter(MARKUP.findall(b)):
        return ValidationResult(False, "wrapper_output")
    if any(pattern.search(b) and not pattern.search(a) for pattern in ANSWER_PREFIXES):
        return ValidationResult(False, "answer_output")
    if not translate and _language_changed(a, b):
        return ValidationResult(False, "language_changed")
    lower = {1: 0.8, 2: 0.7, 3: 0.6, 4: 0.5}[level]
    upper = {1: 1.15, 2: 1.2, 3: 1.3, 4: 1.3}[level]
    if not lower <= len(b) / len(a) <= upper:
        return ValidationResult(False, "length_ratio")
    if not translate:
        coverage, precision = _coverage(words_a, words_b)
        if (words_a or words_b) and (coverage < (0.65 if level == 4 else 0.78) or precision < (0.8 if level == 4 else 0.85)):
            return ValidationResult(False, "content_changed")
        content_a = Counter({word: count for word, count in words_a.items() if word not in STOPWORDS})
        content_b = Counter({word: count for word, count in words_b.items() if word not in STOPWORDS})
        coverage, precision = _coverage(content_a, content_b)
        if content_a and (coverage < (0.65 if level == 4 else 0.75) or precision < 0.85):
            return ValidationResult(False, "answer_or_content_changed")
        similarity = SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
        if similarity < (0.65 if level == 4 else 0.75):
            return ValidationResult(False, "too_different")
    return ValidationResult(True, "ok")
