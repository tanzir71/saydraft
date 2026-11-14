"""Browser container fallback uses only a bounded explicit read-only native range."""

from types import SimpleNamespace as NS

import pytest

from saydraft.context.uia_native import NativeUIAReader


def fixture():
    reader = NativeUIAReader.__new__(NativeUIAReader)
    reader.lib = NS(UIA_TextPatternId=10014, IUIAutomationTextPattern=object(),
        UIA_IsTextPatternAvailablePropertyId=30040, UIA_IsReadOnlyAttributeId=40015,
        UIA_ValueIsReadOnlyPropertyId=30046)
    reader.cache = object()
    state = NS(read_only=True, count=1, available=False, visits=[], clones=0)
    def no_text(*args):
        pytest.fail('Ancestor discovery must not read document, value or selection text')
    selected = NS(GetText=no_text)
    def attribute(key):
        assert key == 40015
        return state.read_only
    def clone():
        state.clones += 1
        return selected
    selected.GetAttributeValue, selected.Clone = attribute, clone
    class Ranges:
        @property
        def Length(self):
            return state.count
        def GetElement(self, index):
            assert index == 0
            return selected
    pattern = NS(GetSelection=Ranges)
    document = NS(kind=50030, password=False, fresh=False, handle=0, parent=None,
        GetCurrentPattern=lambda key: NS(QueryInterface=lambda interface: pattern))
    pane = NS(kind=50033, password=False, fresh=False, handle=0, parent=document)
    body = NS(kind=50026, password=False, fresh=False, handle=0, parent=pane,
        GetCurrentPropertyValueEx=lambda key, _ignore: state.available if key == 30040 else False)
    def unsupported(*args):
        raise OSError('No focused text pattern')
    body.GetCurrentPattern = unsupported
    def parent(element, cache):
        assert cache is reader.cache
        state.visits.append(element)
        return element.parent
    reader.client = NS(RawViewWalker=NS(GetParentElementBuildCache=parent))
    reader.control_type, reader.password = lambda node: node.kind, lambda node: node.password
    reader.fresh_password, reader.field_handle = lambda node: node.fresh, lambda node: node.handle
    return NS(reader=reader, body=body, pane=pane, document=document, state=state, selected=selected)


def test_focused_body_uses_selected_range_of_nearest_read_only_document_without_text_or_focus_changes():
    f = fixture()
    assert f.reader.selection_range(f.body, lambda: True) is f.selected
    assert f.state.visits == [f.body, f.pane] and f.state.clones == 1
    assert f.reader.selection_range_read_only(f.selected, lambda: True) is True


@pytest.mark.parametrize('value', [False, None, 0, 'true', object()])
def test_mutable_unknown_or_mixed_range_attributes_never_enable_container_fallback(value):
    f = fixture()
    f.state.read_only = value
    assert f.reader.selection_range(f.body, lambda: True) is None


@pytest.mark.parametrize('kind', [50000, 50004, 50005, 50030, 50032])
def test_interactive_controls_and_windows_cannot_borrow_an_ancestor_selection(kind):
    f = fixture()
    f.body.kind = kind
    assert f.reader.selection_range(f.body, lambda: True) is None and not f.state.visits


@pytest.mark.parametrize('change', ['password', 'unknown_password', 'fresh_password', 'native_window', 'edit', 'window',
                                   'missing_document', 'multiple'])
def test_sensitive_unknown_cross_window_and_ambiguous_paths_stop_without_an_answer(change):
    f = fixture()
    if change == 'password':
        f.pane.password = True
    elif change == 'unknown_password':
        f.pane.password = None
    elif change == 'fresh_password':
        f.pane.fresh = True
    elif change == 'native_window':
        f.pane.handle = 123
    elif change in ('edit', 'window'):
        f.pane.kind = 50004 if change == 'edit' else 50032
    elif change == 'missing_document':
        f.pane.parent = None
    elif change == 'multiple':
        f.state.count = 2
    assert f.reader.selection_range(f.body, lambda: True) is None


def test_empty_focused_container_selection_uses_document_but_multiple_ranges_are_ambiguous():
    f = fixture()
    focused_ranges = NS(Length=0)
    f.body.GetCurrentPattern = lambda key: NS(QueryInterface=lambda interface: NS(GetSelection=lambda: focused_ranges))
    assert f.reader.selection_range(f.body, lambda: True) is f.selected
    f.state.visits.clear()
    focused_ranges.Length = 2
    assert f.reader.selection_range(f.body, lambda: True) is None and not f.state.visits


@pytest.mark.parametrize('value', [True, False, None, 0, 'true'])
def test_selected_span_read_only_metadata_requires_a_boolean_and_observes_request_cancellation(value):
    f = fixture()
    f.state.read_only = value
    assert f.reader.selection_range_read_only(f.selected, lambda: True) is (value if type(value) is bool else None)
    assert f.reader.selection_range_read_only(f.selected, lambda: False) is None


def test_ancestor_walk_has_a_fixed_bound_and_observes_cancellation():
    f = fixture()
    f.pane.parent = f.pane
    assert f.reader.selection_range(f.body, lambda: True) is None and len(f.state.visits) == 8
    f.state.visits.clear()
    checks = iter([True, True, False])
    assert f.reader.selection_range(f.body, lambda: next(checks)) is None
    assert len(f.state.visits) <= 1
