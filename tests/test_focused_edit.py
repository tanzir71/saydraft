"""Read-only UIA policy; no desktop or real user content in these tests."""

import pytest

from saydraft.context.focused_edit import CaretText, FocusedEdit, TEXT_LIMIT, read_focused_edit


class Reader:
    def focused_element(self):
        return "fixture"

    def belongs(self, element, window):
        assert element == "fixture" and window == 123
        return True

    def password(self, element):
        return False

    def control_type(self, element):
        return 50004

    def runtime_id(self, element):
        return (1, 2, 3)

    def same_focus(self, element):
        return True

    def text_context(self, element, limit):
        assert limit == TEXT_LIMIT
        return "Before caret ", "Public selection"


def test_explicit_non_password_field_returns_bounded_context_and_identity():
    assert read_focused_edit(Reader(), 123) == FocusedEdit(
        "ok", False, 50004, "Before caret ", "Public selection", (1, 2, 3),
        before_caret_known=True, selection_known=True)


@pytest.mark.parametrize("password", [True, None, 0, "false"])
def test_password_and_unknown_state_never_read_content_or_other_field_properties(password):
    reader = Reader()
    reader.password = lambda element: password
    for name in ("control_type", "runtime_id", "text_context"):
        setattr(reader, name, lambda *args: pytest.fail("Sensitive state must short circuit"))
    result = read_focused_edit(reader, 123)
    assert result == (FocusedEdit(status="password", is_password=True) if password is True else FocusedEdit())


@pytest.mark.parametrize("field", ["focused_element", "belongs", "password", "control_type", "runtime_id", "same_focus"])
def test_provider_errors_discard_partial_context_without_logging_exceptions(field, caplog):
    reader = Reader()
    def fail(*args):
        raise RuntimeError("Public exception fixture must not be logged")
    setattr(reader, field, fail)
    assert read_focused_edit(reader, 123) == FocusedEdit()
    assert not caplog.records


@pytest.mark.parametrize("changed", ["password", "focus"])
def test_changed_sensitive_state_discards_already_read_text(changed):
    reader = Reader()
    checks = iter([False, False, True] if changed == "password" else [True, False])
    setattr(reader, "password" if changed == "password" else "same_focus", lambda element: next(checks))
    result = read_focused_edit(reader, 123)
    assert result.before_caret == result.selection == "" and not result.runtime_id
    assert result.status == ("password" if changed == "password" else "changed")


def test_wrong_window_never_reads_a_password_flag_or_text():
    reader = Reader()
    reader.belongs = lambda *args: False
    reader.password = lambda *args: pytest.fail("Unrelated field must not be inspected")
    assert read_focused_edit(reader, 123).status == "changed"


@pytest.mark.parametrize("runtime_id", [(), tuple(range(33)), (True,), (2**31,), [1, 2]])
def test_invalid_runtime_ids_never_authorize_text_reads(runtime_id):
    reader = Reader()
    reader.runtime_id = lambda element: runtime_id
    reader.text_context = lambda *args: pytest.fail("Missing field identity")
    assert read_focused_edit(reader, 123) == FocusedEdit()


def test_missing_caret_pattern_keeps_verified_field_but_never_invents_text():
    reader = Reader()
    def unsupported(*args):
        raise OSError("No text pattern")
    reader.text_context = unsupported
    result = read_focused_edit(reader, 123)
    assert result.status == "ok" and result.control_type == 50004
    assert result.before_caret == result.selection == ""


def test_utf16_bounds_keep_tail_before_caret_and_flag_incomplete_selection():
    reader = Reader()
    reader.text_context = lambda *args: ("A" * 10 + "😀" * 600, "😀" * 600 + "B" * 10)
    result = read_focused_edit(reader, 123)
    assert result.before_caret == result.selection == "😀" * 512 and result.selection_truncated


def test_metadata_verification_uses_one_fresh_password_and_focus_check_without_text():
    reader, calls = Reader(), []
    reader.fresh_password = lambda element: calls.append("password") or False
    reader.same_focus = lambda element: calls.append("focus") or True
    reader.text_context = lambda *args: pytest.fail("Metadata verification must not read text")
    result = read_focused_edit(reader, 123, include_text=False)
    assert result.status == "ok" and result.before_caret == result.selection == ""
    assert calls == ["password", "focus"]


def test_known_empty_context_differs_from_unavailable_and_suffix_is_one_unicode_character():
    reader = Reader()
    reader.text_context = lambda *args: CaretText("", "", "😀x", True, True, True)
    result = read_focused_edit(reader, 123)
    assert result.before_caret == "" and result.before_caret_known and result.selection_known
    assert result.after_caret == "😀" and result.after_caret_known
    reader.text_context = lambda *args: CaretText("Unplaced prefix", "Unknown selection", "x")
    result = read_focused_edit(reader, 123)
    assert result.before_caret == result.selection == result.after_caret == ""
    assert not result.before_caret_known and not result.selection_known and not result.after_caret_known


def test_incomplete_surrogate_peek_is_unknown_rather_than_an_empty_field_suffix():
    reader = Reader()
    reader.text_context = lambda *args: CaretText("", "", "\ud83d", True, True, True)
    result = read_focused_edit(reader, 123)
    assert result.after_caret == "" and not result.after_caret_known
