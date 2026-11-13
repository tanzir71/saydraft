"""Fake COM ranges verify native calls without reading the desktop."""

from types import SimpleNamespace as NS

import pytest

from tests.test_uia_patterns import Range, reader_and_element


def test_native_selection_clones_only_one_selected_range_without_reading_edges():
    selected = Range("Public selection", 0, 16)
    reader, element = reader_and_element(selected, 1)
    clone = reader.selection_range(element, lambda: True)
    assert clone is not selected and (clone.start, clone.end) == (0, 16)
    for count in (0, 2):
        reader, element = reader_and_element(selected, count)
        assert reader.selection_range(element, lambda: True) is None


def test_native_text_limit_is_bounded_and_checked_before_and_after_the_read():
    reader, _ = reader_and_element(Range("x", 0, 1), 1)
    calls = []
    selected = NS(GetText=lambda limit: calls.append(limit) or "Public")
    assert reader.selection_text(selected, 8192, lambda: True) == "Public" and calls == [8193]
    for limit in (-1, 0, 8193, True):
        assert reader.selection_text(selected, limit, lambda: True) is None
    assert reader.selection_text(selected, 8192, lambda: False) is None and calls == [8193]
    checks = iter([True, False])
    assert reader.selection_text(selected, 8192, lambda: next(checks)) is None


@pytest.mark.parametrize("start,end,expected", [(0, 0, True), (1, 0, False), (0, -1, False), (False, 0, False)])
def test_both_native_endpoints_must_match_as_integer_positions(start, end, expected):
    reader, _ = reader_and_element(Range("x", 0, 1), 1)
    calls = []
    current = object()
    def compare(endpoint, other, other_endpoint):
        assert other is current and other_endpoint == endpoint
        calls.append(endpoint)
        return start if endpoint == 0 else end
    assert reader.same_selection(NS(CompareEndpoints=compare), current) is expected
    assert calls[0] == 0


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), (0, None), ("false", None), (None, None)])
def test_read_only_property_is_tri_state_and_does_not_read_value(value, expected):
    reader, _ = reader_and_element(Range("x", 0, 1), 1)
    reader.lib.UIA_ValueIsReadOnlyPropertyId = 30046
    calls = []
    element = NS(GetCurrentPropertyValueEx=lambda key, ignore_default: calls.append((key, ignore_default)) or value)
    assert reader.selection_read_only(element) is expected and calls == [(30046, True)]
