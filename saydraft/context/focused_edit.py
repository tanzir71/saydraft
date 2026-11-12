"""Read-only focused-edit policy; unknown password state never authorizes text reads."""

from dataclasses import dataclass

TEXT_LIMIT = 1024


@dataclass(frozen=True)
class CaretText:
    before_caret: str = ""
    selection: str = ""
    after_caret: str = ""
    before_known: bool = False
    selection_known: bool = False
    after_known: bool = False


@dataclass(frozen=True)
class FocusedEdit:
    status: str = "unavailable"
    is_password: bool = False
    control_type: int | None = None
    before_caret: str = ""
    selection: str = ""
    runtime_id: tuple[int, ...] = ()
    selection_truncated: bool = False
    before_caret_known: bool = False
    selection_known: bool = False
    after_caret: str = ""
    after_caret_known: bool = False


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
        fresh_password = getattr(reader, "fresh_password", reader.password)
        if include_text:
            password = fresh_password(element)
            if password is True:
                return FocusedEdit(status="password", is_password=True)
            if password is not False:
                return FocusedEdit()
            if not reader.same_focus(element):
                return FocusedEdit(status="changed")
        if not current():
            return FocusedEdit()
        caret = CaretText()
        if include_text:
            try:
                aware = getattr(reader, "text_context_for_request", None)
                value = aware(element, TEXT_LIMIT, current) if aware is not None else reader.text_context(element, TEXT_LIMIT)
                caret = value if isinstance(value, CaretText) else CaretText(*value, before_known=True, selection_known=True)
            except Exception:
                pass  # No supported caret pattern is a normal case.
        if (not all(isinstance(value, str) for value in (caret.before_caret, caret.selection, caret.after_caret))
                or not all(type(flag) is bool for flag in (caret.before_known, caret.selection_known, caret.after_known))):
            return FocusedEdit()
        if not current():
            return FocusedEdit()
        # Recheck sensitive state and identity before returning any text.
        password = fresh_password(element)
        if password is True:
            return FocusedEdit(status="password", is_password=True)
        if password is not False:
            return FocusedEdit()
        if not reader.same_focus(element):
            return FocusedEdit(status="changed")
        if not current():
            return FocusedEdit()
        preceding = (caret.before_caret if caret.before_known else "").encode("utf-16-le", errors="surrogatepass")
        selected = (caret.selection if caret.selection_known else "").encode("utf-16-le", errors="surrogatepass")
        following = caret.after_caret if caret.after_known else ""
        after_known = caret.after_known
        try:
            after = following.encode("utf-16-le", errors="surrogatepass")[:4].decode("utf-16-le")[:1]
        except UnicodeError:
            after, after_known = "", False
        return FocusedEdit("ok", False, control_type,
            preceding[-2 * TEXT_LIMIT:].decode("utf-16-le", errors="ignore"),
            selected[:2 * TEXT_LIMIT].decode("utf-16-le", errors="ignore"), runtime_id,
            len(selected) // 2 > TEXT_LIMIT, caret.before_known, caret.selection_known, after, after_known)
    except Exception:
        return FocusedEdit()  # Never return/log a provider's exception or partial text.
