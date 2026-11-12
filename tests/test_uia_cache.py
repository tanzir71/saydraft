import sys
from types import SimpleNamespace as NS

import pytest

from saydraft.context.focused_edit import FocusedEdit, read_focused_edit
from tests.test_focused_edit import Reader


def native_reader():
    if sys.platform != "win32":
        pytest.skip("Windows COM binding required")
    from saydraft.context.uia_native import NativeUIAReader
    reader = NativeUIAReader.__new__(NativeUIAReader)
    reader.lib = NS(UIA_IsPasswordPropertyId=19, UIA_ControlTypePropertyId=3, UIA_RuntimeIdPropertyId=0,
                    UIA_NativeWindowHandlePropertyId=20, UIA_HasKeyboardFocusPropertyId=8)
    return reader


def test_cached_identity_does_not_replace_live_password_and_focus_checks():
    reader, calls = native_reader(), []
    cached = {19: False, 3: 50004, 0: (1, 2, 3)}
    def cache(property, ignore_default):
        assert ignore_default is True
        calls.append(("cache", property))
        return cached[property]
    def current(property, ignore_default):
        assert ignore_default is True
        calls.append(("live", property))
        return True
    element = NS(GetCachedPropertyValueEx=cache, GetCurrentPropertyValueEx=current)
    assert reader.password(element) is False and reader.fresh_password(element) is True
    assert reader.control_type(element) == 50004 and reader.runtime_id(element) == (1, 2, 3)
    assert reader.same_focus(element)
    assert calls == [("cache", 19), ("live", 19), ("cache", 3), ("cache", 0), ("live", 8)]


def test_native_child_handle_proves_root_ownership_without_cross_process_parent_walk():
    reader, calls = native_reader(), []
    reader.user = NS(GetAncestor=lambda handle, flag: calls.append((handle, flag)) or 123)
    reader.native_windows = NS(GetParentElementBuildCache=lambda *args: pytest.fail("No UIA parent walk needed"))
    element = NS(GetCachedPropertyValueEx=lambda *args: -268435424)
    assert reader.belongs(element, 123) and calls == [(0xF0000020, 2)]


def test_native_ancestor_search_is_bounded_for_hwndless_provider_elements():
    reader, calls = native_reader(), []
    reader.cache = object()
    element = NS(GetCachedPropertyValueEx=lambda *args: 0)
    reader.native_windows = NS(GetParentElementBuildCache=lambda *args: calls.append(True) or element)
    assert not reader.belongs(element, 123) and len(calls) == 32


@pytest.mark.parametrize("fresh", [True, None])
def test_cached_false_cannot_authorize_text_after_sensitive_state_becomes_true_or_unknown(fresh):
    reader = Reader()
    reader.fresh_password = lambda element: fresh
    reader.text_context = lambda *args: pytest.fail("No sensitive text read")
    assert read_focused_edit(reader, 123) == (
        FocusedEdit(status="password", is_password=True) if fresh is True else FocusedEdit())
