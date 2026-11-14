"""Authored command-edit cases; semantic anchors supplement mechanical validation.

References are examples, not exact-match goldens. Anchors catch known omissions;
native outputs still need qualitative review and do not establish owner accuracy.
"""

import json
import re
from pathlib import Path

from .edit import validate_edit_output

DEFAULT_CASES = Path(__file__).resolve().parents[3] / 'tests' / 'command_edits.jsonl'


def load_cases(path=DEFAULT_CASES):
    cases = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate command edit case')
    return cases


def check_case(case, text):
    checked = validate_edit_output(case['selection'], case['instruction'], text)
    if not checked.ok:
        return checked.reason
    folded = text.casefold()
    if any(not any(option.casefold() in folded for option in group) for group in case['required']):
        return 'missing_semantic_anchor'
    if any(term.casefold() in folded for term in case.get('forbidden', [])):
        return 'unwanted_phrase'
    if case['kind'] == 'shorter' and len(text) >= len(case['selection']):
        return 'not_shorter'
    if len(re.findall(r'^\s*[-*•]\s+\S', text, re.MULTILINE)) < case.get('min_bullets', 0):
        return 'missing_bullets'
    return 'ok'
