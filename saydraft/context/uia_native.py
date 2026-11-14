"""Windows UIA reader. Import on the owner thread, construct/use/close on its MTA worker."""

import threading
from array import array
import ctypes as ct
from ctypes import wintypes as wt

import comtypes
import comtypes.client

from .focused_edit import CaretText

_TYPELIB_LOCK = threading.Lock()


class NativeUIAReader:
    def __init__(self):
        self._thread, self.client = threading.get_ident(), None
        self.cache = self.native_windows = None
        comtypes.CoInitializeEx(0)  # COINIT_MULTITHREADED; this thread owns no windows.
        self._initialized = True
        try:
            with _TYPELIB_LOCK:
                previous = comtypes.client.gen_dir
                try:
                    comtypes.client.gen_dir = None  # Generate SDK metadata only in RAM, never user text on disk.
                    self.lib = comtypes.client.GetModule("UIAutomationCore.dll")
                finally:
                    comtypes.client.gen_dir = previous
            self.client = comtypes.client.CreateObject(self.lib.CUIAutomation8,
                interface=self.lib.IUIAutomation2, clsctx=comtypes.CLSCTX_INPROC_SERVER)
            self.client.AutoSetFocus = False
            self.client.ConnectionTimeout = 100
            self.client.TransactionTimeout = 100
            self.cache = self.client.CreateCacheRequest()
            self.cache.TreeScope = self.lib.TreeScope_Element
            self.cache.TreeFilter = self.client.RawViewCondition
            self.cache.AutomationElementMode = self.lib.AutomationElementMode_Full
            for property_id in (self.lib.UIA_IsPasswordPropertyId, self.lib.UIA_ControlTypePropertyId,
                                self.lib.UIA_RuntimeIdPropertyId, self.lib.UIA_NativeWindowHandlePropertyId,
                                self.lib.UIA_HasKeyboardFocusPropertyId):
                self.cache.AddProperty(property_id)  # Metadata only; no text, Name or Value.
            condition = self.client.CreateNotCondition(
                self.client.CreatePropertyCondition(self.lib.UIA_NativeWindowHandlePropertyId, 0))
            self.native_windows = self.client.CreateTreeWalker(condition)
            self.user = ct.WinDLL("user32", use_last_error=True)
            self.user.GetAncestor.argtypes, self.user.GetAncestor.restype = [wt.HWND, wt.UINT], wt.HWND
            self.user.GetWindowThreadProcessId.argtypes = [wt.HWND, ct.POINTER(wt.DWORD)]
            self.user.GetWindowThreadProcessId.restype = wt.DWORD
        except Exception:
            self.close()
            raise

    def close(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("UIA must close on its owning MTA thread")
        self.native_windows = self.cache = self.client = None
        if self._initialized:
            self._initialized = False
            comtypes.CoUninitialize()

    def focused_element(self):
        return self.client.GetFocusedElementBuildCache(self.cache)

    def belongs(self, element, window):
        for _ in range(32):
            if not element:
                return False
            handle = element.GetCachedPropertyValueEx(self.lib.UIA_NativeWindowHandlePropertyId, True)
            if type(handle) is int and handle:
                handle &= 0xFFFFFFFF  # UIA's HWND property is a signed 32-bit value.
                if handle == window or self.user.GetAncestor(handle, 2) == window:  # GA_ROOT.
                    return True
            element = self.native_windows.GetParentElementBuildCache(element, self.cache)
        return False

    def same_focus(self, element):
        return self.keyboard_focus(element) is True

    def keyboard_focus(self, element):
        value = element.GetCurrentPropertyValueEx(self.lib.UIA_HasKeyboardFocusPropertyId, True)
        return value if type(value) is bool else None

    def keyboard_focus_snapshot(self, element):
        value = element.GetCachedPropertyValueEx(self.lib.UIA_HasKeyboardFocusPropertyId, True)
        return value if type(value) is bool else None

    def window_pid(self, window):
        pid = wt.DWORD()
        if not self.user.GetWindowThreadProcessId(window, ct.byref(pid)):
            return None
        return pid.value

    def current_runtime_id(self, element):
        return tuple(element.GetRuntimeId())

    def field_handle(self, element):
        handle = element.GetCachedPropertyValueEx(self.lib.UIA_NativeWindowHandlePropertyId, True)
        return handle & 0xFFFFFFFF if type(handle) is int and handle else 0

    def refresh_element(self, element, window, runtime_id, current):
        if not current():
            return None
        handle = self.field_handle(element)
        if handle:
            fresh = self.client.ElementFromHandleBuildCache(handle, self.cache)
            if current() and self.runtime_id(fresh) == runtime_id:
                return fresh
        if not current():
            return None
        root = self.client.ElementFromHandleBuildCache(window, self.cache)
        condition = self.client.CreatePropertyCondition(self.lib.UIA_RuntimeIdPropertyId, array("i", runtime_id))
        fresh = root.FindFirstBuildCache(self.lib.TreeScope_Subtree, condition, self.cache)
        return fresh if fresh and current() else None  # Metadata-only, exact identity under the original HWND.

    def password(self, element):
        value = element.GetCachedPropertyValueEx(self.lib.UIA_IsPasswordPropertyId, True)
        return value if type(value) is bool else None

    def fresh_password(self, element):
        value = element.GetCurrentPropertyValueEx(self.lib.UIA_IsPasswordPropertyId, True)
        return value if type(value) is bool else None

    def control_type(self, element):
        return element.GetCachedPropertyValueEx(self.lib.UIA_ControlTypePropertyId, True)

    def runtime_id(self, element):
        return tuple(element.GetCachedPropertyValueEx(self.lib.UIA_RuntimeIdPropertyId, True))

    def _read_range(self, value, limit, current):
        if type(limit) is not int or not 1 <= limit <= 8192 or not current():
            return None
        text = value.GetText(limit + 1)
        if (not isinstance(text, str) or len(text.encode("utf-16-le")) // 2 > limit or not current()):
            return None
        return text

    def document_text(self, element, limit, current):
        pattern = element.GetCurrentPattern(self.lib.UIA_TextPatternId).QueryInterface(self.lib.IUIAutomationTextPattern)
        return self._read_range(pattern.DocumentRange, limit, current)

    def insertion_edges(self, element, limit, current):
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        ranges = pattern.GetSelection()
        if ranges.Length != 1:
            return None
        selected, document = ranges.GetElement(0), pattern.DocumentRange
        before, after = document.Clone(), document.Clone()
        before.MoveEndpointByRange(lib.TextPatternRangeEndpoint_End, selected, lib.TextPatternRangeEndpoint_Start)
        after.MoveEndpointByRange(lib.TextPatternRangeEndpoint_Start, selected, lib.TextPatternRangeEndpoint_End)
        parts = []
        for value in (before, after):
            text = self._read_range(value, limit, current)
            if text is None:
                return None
            parts.append(text)
        # Do not read the replaced selection. The subsequent fresh full-field
        # confirmation must match these edges and the exact inserted text.
        return tuple(parts)

    def text_context_for_request(self, element, limit, current):
        return self.text_context(element, limit, current=current)

    def selection_range(self, element, current):
        """Clone one selected range; no caret/document/value fallback or selection mutation."""
        if not current():
            return None
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        ranges = pattern.GetSelection()
        if type(ranges.Length) is not int or ranges.Length != 1 or not current():
            return None
        selected = ranges.GetElement(0).Clone()
        return selected if current() else None

    def selection_text(self, selected, limit, current):
        if type(limit) is not int or not 1 <= limit <= 8192 or not current():
            return None
        text = selected.GetText(limit + 1)
        return text if current() else None

    def same_selection(self, saved, current):
        lib = self.lib
        for endpoint in (lib.TextPatternRangeEndpoint_Start, lib.TextPatternRangeEndpoint_End):
            comparison = saved.CompareEndpoints(endpoint, current, endpoint)
            if type(comparison) is not int or comparison != 0:
                return False
        return True

    def selection_read_only(self, element):
        try:
            value = element.GetCurrentPropertyValueEx(self.lib.UIA_ValueIsReadOnlyPropertyId, True)
            return value if type(value) is bool else None
        except Exception:
            return None

    def _position_range(self, document, position, current):
        lib = self.lib
        result = document.Clone()
        result.MoveEndpointByRange(lib.TextPatternRangeEndpoint_End, document, lib.TextPatternRangeEndpoint_Start)
        if position:
            moved = result.MoveEndpointByUnit(lib.TextPatternRangeEndpoint_Start, lib.TextUnit_Character, position)
            if type(moved) is not int or moved != position:
                return None
        return result if current() else None

    def selection_position(self, element, selected, current):
        """Round-trip a metadata-only native offset, with no document GetText."""
        if not current():
            return None
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        document, probe = pattern.DocumentRange, selected.Clone()
        moved = probe.MoveEndpointByUnit(lib.TextPatternRangeEndpoint_Start, lib.TextUnit_Character, -(2**31 - 1))
        if type(moved) is not int or not -(2**31 - 1) <= moved <= 0 or not current():
            return None
        compared = probe.CompareEndpoints(lib.TextPatternRangeEndpoint_Start, document, lib.TextPatternRangeEndpoint_Start)
        if type(compared) is not int or compared != 0:
            return None
        restored = self._position_range(document, -moved, current)
        if restored is None:
            return None
        compared = restored.CompareEndpoints(lib.TextPatternRangeEndpoint_Start, selected, lib.TextPatternRangeEndpoint_Start)
        return -moved if type(compared) is int and compared == 0 and current() else None

    def replacement_text(self, element, position, limit, current):
        """Read only the bounded planned span ending at the current caret.

        Native units may be promoted by a provider; capture requires an exact
        round trip. No Python character count is used as a native coordinate.
        """
        if (type(position) is not int or not 0 <= position < 2**31 or type(limit) is not int
                or not 1 <= limit <= 16384 or not current()):
            return None
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        start = self._position_range(pattern.DocumentRange, position, current)
        caret = self.selection_range(element, current)
        if start is None or caret is None:
            return None
        collapsed = caret.CompareEndpoints(lib.TextPatternRangeEndpoint_Start, caret, lib.TextPatternRangeEndpoint_End)
        after = start.CompareEndpoints(lib.TextPatternRangeEndpoint_Start, caret, lib.TextPatternRangeEndpoint_Start)
        if type(collapsed) is not int or collapsed != 0 or type(after) is not int or after >= 0 or not current():
            return None
        start.MoveEndpointByRange(lib.TextPatternRangeEndpoint_End, caret, lib.TextPatternRangeEndpoint_Start)
        text = start.GetText(limit + 1)
        if (type(text) is not str or len(text) > limit or len(text.encode("utf-16-le")) // 2 > limit or not current()):
            return None
        fresh = self.selection_range(element, current)
        if fresh is None or not self.same_selection(caret, fresh) or not current():
            return None
        return text

    def text_context(self, element, limit, *, current=lambda: True):
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("UIA text read must be bounded")
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        ranges = pattern.GetSelection()
        selection_known = ranges.Length == 1
        if ranges.Length == 1:
            selected = ranges.GetElement(0)
        elif ranges.Length == 0:
            pattern2 = element.GetCurrentPattern(lib.UIA_TextPattern2Id).QueryInterface(lib.IUIAutomationTextPattern2)
            active, selected = pattern2.GetCaretRange()
            if not active:
                return CaretText()
        else:
            return CaretText()  # Multiple disjoint selections have no single insertion context.
        if not current():
            return CaretText()
        selection = selected.GetText(limit + 1)
        if not current():
            return CaretText()
        before = selected.Clone()
        before.MoveEndpointByRange(lib.TextPatternRangeEndpoint_End, selected, lib.TextPatternRangeEndpoint_Start)
        before.MoveEndpointByUnit(lib.TextPatternRangeEndpoint_Start, lib.TextUnit_Character, -limit)
        preceding = before.GetText(limit + 1)
        # Providers may promote Character to a larger unit. A bounded prefix
        # of that larger range would not be adjacent to the caret.
        before_known = len(preceding.encode("utf-16-le", errors="surrogatepass")) // 2 <= limit
        if not before_known:
            preceding = ""
        if not current():
            return CaretText()
        following, after_known = "", False
        if selection_known:
            try:
                after = selected.Clone()
                after.MoveEndpointByRange(lib.TextPatternRangeEndpoint_Start, selected, lib.TextPatternRangeEndpoint_End)
                after.MoveEndpointByUnit(lib.TextPatternRangeEndpoint_End, lib.TextUnit_Character, 2)
                if not current():
                    return CaretText()
                following, after_known = after.GetText(2), True  # At most one surrogate pair.
            except Exception:
                pass  # A valid preceding range remains useful without a suffix peek.
        return CaretText(preceding, selection, following, before_known, selection_known, after_known)
