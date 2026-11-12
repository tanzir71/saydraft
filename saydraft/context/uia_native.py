"""Windows UIA reader. Import on the owner thread, construct/use/close on its MTA worker."""

import threading

import comtypes
import comtypes.client

_TYPELIB_LOCK = threading.Lock()


class NativeUIAReader:
    def __init__(self):
        self._thread, self.client = threading.get_ident(), None
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
        except Exception:
            self.close()
            raise

    def close(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("UIA must close on its owning MTA thread")
        self.client = None
        if self._initialized:
            self._initialized = False
            comtypes.CoUninitialize()

    def focused_element(self):
        return self.client.GetFocusedElement()

    def belongs(self, element, window):
        for _ in range(32):
            if not element:
                return False
            if element.CurrentNativeWindowHandle == window:
                return True
            element = self.client.ControlViewWalker.GetParentElement(element)
        return False

    def same_focus(self, element):
        return bool(self.client.CompareElements(element, self.client.GetFocusedElement()))

    def password(self, element):
        value = element.GetCurrentPropertyValueEx(self.lib.UIA_IsPasswordPropertyId, True)
        return value if type(value) is bool else None

    def control_type(self, element):
        return element.GetCurrentPropertyValueEx(self.lib.UIA_ControlTypePropertyId, True)

    def runtime_id(self, element):
        return tuple(element.GetRuntimeId())

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
