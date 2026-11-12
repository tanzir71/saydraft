"""Render explicit spoken code syntax without prose edits or app execution."""

from __future__ import annotations

import re
import unicodedata

from saydraft.text_entities import BARE_DOMAIN_PATTERN, EMAIL_PATTERN
from .itn import normalize_itn

_CASES = {"camel case": "camel", "snake case": "snake", "kebab case": "kebab",
          "pascal case": "pascal", "constant case": "constant"}
_CASES.update({key.replace(" ", ""): value for key, value in tuple(_CASES.items())})
_SYMBOLS = {
    "triple equals": ("===", "binary"), "double equals": ("==", "binary"), "equals equals": ("==", "binary"),
    "not equals": ("!=", "binary"), "greater than or equal": (">=", "binary"),
    "less than or equal": ("<=", "binary"), "greater than": (">", "binary"), "less than": ("<", "binary"),
    "equals": ("=", "binary"), "plus": ("+", "binary"), "minus": ("-", "binary"),
    "asterisk": ("*", "binary"), "star": ("*", "binary"),
    "double pipe": ("||", "binary"), "pipe": ("|", "binary"),
    "double ampersand": ("&&", "binary"), "ampersand": ("&", "binary"),
    "open paren": ("(", "join"), "close paren": (")", "close"),
    "open parenthesis": ("(", "join"), "close parenthesis": (")", "close"),
    "open bracket": ("[", "join"), "close bracket": ("]", "close"),
    "open brace": ("{", "join"), "close brace": ("}", "close"),
    "dot": (".", "join"), "period": (".", "join"), "full stop": (".", "join"),
    "slash": ("/", "join"), "backslash": ("\\", "join"),
    "hyphen": ("-", "join"), "underscore": ("_", "join"),
    "dash dash": ("--", "flag"), "dash": ("-", "flag"),
    "comma": (",", "delimiter"), "colon": (":", "delimiter"), "semicolon": (";", "delimiter"),
    "at sign": ("@", "join"), "hash": ("#", "join"), "dollar sign": ("$", "join"),
    "percent sign": ("%", "close"), "question mark": ("?", "close"), "exclamation mark": ("!", "close"),
    "open quote": ('"', "quote_open"), "close quote": ('"', "close"),
    "open single quote": ("'", "quote_open"), "close single quote": ("'", "close"),
    "new line": ("\n", "newline"), "newline": ("\n", "newline"), "new paragraph": ("\n\n", "newline"),
}
_KEYS = (*_CASES, *_SYMBOLS, "at file", "number")
_COMMAND = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(key) for key in sorted(_KEYS, key=len, reverse=True))
                      + r")(?!\w)", re.IGNORECASE)
_EXPLICIT = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(key) for key in sorted(_KEYS, key=len, reverse=True)
                                               if " " in key) + r")(?!\w)|\bnumber[ \t]+(?![=(){}\[\];:])", re.IGNORECASE)
_TYPED_SYNTAX = re.compile(r"[=(){}\[\];:]")
_DECLARATION = re.compile(r"\b(?:def|class|function|fn|let|const|var|import|return|yield)[ \t]+$", re.IGNORECASE)
_NUMERIC_RHS = re.compile(r"[ \t]+number(?!\w)", re.IGNORECASE)
_HARD_BOUNDARY = re.compile(r"[=+*/().,:;{}\[\]\r\n]")
_COMPONENT = re.compile(r'''[^\s=+*()\[\]{},;:'"<>/\\]+''')
_PATH_JOINS = {"dot": ".", "slash": "/", "backslash": "\\", "hyphen": "-", "dash": "-", "underscore": "_", "colon": ":"}
_SECOND_DASH = re.compile(r"[ \t]+dash(?!\w)", re.IGNORECASE)
_LITERALS = re.compile(r'''```[\s\S]*?```|`[^`]*`|"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|“[^”\n]*”|'''
    r"https?://[^\s<>\"'\])]+|__(?:SPAN|GLOSSARY)_\d+__|⟦T\d+⟧|"
    + EMAIL_PATTERN + "|" + BARE_DOMAIN_PATTERN + r"|(?<!\S)//[^\r\n]*|\#[^\r\n]*", re.IGNORECASE)


def _identifier(value, style, protected_prefix):
    if protected_prefix in value:
        return None
    value = value.strip()
    leading = value[:len(value) - len(value.lstrip("_"))]
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])", " ", value.lstrip("_"))
    words = re.split(r"[\s_-]+", value)
    if not words or not words[0] or not leading and not words[0][0].isalpha() or any(
            not word or any(not char.isalnum() and not unicodedata.category(char).startswith("M") for char in word)
            for word in words):
        return None
    words = [word.lower() for word in words]
    def title(word):
        return word[0].upper() + word[1:]

    if style == "camel":
        return leading + words[0] + "".join(title(word) for word in words[1:])
    if style == "pascal":
        return leading + "".join(title(word) for word in words)
    if style == "constant":
        return leading + "_".join(words).upper()
    return leading + ("_" if style == "snake" else "-").join(words)


