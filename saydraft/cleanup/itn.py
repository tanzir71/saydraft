"""Deterministic English spoken details; ambiguous numeric phrases stay literal."""

from __future__ import annotations

import re

from saydraft.text_entities import BARE_DOMAIN_PATTERN, EMAIL_PATTERN
SMALL = dict(zip(("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                  "fifteen sixteen seventeen eighteen nineteen").split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
SCALES = {"thousand": 1000, "lakh": 100000, "million": 1000000, "crore": 10000000,
          "billion": 1000000000, "trillion": 1000000000000}
ORDINALS = dict(zip(("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
                    "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth").split(),
                   list(SMALL)[1:]))
ORDINALS.update(dict(zip("twentieth thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth".split(), TENS)))
ORDINALS.update(hundredth="hundred", thousandth="thousand", millionth="million", billionth="billion", trillionth="trillion")
DIGITS = {word: str(value) for word, value in SMALL.items() if value < 10} | {"oh": "0"}
_WORDS = sorted((*SMALL, *TENS, *SCALES, *ORDINALS, "hundred", "oh"), key=len, reverse=True)
_WORD = "(?:" + "|".join(_WORDS) + ")"
_ARTICLE_SCALE = "(?:" + "|".join(("hundred", *SCALES)) + r")(?!\w)"
_CARDINAL = rf"(?:a[ ]+(?={_ARTICLE_SCALE}))?(?:{_WORD})(?:[ -]+(?:and[ ]+)?{_WORD})*"
_PART = rf"(?:\d+|{_CARDINAL})"
_VALUE = rf"(?:(?:minus|negative)[ ]+)?{_PART}(?:[ ]+point[ ]+{_PART})?"
_NUMBER = re.compile(rf"(?<!\w){_VALUE}(?!\w)", re.IGNORECASE)
_MONTH = ("january february march april may june july august september october november december "
          "jan feb mar apr jun jul aug sep sept oct nov dec").split()
_MONTH_RE = "(?:" + "|".join(sorted(_MONTH, key=len, reverse=True)) + ")"
_DATE = re.compile(rf"(?<!\w)({_MONTH_RE})[ ]+({_PART}(?:,[ ]*{_PART})?)(?!\w)", re.IGNORECASE)
_REVERSE_DATE = re.compile(rf"(?<!\w)(?:the[ ]+)?({_PART})[ ]+of[ ]+({_MONTH_RE})(?:[ ]+({_PART}))?(?!\w)", re.IGNORECASE)
_TIME = re.compile(rf"(?<!\w)({_PART})[ ]+([ap])[. ]*m(?!\w)", re.IGNORECASE)
_CURRENCY = re.compile(rf"(?<!\w)({_VALUE})[ ]+(dollars?|euros?|taka|pounds?(?:[ ]+sterling)?)"
                       rf"(?:[ ]+and[ ]+({_PART})[ ]+cents?)?(?!\w)", re.IGNORECASE)
_PERCENT = re.compile(rf"(?<!\w)({_VALUE})[ ]+(?:percent|per cent)(?!\w)", re.IGNORECASE)
_VERSION = re.compile(rf"(?<!\w)(v|version)[ ]+({_PART}(?:[ ]+point[ ]+{_PART})+)(?!\w)", re.IGNORECASE)
_DIGIT_WORD = "(?:" + "|".join((*DIGITS, "double", "triple")) + ")"
_PHONE = re.compile(rf"(?<!\w)(call|phone|telephone|number|tel)[ ]+((?:plus[ ]+)?{_DIGIT_WORD}"
                    rf"(?:[ ]+{_DIGIT_WORD}){{0,31}})(?!\w)", re.IGNORECASE)
_LABEL = r"[a-z0-9]+(?:[ ]+(?:hyphen|dash)[ ]+[a-z0-9]+)*"
_DOMAIN = rf"{_LABEL}(?:[ ]+dot[ ]+{_LABEL})+"
_LOCAL = r"[a-z0-9]+(?:[ ]+(?:dot|underscore|plus|hyphen|dash)[ ]+[a-z0-9]+)*"
_EMAIL = re.compile(rf"(?<!\w)({_LOCAL})[ ]+at[ ]+({_DOMAIN})(?!\w)", re.IGNORECASE)
_URL = re.compile(rf"(?<!\w)((?:https?|http s)[ ]*(?:colon|:)[ ]*slash[ ]+slash[ ]+)?({_DOMAIN})"
                  rf"((?:[ ]+slash[ ]+{_LABEL})*)(?!\w)", re.IGNORECASE)
_TLDS = frozenset("com org net io dev app ai co uk edu gov info me online tech xyz".split())
_ENTITIES = re.compile(r"```[\s\S]*?```|`[^`]*`|\"[^\"\n]*\"|“[^”\n]*”|"
    r"https?://[^\s<>\"'\])]+|__(?:SPAN|GLOSSARY)_\d+__|⟦T\d+⟧|"
    + EMAIL_PATTERN + "|" + BARE_DOMAIN_PATTERN, re.IGNORECASE)


def _under_hundred(words):
    if len(words) == 1:
        return SMALL.get(words[0], TENS.get(words[0]))
    if len(words) == 2 and words[0] in TENS and words[1] in SMALL and 0 < SMALL[words[1]] < 10:
        return TENS[words[0]] + SMALL[words[1]]
    return None


def _under_thousand(words):
    if "hundred" not in words:
        return _under_hundred(words)
    index = words.index("hundred")
    if index not in (0, 1) or words.count("hundred") != 1:
        return None
    multiplier = 1 if index == 0 else SMALL.get(words[0], 0)
    if not 1 <= multiplier <= 9:
        return None
    rest = words[index + 1:]
    if rest and rest[0] == "and":
        if len(rest) == 1:
            return None
        rest = rest[1:]
    tail = _under_hundred(rest) if rest else 0
    return None if tail is None else multiplier * 100 + tail


def parse_cardinal(phrase):
    """Parse a whole well-formed phrase, never sum unrelated adjacent numbers."""
    phrase = phrase.strip().casefold()
    if phrase.isdecimal():
        return int(phrase) if len(phrase) <= 18 else None
    words = phrase.replace("-", " ").split()
    if len(words) >= 2 and words[0] == "a" and words[1] in {"hundred", *SCALES}:
        words[0] = "one"
    if not words or len(words) > 30:
        return None
    total, start, previous = 0, 0, float("inf")
    for index, word in enumerate(words):
        if word not in SCALES:
            continue
        scale = SCALES[word]
        group = words[start:index]
        if start and group and group[0] == "and":
            group = group[1:]
        if start and not group:
            return None
        value = _under_thousand(group) if group else 1
        if scale >= previous or value is None or value == 0:
            return None
        total += value * scale
        previous, start = scale, index + 1
    rest = words[start:]
    if start and rest and rest[0] == "and":
        if len(rest) == 1:
            return None
        rest = rest[1:]
    tail = _under_thousand(rest) if rest else 0
    return None if tail is None else total + tail


def _ordinal(phrase):
    words = phrase.casefold().replace("-", " ").split()
    if not words or words[-1] not in ORDINALS:
        return None
    words[-1] = ORDINALS[words[-1]]
    value = parse_cardinal(" ".join(words))
    if value is None:
        return None
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return value, f"{value}{suffix}"


def _value(phrase):
    words = phrase.casefold().split()
    sign = ""
    if words and words[0] in ("minus", "negative"):
        sign, words = "-", words[1:]
    if "point" not in words:
        number = parse_cardinal(" ".join(words))
        return None if number is None else sign + str(number)
    if words.count("point") != 1:
        return None
    index = words.index("point")
    integer = parse_cardinal(" ".join(words[:index]))
    fraction = words[index + 1:]
    if integer is None or not fraction:
        return None
    if all(word in DIGITS for word in fraction):
        digits = "".join(DIGITS[word] for word in fraction)
    else:
        number = parse_cardinal(" ".join(fraction))
        if number is None:
            return None
        digits = str(number)
    return sign + str(integer) + "." + digits


def _year(words):
    value = parse_cardinal(" ".join(words))
    if value is not None and 1000 <= value <= 9999:
        return value
    for index in range(1, len(words)):
        first, last = parse_cardinal(" ".join(words[:index])), parse_cardinal(" ".join(words[index:]))
        if first is not None and last is not None and 19 <= first <= 21 and 0 <= last <= 99:
            return first * 100 + last
    return None


def _domain(value):
    value = re.sub(r"[ ]+(?:hyphen|dash)[ ]+", "-", value, flags=re.IGNORECASE)
    return re.sub(r"[ ]+dot[ ]+", ".", value, flags=re.IGNORECASE)


def _normalize(text, *, intensity=3, style="prose", addresses_only=False):
    if type(intensity) is not int or not 1 <= intensity <= 4 or style not in ("prose", "compact"):
        raise ValueError("Unsupported ITN intensity or style")
    prefix = "__ITN_"
    while prefix in text:
        prefix = "_" + prefix
    saved = {}

    def store(value):
        token = f"{prefix}{len(saved)}__"
        saved[token] = value
        return token

    def restore(value):
        return re.sub(re.escape(prefix) + r"\d+__", lambda match: saved[match[0]], value)

    out = _ENTITIES.sub(lambda match: store(match[0]), text)

    def email(match):
        local, domain = match[1], _domain(match[2])
        explicit = re.search(r"\b(?:email|e-mail|address|contact)[ ]+$", out[:match.start()], re.IGNORECASE)
        if not explicit and local.casefold() in {"look", "meet", "arrive", "work", "stay", "go", "wait", "be", "is", "are",
                                                "stop", "visit", "browse", "check", "start", "starts", "continue", "works"}:
            return match[0]
        if domain.rsplit(".", 1)[-1].casefold() not in _TLDS:
            return match[0]
        for word, symbol in (("dot", "."), ("underscore", "_"), ("plus", "+"), ("hyphen", "-"), ("dash", "-")):
            local = re.sub(rf"[ ]+{word}[ ]+", lambda match: symbol, local, flags=re.IGNORECASE)
        return store(local + "@" + domain)

    out = _EMAIL.sub(email, out)

    def url(match):
        domain = _domain(match[2])
        if domain.rsplit(".", 1)[-1].casefold() not in _TLDS:
            return match[0]
        scheme = ""
        if match[1]:
            scheme = "https://" if match[1].casefold().startswith(("https", "http s")) else "http://"
        path = re.sub(r"[ ]+slash[ ]+", "/", match[3], flags=re.IGNORECASE)
        return store(scheme + domain + _domain(path))

    out = _URL.sub(url, out)
    if addresses_only:
        return restore(out)

    def phone(match):
        words = match[2].casefold().split()
        digits, index = "", 0
        if words[0] == "plus":
            digits, index = "+", 1
        while index < len(words):
            repeats = {"double": 2, "triple": 3}.get(words[index], 1)
            if repeats > 1:
                index += 1
            if index >= len(words) or words[index] not in DIGITS:
                return store(match[0])
            digits += DIGITS[words[index]] * repeats
            index += 1
        if not 1 <= len(digits.lstrip("+")) <= 32:
            return store(match[0])
        return match[1] + " " + store(digits)

    out = _PHONE.sub(phone, out)

    def version(match):
        parts = [parse_cardinal(part) for part in re.split(r"[ ]+point[ ]+", match[2], flags=re.IGNORECASE)]
        if any(part is None for part in parts):
            return match[0]
        label = "v" if match[1].casefold() == "v" else match[1] + " "
        return store(label + ".".join(map(str, parts)))

    out = _VERSION.sub(version, out)

    def time(match):
        words = match[1].casefold().split()
        for index in range(1, len(words) + 1):
            hour = parse_cardinal(" ".join(words[:index]))
            tail = words[index:]
            minute = parse_cardinal(" ".join(tail)) if tail else None
            if tail and all(word in DIGITS for word in tail):
                minute = int("".join(DIGITS[word] for word in tail))
            if hour is not None and 1 <= hour <= 12 and (not tail or minute is not None and 0 <= minute <= 59):
                value = str(hour) + (f":{minute:02}" if tail else "") + " " + match[2].upper() + "M"
                return store(value)
        return match[0]

    out = _TIME.sub(time, out)

    def currency(match):
        amount, unit = _value(match[1]), match[2].casefold()
        if amount is None:
            return match[0]
        if unit in ("pound", "pounds") and not re.search(
                r"\b(?:pay|paid|cost|costs|price|total|invoice|charge|owe|worth)\b", out[max(0, match.start() - 35):match.start()], re.IGNORECASE):
            return match[0]
        if unit in ("pound", "pounds") and re.search(r"\b(?:weigh|weighs|weight|bag|bags)\b",
                out[max(0, match.start() - 35):match.start()], re.IGNORECASE):
            return match[0]
        if match[3]:
            cents = parse_cardinal(match[3])
            if cents is None or not 0 <= cents <= 99 or "." in amount:
                return match[0]
            amount += f".{cents:02}"
        if "." in amount:
            whole, fraction = amount.split(".")
            amount = whole + "." + fraction.ljust(2, "0")
        symbol = "$" if unit.startswith("dollar") else "€" if unit.startswith("euro") else "৳" if unit == "taka" else "£"
        sign = "-" if amount.startswith("-") else ""
        return store(sign + symbol + amount.lstrip("-"))

    out = _CURRENCY.sub(currency, out)
    out = _PERCENT.sub(lambda match: store(value + "%") if (value := _value(match[1])) is not None else match[0], out)

    def date(match, *, reverse=False):
        month, phrase = (match[2], match[1]) if reverse else (match[1], match[2])
        words = phrase.casefold().replace(",", " ").split()
        for index in range(len(words), 0, -1):
            ordinal = _ordinal(" ".join(words[:index]))
            day = ordinal[0] if ordinal else parse_cardinal(" ".join(words[:index]))
            year = _year(words[index:]) if index < len(words) else None
            if reverse and match[3]:
                year = _year(match[3].casefold().split())
                if year is None:
                    return match[0]
            if day is None or not 1 <= day <= 31 or index < len(words) and year is None:
                continue
            following = out[match.end():].lstrip().split(" ", 1)[0].casefold().rstrip(".,!?")
            if not reverse and month.casefold() in ("march", "may"):
                date_cue = re.search(r"\b(?:on|by|for|due|deadline|meeting|meet|date|dated|since|until|before|after)[ ]+$",
                                     out[:match.start()], re.IGNORECASE)
                if (following in {"block", "blocks", "step", "steps", "mile", "miles", "ask", "attend", "say"}
                        or month.islower() and following and not date_cue):
                    return store(match[0])
            value = f"{day} {month.capitalize()}" if reverse else f"{month.capitalize()} {day}"
            if year is not None:
                value += f", {year}"
            return store(value)
        return match[0]

    out = _REVERSE_DATE.sub(lambda match: date(match, reverse=True), out)
    out = _DATE.sub(date, out)

    def number(match):
        if match[0].isdecimal():
            return match[0]  # Existing typed digits/leading zeroes are already authoritative.
        words = match[0].casefold().split()
        if len(words) == 2 and words[0] in SMALL and words[1] == "second":
            return match[0] if SMALL[words[0]] < 10 and intensity < 3 and style == "prose" else store(
                str(SMALL[words[0]]) + " second")
        ordinal = _ordinal(match[0])
        if ordinal and re.search(r"\b(?:a|per|each|every)[ ]+$", out[:match.start()], re.IGNORECASE):
            return match[0]
        if match[0].casefold() in ("second", "third") and re.search(
                r"\b(?:a|per|each|every|one|1)[ ]+$", out[:match.start()], re.IGNORECASE):
            return match[0]  # A second / a third are units or fractions, not ordinals.
        value = str(ordinal[0]) if ordinal else _value(match[0])
        if value is None:
            return match[0]
        if "." not in value and not value.startswith("-") and int(value) < 10 and intensity < 3 and style == "prose":
            return match[0]
        return store(ordinal[1] if ordinal else value)

    out = _NUMBER.sub(number, out)
    return restore(out)


def normalize_itn(text, *, intensity=3, style="prose"):
    return _normalize(text, intensity=intensity, style=style)


def normalize_addresses(text):
    """Resolve address-shaped phrases before filler removal can consume a label."""
    return _normalize(text, addresses_only=True)
