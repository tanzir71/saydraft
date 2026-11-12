"""Read-only focused-edit policy; unknown password state never authorizes text reads."""

from dataclasses import dataclass

TEXT_LIMIT = 1024


@dataclass(frozen=True)
class FocusedEdit:
    status: str = "unavailable"
    is_password: bool = False
    control_type: int | None = None
    before_caret: str = ""
    selection: str = ""
    runtime_id: tuple[int, ...] = ()
    selection_truncated: bool = False


def read_focused_edit(reader, window, *, include_text=True, current=lambda: True):
    """All element/proxy lifetimes stay on the caller's non-GUI MTA thread."""
    try:
        if not current():
            return FocusedEdit()
        element = reader.focused_element()
        if element is None or not reader.belongs(element, window):
            return FocusedEdit(status="changed")
        password = reader.password(element)
        if password is True:
            return FocusedEdit(status="password", is_password=True)
        if password is not False:
            return FocusedEdit()  # Unsupported/default/failed is not an explicit false.
        control_type = reader.control_type(element)
        if type(control_type) is not int or not 50000 <= control_type <= 59999:
            return FocusedEdit()
        runtime_id = reader.runtime_id(element)
        if (not isinstance(runtime_id, tuple) or not 1 <= len(runtime_id) <= 32
                or any(type(value) is not int or not -(2**31) <= value < 2**31 for value in runtime_id)):
            return FocusedEdit()
        if not reader.same_focus(element):
            return FocusedEdit(status="changed")
        if not current():
            return FocusedEdit()
        before, selection = "", ""
        if include_text:
            try:
                before, selection = reader.text_context(element, TEXT_LIMIT)
            except Exception:
                pass  # No supported caret pattern is a normal case.
        if not isinstance(before, str) or not isinstance(selection, str):
            return FocusedEdit()
        # Recheck sensitive state and identity before returning any text.
        password = reader.password(element)
        if password is True:
            return FocusedEdit(status="password", is_password=True)
        if password is not False:
            return FocusedEdit()
        if not reader.same_focus(element):
            return FocusedEdit(status="changed")
        if not current():
            return FocusedEdit()
        preceding = before.encode("utf-16-le", errors="surrogatepass")
        selected = selection.encode("utf-16-le", errors="surrogatepass")
        return FocusedEdit("ok", False, control_type,
            preceding[-2 * TEXT_LIMIT:].decode("utf-16-le", errors="ignore"),
            selected[:2 * TEXT_LIMIT].decode("utf-16-le", errors="ignore"), runtime_id,
            len(selected) // 2 > TEXT_LIMIT)
    except Exception:
        return FocusedEdit()  # Never return/log a provider's exception or partial text.
