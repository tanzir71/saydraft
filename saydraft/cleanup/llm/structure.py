"""Finite guards for layout and strong punctuation already rendered by rules."""

import re

_BREAKS = re.compile(r"\r\n|[\r\n]")
_PREFIX = re.compile(r"^[ \t]*(?:(?:[-*•]|\d+[.)])[ \t]+)?")
_STRONG = re.compile(r"\.{2,}|[…!?！？؟]")
_TERMINALS = ".。।۔!?！？؟…"
_CLOSERS = '\"\'”’)]}'


def _terminal(text):
    body = text.rstrip().rstrip(_CLOSERS)
    return body[len(body.rstrip(_TERMINALS)):]


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
    return None
