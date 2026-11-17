"""Finite guards for layout and strong punctuation already rendered by rules."""

import re

_BREAKS = re.compile(r"\r\n|[\r\n]")
_PREFIX = re.compile(r"^[ \t]*(?:(?:[-*•]|\d+[.)])[ \t]+)?")
_STRONG = re.compile(r"\.{2,}|[…!?！？؟]")
_TERMINALS = ".。।۔!?！？؟…"
_CLOSERS = '\"\'”’)]}'
_LITERAL_COMMA = re.compile(r"(?<!\w)comma(?!\w)", re.I)
_COMMAS = ",،，、"


def _terminal(text):
    body = text.rstrip().rstrip(_CLOSERS)
    return body[len(body.rstrip(_TERMINALS)):]


def _literal_comma_edges(text):
    # A surviving spoken-punctuation word is literal after rules have run.
    # Compare only its immediate comma boundaries; ordinary prose punctuation
    # elsewhere remains editable. False refusals safely retain the rules text.
    edges = []
    for word in _LITERAL_COMMA.finditer(text):
        left, right = word.start() - 1, word.end()
        while left >= 0 and text[left] in " \t":
            left -= 1
        while right < len(text) and text[right] in " \t":
            right += 1
        edges.append((left >= 0 and text[left] in _COMMAS,
                      right < len(text) and text[right] in _COMMAS))
    return edges


def rule_structure_reason(source: str, candidate: str) -> str | None:
    """Refuse lost layout/explicit punctuation, allowing ordinary grammar edits.

    This does not establish semantic equivalence or enforce a golden string.
    An added final period is left to the prompt/app formatting contract.
    """
    if _BREAKS.findall(source) != _BREAKS.findall(candidate):
        return "rules_linebreaks_changed"
    for before, after in zip(_BREAKS.split(source), _BREAKS.split(candidate)):
        if (not before.strip()) != (not after.strip()):
            return "rules_paragraphs_changed"
        if _PREFIX.match(before)[0] != _PREFIX.match(after)[0]:
            return "rules_list_or_indent_changed"
        if _STRONG.findall(before) != _STRONG.findall(after):
            return "rules_punctuation_changed"
        terminal = _terminal(before)
        if terminal and terminal != _terminal(after):
            return "rules_terminal_changed"
        if _literal_comma_edges(before) != _literal_comma_edges(after):
            return "rules_literal_comma_changed"
    return None
