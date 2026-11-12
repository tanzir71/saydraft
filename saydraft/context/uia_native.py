"""Windows UIA reader. Import on the owner thread, construct/use/close on its MTA worker."""

import threading
import ctypes as ct
from ctypes import wintypes as wt

import comtypes
import comtypes.client

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
                                self.lib.UIA_RuntimeIdPropertyId, self.lib.UIA_NativeWindowHandlePropertyId):
                self.cache.AddProperty(property_id)  # Metadata only; no text, Name or Value.
            condition = self.client.CreateNotCondition(
                self.client.CreatePropertyCondition(self.lib.UIA_NativeWindowHandlePropertyId, 0))
            self.native_windows = self.client.CreateTreeWalker(condition)
            self.user = ct.WinDLL("user32", use_last_error=True)
            self.user.GetAncestor.argtypes, self.user.GetAncestor.restype = [wt.HWND, wt.UINT], wt.HWND
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
        return element.GetCurrentPropertyValueEx(self.lib.UIA_HasKeyboardFocusPropertyId, True) is True

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

    def text_context(self, element, limit):
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("UIA text read must be bounded")
        lib = self.lib
        pattern = element.GetCurrentPattern(lib.UIA_TextPatternId).QueryInterface(lib.IUIAutomationTextPattern)
        ranges = pattern.GetSelection()
        if ranges.Length == 1:
            selected = ranges.GetElement(0)
        elif ranges.Length == 0:
            pattern2 = element.GetCurrentPattern(lib.UIA_TextPattern2Id).QueryInterface(lib.IUIAutomationTextPattern2)
            active, selected = pattern2.GetCaretRange()
            if not active:
                return "", ""
        else:
            return "", ""  # Multiple disjoint selections have no single insertion context.
        selection = selected.GetText(limit + 1)
        before = selected.Clone()
        before.MoveEndpointByRange(lib.TextPatternRangeEndpoint_End, selected, lib.TextPatternRangeEndpoint_Start)
        before.MoveEndpointByUnit(lib.TextPatternRangeEndpoint_Start, lib.TextUnit_Character, -limit)
        preceding = before.GetText(limit + 1)
        # Providers may promote Character to a larger unit. A bounded prefix
        # of that larger range would not be adjacent to the caret.
        if len(preceding.encode("utf-16-le", errors="surrogatepass")) // 2 > limit:
            preceding = ""
        return preceding, selection
