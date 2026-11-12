"""Text-only backtracks with bounded phrase alignment and original slices."""

from __future__ import annotations

import re

from saydraft.text_boundaries import whole_word_match

_TOKEN = re.compile(r"__(?:GLOSSARY|SPAN)_\d+__|[+−-]?[$€£¥₹৳]?\d+(?:[.,:]\d+)*[%٪]?|[^\s,;:!?！？؟؛…。।۔—–.]+")
_MARKER = re.compile(r"(?<!\w)(?:scratch[ \t,]+that|never[ \t,]+mind|no[ \t,]+(?:actually|sorry|wait)"
                     r"|i[ \t,]+mean|actually|sorry)(?!\w)", re.IGNORECASE)
_HARD = re.compile(r"(?<!\.)\.(?!\.)|[!?！？؟؛;:\n\r。।۔]")
_PAUSE = re.compile(r"\.{2,}|[…—–]")
_WINDOW = 64
_SUBJECT = set("i we you he she it they this that".split())
_FUSED_SUBJECT = set("i'm i'll i've i'd we're we'll we've we'd you're you'll you've you'd he's he'll he'd"
                     " she's she'll she'd it's it'll they're they'll they've they'd that's".split())
_SUBJECT |= _FUSED_SUBJECT
_AUX = set("am are is was were be been being do does did can could should would will have has had must might"
           " cannot can't couldn't shouldn't wouldn't won't doesn't didn't isn't wasn't aren't weren't don't".split())
_VERBS = set("send tell call bring use make book move turn set change choose pick order buy add put take"
             " meet schedule cancel open close keep write read deliver pay invite email text give get need want".split())
_VERBS |= set("sent told called brought used made booked moved turned changed chose picked ordered bought added"
              " took met scheduled cancelled canceled opened closed kept wrote delivered paid invited emailed gave got".split())
_PREPS = set("to for at on in with from into as of by".split())
_ARTICLES = {"a", "an", "the"}
_SLOTS = _VERBS | _PREPS | {"am", "are", "is", "was", "were", "be"}
_SLOT_OBJECTS = set("priority color colour size status price total amount level deadline date time destination"
                    " recipient name title subject volume".split())
_CONTINUATION = set("after before because when once if while please then".split())
_FALSE_STARTS = set("and but or so because if when while is are was were am be been being appears appeared".split())
_META = set("word words phrase phrases term terms called said say says means meant".split())
_ADVERB_BEFORE = (_SUBJECT | _AUX | _META | set("really not never also still already looks seems feels"
    " i'm im we're they're you're can't cannot don't doesn't didn't won't isn't wasn't aren't weren't".split())
    | {"আমি", "আমরা", "তুমি", "আপনি", "তোমরা", "আপনারা", "সে", "তারা", "أنا", "نحن", "أنت", "هو", "هي", "هم"})
_ADVERB_AFTER = set("agree work works want need like know think believe care support love hate understand"
                    " remember helps matters means happened responds arrives".split()) | _AUX


def _key(token):
    return token[0].strip('"\'“”‘’()[]{}').casefold()


def _left_clause(kept, text):
    start = max(0, len(kept) - _WINDOW)
    for i in range(len(kept) - 1, start, -1):
        if _HARD.search(text[kept[i - 1].end():kept[i].start()]):
            return kept[i:]
    return kept[start:]


def _right_clause(tokens, start, stop, text):
    result = []
    for token in tokens[start:start + _WINDOW]:
        if token.start() >= stop or result and _HARD.search(text[result[-1].end():token.start()]):
            break
        result.append(token)
    return result


def _name_start(left, right):
    if not right[0][0][0].isupper() or _key(right[0]) in _SUBJECT | _ARTICLES | _VERBS:
        return None
    i = len(left)
    while i and left[i - 1][0][0].isupper() and _key(left[i - 1]) not in _SUBJECT | _ARTICLES | _SLOTS:
        i -= 1
    if i == 0 and len(left) > 1:
        return None  # An unknown capitalized clause opener may be a verb.
    return i if i < len(left) else None


def _aligned_cut(left, right):
    a, b = [_key(t) for t in left], [_key(t) for t in right]
    matches = []
    for i in range(len(a)):
        n = 0
        while n < min(8, len(a) - i, len(b)) and a[i + n] == b[n]:
            n += 1
        if n >= 2 or n == 1 and b[0] in _PREPS | _ARTICLES | _VERBS:
            matches.append((n, i))
    if matches:
        return max(matches)[1], True
    name = _name_start(left, right)
    if name is not None:
        return name, False
    # A shared internal frame aligns differently sized replacements: Friday at
    # two -> Monday at three. The right continuation stays outside the deletion.
    for j in range(1, min(4, len(b))):
        if b[j] in _PREPS:
            for i in range(len(a) - 1, j - 1, -1):
                if a[i] == b[j] and len(a) - (i - j) <= 6:
                    return i - j, False
    for i in range(len(a) - 1, -1, -1):
        if a[i] in _SLOTS:
            cut = i + 1
            if a[i] in _VERBS:
                while cut < len(a) and a[cut] in {"it", "them", "me", "us"}:
                    cut += 1
                if a[i] in {"set", "change"}:
                    obj = cut + (cut < len(a) and a[cut] == "the")
                    if obj < len(a) and a[obj] in _SLOT_OBJECTS:
                        cut = obj + 1
            if cut < len(a):
                return cut, False
    n = next((i for i, word in enumerate(b) if i and word in _CONTINUATION), len(b))
    return (len(a) - n, False) if 0 < n <= min(6, len(a)) else (None, False)