def _operand_end(text, start, *, signed=False):
    command = _COMMAND.search(text, start)
    if signed and command and command[0].casefold() == "minus" and not text[start:command.start()].strip():
        command = _COMMAND.search(text, command.end())
    boundary = _HARD_BOUNDARY.search(text, start, command.start() if command else len(text))
    return min(command.start() if command else len(text), boundary.start() if boundary else len(text))


def _path(text, start):
    cursor, pieces, has_component = start, [], False
    while True:
        position = cursor
        while position < len(text) and text[position] in " \t":
            position += 1
        token = _COMPONENT.match(text, position)
        if token is None:
            break
        word = token[0]
        if word.casefold() in _PATH_JOINS:
            # Two spoken dashes introduce a CLI flag, ending a preceding path.
            if word.casefold() == "dash" and _SECOND_DASH.match(text, token.end()):
                break
            pieces.append(_PATH_JOINS[word.casefold()])
            cursor = token.end()
            continue
        if has_component and (not pieces or pieces[-1] not in _PATH_JOINS.values()):
            break
        pieces.append(word)
        has_component, cursor = True, token.end()
    return ("".join(pieces), cursor) if has_component else (None, start)


class _Emitter:
    def __init__(self):
        self.parts, self.trim_next, self.generated_tail, self.line_content = [], False, False, False

    def _append(self, value):
        if value:
            self.parts.append(value)
            self.generated_tail = False
            if "\n" in value:
                self.line_content = bool(value.rsplit("\n", 1)[-1].strip())
            elif value.strip():
                self.line_content = True

    def literal(self, value):
        if self.trim_next:
            value = value.lstrip(" \t")
        if value:
            self._append(value)
            self.trim_next = False

    def _trim(self):
        if not self.line_content:
            return  # Existing indentation belongs to the user.
        while self.parts:
            value = self.parts.pop().rstrip(" \t")
            if value:
                self.parts.append(value)
                break
        self.generated_tail = False

    def symbol(self, value, kind):
        keep_operator_space = self.generated_tail and kind == "join" and value in ("(", "[", "{")
        if kind != "quote_open" and not keep_operator_space:
            self._trim()
        if kind in ("binary", "flag", "unary") and self.line_content:
            self._append(" ")
        self._append(value)
        if kind in ("binary", "delimiter"):
            self._append(" ")
            self.generated_tail = True
        self.trim_next = kind not in ("close",)

    def finish(self):
        value = "".join(self.parts)
        return value[:-1] if self.generated_tail else value


def render_code(text):
    index, prefix = 0, "__CODE_LITERAL_0_"
    while prefix in text:
        index += 1
        prefix = f"__CODE_LITERAL_{index}_"
    saved = {}

    def save(value):
        token = f"{prefix}{len(saved)}__"
        saved[token] = value
        return token

    source = _LITERALS.sub(lambda match: save(match[0]), text)
    lines = []
    for line in source.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        # Existing syntax makes single operator words ordinary code identifiers.
        # Explicit multiword dictation commands still support mixed input.
        lines.append((save(body) if _TYPED_SYNTAX.search(body) and not _EXPLICIT.search(body) else body) + ending)
    source = "".join(lines)
    emitter, cursor = _Emitter(), 0
    while (match := _COMMAND.search(source, cursor)) is not None:
        emitter.literal(source[cursor:match.start()])
        key = match[0].casefold()
        if key in _CASES or key == "number":
            end = _operand_end(source, match.end(), signed=key == "number")
            operand = source[match.end():end].strip()
            if key in _CASES:
                value = _identifier(operand, _CASES[key], prefix)
            else:
                candidate = normalize_itn(operand, style="compact") if operand else ""
                value = candidate if re.fullmatch(r"-?\d+(?:\.\d+)?", candidate) else None
            if value is not None:
                emitter.literal(value)
                cursor = end
                continue
        elif key == "at file":
            value, end = _path(source, match.end())
            if value is not None:
                emitter.literal("@" + value)
                cursor = end
                continue
        else:
            declaration = _DECLARATION.search(source[max(0, match.start() - 40):match.start()])
            numeric_rhs = _NUMERIC_RHS.match(source, match.end())
            return_like = declaration and declaration[0].strip().casefold() in ("return", "yield")
            if " " not in key and declaration and not (return_like and numeric_rhs):
                emitter.literal(match[0])
                cursor = match.end()
                continue
            value, kind = _SYMBOLS[key]
            emitter.symbol(value, "unary" if return_like and numeric_rhs and key in ("plus", "minus") else kind)
            cursor = match.end()
            continue
        emitter.literal(match[0])  # Unsupported/empty operand stays visible, never dropped.
        cursor = match.end()
    emitter.literal(source[cursor:])
    result = emitter.finish()
    # Typed-line masks can contain a first-layer string/comment/entity mask.
    for _ in range(2):
        result = re.sub(re.escape(prefix) + r"\d+__", lambda match: saved[match[0]], result)
    return result
