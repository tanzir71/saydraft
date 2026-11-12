"""Native range operations against fake COM patterns, never the desktop."""

import sys
from types import SimpleNamespace as NS

import pytest

from saydraft.context.focused_edit import CaretText


class Range:
    def __init__(self, text, start, end, *, promote=False):
        self.text, self.start, self.end, self.promote = text, start, end, promote

    def GetText(self, maximum):
        assert maximum in (1025, 2)
        return self.text[self.start:self.end][:maximum]

    def Clone(self):
        return Range(self.text, self.start, self.end, promote=self.promote)

    def MoveEndpointByRange(self, endpoint, other, other_endpoint):
        if (endpoint, other_endpoint) == (1, 0):
            self.end = other.start
        else:
            assert (endpoint, other_endpoint) == (0, 1)
            self.start = other.end

    def MoveEndpointByUnit(self, endpoint, unit, count):
        if (endpoint, unit, count) == (0, 0, -1024):
            self.start = 0 if self.promote else max(0, self.start + count)
        else:
            assert (endpoint, unit, count) == (1, 0, 2)
            self.end = min(len(self.text), self.end + (100 if self.promote else 2))


def reader_and_element(selected, count):
    if sys.platform != "win32":
        pytest.skip("Windows COM binding required")
    from saydraft.context.uia_native import NativeUIAReader
    reader = NativeUIAReader.__new__(NativeUIAReader)
    reader.lib = NS(UIA_TextPatternId=14, UIA_TextPattern2Id=24, IUIAutomationTextPattern="text",
        IUIAutomationTextPattern2="caret", TextPatternRangeEndpoint_Start=0, TextPatternRangeEndpoint_End=1,
        TextUnit_Character=0)
    pattern = NS(GetSelection=lambda: NS(Length=count, GetElement=lambda index: selected))
    caret = NS(GetCaretRange=lambda: (True, selected))
    element = NS(GetCurrentPattern=lambda id: NS(QueryInterface=lambda interface: pattern if id == 14 else caret))
    return reader, element


def test_range_before_selection_ends_at_its_start_and_remains_adjacent_to_caret():
    selected = Range("A" * 2000 + "tailselected", 2004, 2012)
    reader, element = reader_and_element(selected, 1)
    result = reader.text_context(element, 1024)
    assert result == CaretText("A" * 1020 + "tail", "selected", "", True, True, True)
    assert selected.start == 2004 and selected.end == 2012  # Clone, never mutate the real selection.


def test_promoted_text_units_do_not_return_a_distant_document_prefix():
    selected = Range("A" * 2000 + "tailselected", 2004, 2012, promote=True)
    reader, element = reader_and_element(selected, 1)
    assert reader.text_context(element, 1024) == CaretText("", "selected", "", False, True, True)


def test_active_caret_fallback_and_disjoint_selection_avoid_invented_context():
    selected = Range("before after", 7, 7)
    reader, element = reader_and_element(selected, 0)
    assert reader.text_context(element, 1024) == CaretText("before ", "", "", True, False, False)
    reader, element = reader_and_element(selected, 2)
    assert reader.text_context(element, 1024) == CaretText()


def test_suffix_peek_starts_after_the_selection_and_does_not_move_it():
    selected = Range("left OLD right", 5, 8)
    reader, element = reader_and_element(selected, 1)
    result = reader.text_context(element, 1024)
    assert result == CaretText("left ", "OLD", " r", True, True, True)
    assert (selected.start, selected.end) == (5, 8)


def test_expiration_between_reads_prevents_the_next_native_text_request():
    selected = Range("Public selection", 0, 6)
    reader, element = reader_and_element(selected, 1)
    calls, get = [], selected.GetText
    selected.GetText = lambda maximum: calls.append(maximum) or get(maximum)
    checks = iter([True, False])
    assert reader.text_context(element, 1024, current=lambda: next(checks)) == CaretText()
    assert calls == [1025]