def _cut_for_marker(marker, left, right, text, start, end):
    if not left or not right:
        return None
    a, b = [_key(t) for t in left], [_key(t) for t in right]
    if (re.search(r"[\n\r!?！？؟؛;。।۔]", text[left[-1].end():start])
            or _HARD.search(text[end:right[0].start()]) or a[-1] in _META or b[0] in _FALSE_STARTS):
        return None
    if marker == "no wait" and b[0] in {"for", "list", "time"}:
        return None
    if marker == "i mean" and b[0] in {"it", "that", "this", "what", "well", "business", "no"}:
        return None
    if marker == "scratch that" and b[0] in {"itch", "surface", "spot", "mark"}:
        return None
    cut, repeated = _aligned_cut(left, right)
    if marker == "sorry" and (a[-1] in _ADVERB_BEFORE | {"so", "very", "feel", "felt"}
                              or not repeated and b[0] in {"for", "about", "that"} | _SUBJECT):
        return None
    restart = len(b) > 1 and (b[0] in _FUSED_SUBJECT
        or b[0] in _SUBJECT | {"please"} and b[1] in _AUX | _VERBS | _ADVERB_AFTER)
    if marker not in {"actually", "sorry"} and restart:
        return 0
    if marker == "actually" and not repeated and (
            a[-1] in _ADVERB_BEFORE or b[0] in _ADVERB_AFTER | _SUBJECT
            or len(a) > 1 and a[-2] in {"when", "if", "while", "because"}
            or not any(word in _SLOTS for word in a) and _name_start(left, right) is None
               and not any(char.isdigit() for char in left[-1][0])):
        return None
    if a[-1] in _AUX and not repeated:
        return None
    if b[0] in _VERBS and marker not in {"actually", "sorry"} and not repeated:
        return 0
    return cut


def _delete(text, edits):
    merged = []
    for start, end in sorted(edits):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    parts, cursor = [], 0
    for start, end in merged:
        parts.append(text[cursor:start])
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _explicit(text):
    tokens = list(_TOKEN.finditer(text))
    markers = [m for m in _MARKER.finditer(text) if whole_word_match(text, m)]
    kept, edits, cursor = [], [], 0
    for index, match in enumerate(markers):
        while cursor < len(tokens) and tokens[cursor].start() < match.start():
            kept.append(tokens[cursor])
            cursor += 1
        right_start = cursor
        while right_start < len(tokens) and tokens[right_start].start() < match.end():
            right_start += 1
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        left = _left_clause(kept, text)
        right = _right_clause(tokens, right_start, stop, text)
        marker = " ".join(re.findall(r"\w+", match[0].casefold()))
        cut = _cut_for_marker(marker, left, right, text, match.start(), match.end())
        if cut is not None:
            offset = left[cut].start()
            edits.append((offset, right[0].start()))
            while kept and kept[-1].start() >= offset:
                kept.pop()
            cursor = right_start
    return _delete(text, edits)


def _restatements(text):
    tokens, kept, edits = list(_TOKEN.finditer(text)), [], []
    for j, token in enumerate(tokens):
        gap = text[kept[-1].end():token.start()] if kept else ""
        if _PAUSE.search(gap) and not _HARD.search(gap):
            left = _left_clause(kept, text)
            right = _right_clause(tokens, j, len(text), text)
            a, b = [_key(t) for t in left], [_key(t) for t in right]
            for i in range(len(a) - 2, -1, -1):
                n = 0
                while n < min(8, len(a) - i, len(b)) and a[i + n] == b[n]:
                    n += 1
                frame = n >= 2 and b[0] in _PREPS and b[1] in _ARTICLES
                clause = n >= 2 and i == 0 and b[0] in _SUBJECT | {"please"}
                old = a[i + n:]
                if (not (frame or clause) or not old or len(old) > 12 or len(b) <= n
                        or any(word in {"and", "or", "but", "than"} or word.startswith("__") for word in old)):
                    continue
                offset = left[i].start()
                edits.append((offset, token.start()))
                while kept and kept[-1].start() >= offset:
                    kept.pop()
                break
        kept.append(token)
    return _delete(text, edits)


def repair_backtracks(text: str) -> str:
    """Caller masks literal/quoted/code spans; both passes retain source slices."""
    return _restatements(_explicit(text)) if text else text
