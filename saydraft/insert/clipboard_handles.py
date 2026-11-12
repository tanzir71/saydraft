"""Owned, size-checked copies of Windows clipboard memory and GDI objects."""

import ctypes as ct
from ctypes import wintypes as wt
from dataclasses import dataclass

MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
_BASE_FORMAT = {0x82: 2, 0x83: 3, 0x8E: 14}  # Display bitmap/metafile equivalents.


class ClipboardUnavailable(OSError):
    """No clipboard mutation is safe; preserve it and use another delivery route."""


class SnapshotTooLarge(ClipboardUnavailable):
    pass


class Bitmap(ct.Structure):
    _fields_ = [("type", wt.LONG), ("width", wt.LONG), ("height", wt.LONG),
        ("width_bytes", wt.LONG), ("planes", wt.WORD), ("bits_pixel", wt.WORD), ("bits", ct.c_void_p)]


class MetafilePicture(ct.Structure):
    _fields_ = [("mapping_mode", wt.LONG), ("x_extent", wt.LONG), ("y_extent", wt.LONG), ("metafile", wt.HANDLE)]


@dataclass
class StoredFormat:
    format: int
    handle: int
    size: int
    api: object

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, 0
            self.api.free(self.format, handle)

    def transfer(self):
        """Call only after successful SetClipboardData; Windows now owns this copy."""
        self.handle = 0


class ClipboardHandles:
    def __init__(self):
        self.kernel = ct.WinDLL("kernel32", use_last_error=True)
        self.gdi = ct.WinDLL("gdi32", use_last_error=True)
        self.ole = ct.WinDLL("ole32", use_last_error=True)
        signatures = (
            (self.kernel, "GlobalSize", [wt.HANDLE], ct.c_size_t),
            (self.kernel, "GlobalLock", [wt.HANDLE], ct.c_void_p),
            (self.kernel, "GlobalUnlock", [wt.HANDLE], wt.BOOL),
            (self.kernel, "GlobalAlloc", [wt.UINT, ct.c_size_t], wt.HANDLE),
            (self.kernel, "GlobalFree", [wt.HANDLE], wt.HANDLE),
            (self.gdi, "GetObjectW", [wt.HANDLE, ct.c_int, ct.c_void_p], ct.c_int),
            (self.gdi, "GetPaletteEntries", [wt.HANDLE, wt.UINT, wt.UINT, ct.c_void_p], wt.UINT),
            (self.gdi, "GetEnhMetaFileBits", [wt.HANDLE, wt.UINT, ct.c_void_p], wt.UINT),
            (self.gdi, "GetMetaFileBitsEx", [wt.HANDLE, wt.UINT, ct.c_void_p], wt.UINT),
            (self.gdi, "CopyEnhMetaFileW", [wt.HANDLE, wt.LPCWSTR], wt.HANDLE),
            (self.gdi, "DeleteEnhMetaFile", [wt.HANDLE], wt.BOOL),
            (self.gdi, "DeleteMetaFile", [wt.HANDLE], wt.BOOL),
            (self.gdi, "DeleteObject", [wt.HANDLE], wt.BOOL),
            (self.ole, "OleDuplicateData", [wt.HANDLE, wt.WORD, wt.UINT], wt.HANDLE))
        for library, name, args, result in signatures:
            function = getattr(library, name)
            function.argtypes, function.restype = args, result

    def _picture(self, handle):
        if self.kernel.GlobalSize(handle) < ct.sizeof(MetafilePicture):
            raise ClipboardUnavailable("Metafile picture is unavailable")
        pointer = self.kernel.GlobalLock(handle)
        if not pointer:
            raise ClipboardUnavailable("Metafile picture is unavailable")
        try:
            return MetafilePicture.from_buffer_copy(ct.string_at(pointer, ct.sizeof(MetafilePicture)))
        finally:
            self.kernel.GlobalUnlock(handle)

    def size(self, format, handle):
        if type(format) is not int or not 1 <= format <= 0xFFFF:
            raise ClipboardUnavailable("Invalid clipboard format identifier")
        if not handle or format == 0x80 or 0x200 <= format <= 0x2FF:
            # Owner-display/private handles can be arbitrary pointers with owner-specific lifetimes.
            raise ClipboardUnavailable("Opaque clipboard owner format")
        kind = _BASE_FORMAT.get(format, format)
        if kind == 2:
            bitmap = Bitmap()
            if self.gdi.GetObjectW(handle, ct.sizeof(bitmap), ct.byref(bitmap)) != ct.sizeof(bitmap):
                raise ClipboardUnavailable("Bitmap could not be rendered")
            size = abs(bitmap.height) * bitmap.width_bytes
            if bitmap.width <= 0 or bitmap.height == 0 or bitmap.width_bytes <= 0:
                raise ClipboardUnavailable("Invalid bitmap dimensions")
        elif kind == 9:
            entries = self.gdi.GetPaletteEntries(handle, 0, 0, None)
            size = 4 + 4 * entries if entries else 0
        elif kind == 14:
            size = self.gdi.GetEnhMetaFileBits(handle, 0, None)
        elif kind == 3:
            picture = self._picture(handle)
            bits = self.gdi.GetMetaFileBitsEx(picture.metafile, 0, None)
            size = ct.sizeof(MetafilePicture) + bits if bits else 0
        else:
            size = self.kernel.GlobalSize(handle)
        if not size:
            raise ClipboardUnavailable("Clipboard format could not be rendered")
        return size

    def duplicate(self, format, handle, *, remaining=MAX_SNAPSHOT_BYTES):
        size = self.size(format, handle)
        if not 0 < size <= remaining <= MAX_SNAPSHOT_BYTES:
            raise SnapshotTooLarge("Clipboard snapshot exceeds its memory limit")
        kind = _BASE_FORMAT.get(format, format)
        copy = (self.gdi.CopyEnhMetaFileW(handle, None) if kind == 14
                else self.ole.OleDuplicateData(handle, kind, 2))  # GMEM_MOVEABLE.
        if not copy or copy == handle:
            raise ClipboardUnavailable("Clipboard format could not be duplicated")
        return StoredFormat(format, copy, size, self)

    def memory(self, format, data):
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SNAPSHOT_BYTES:
            raise ClipboardUnavailable("Invalid clipboard payload size")
        handle = self.kernel.GlobalAlloc(2, len(data))
        if not handle:
            raise ClipboardUnavailable("Clipboard memory allocation failed")
        pointer = self.kernel.GlobalLock(handle)
        if not pointer:
            self.kernel.GlobalFree(handle)
            raise ClipboardUnavailable("Clipboard memory allocation failed")
        try:
            ct.memmove(pointer, data, len(data))
        except BaseException:
            self.kernel.GlobalUnlock(handle)
            self.kernel.GlobalFree(handle)
            raise
        self.kernel.GlobalUnlock(handle)
        return StoredFormat(format, handle, len(data), self)

    def unicode_text(self, handle, *, limit=65536):
        """Read a bounded, terminated CF_UNICODETEXT allocation without changing it."""
        size = self.kernel.GlobalSize(handle)
        if not 2 <= size <= (limit + 1) * 2 or size % 2:
            raise ClipboardUnavailable("Clipboard text exceeds its limit or is unavailable")
        pointer = self.kernel.GlobalLock(handle)
        if not pointer:
            raise ClipboardUnavailable("Clipboard text is unavailable")
        try:
            data = ct.string_at(pointer, size)
        finally:
            self.kernel.GlobalUnlock(handle)
        end = next((i for i in range(0, size, 2) if data[i:i+2] == b"\0\0"), None)
        if end is None:
            raise ClipboardUnavailable("Clipboard text has no terminator")
        try:
            return data[:end].decode("utf-16-le")
        except UnicodeError as exc:
            raise ClipboardUnavailable("Clipboard text is not valid Unicode") from exc

    def free(self, format, handle):
        kind = _BASE_FORMAT.get(format, format)
        if kind in (2, 9):
            failed = not self.gdi.DeleteObject(handle)
        elif kind == 14:
            failed = not self.gdi.DeleteEnhMetaFile(handle)
        elif kind == 3:
            try:
                picture = self._picture(handle)
                failed = not self.gdi.DeleteMetaFile(picture.metafile)
            finally:
                freed = not self.kernel.GlobalFree(handle)
            failed = failed or not freed
        else:
            failed = bool(self.kernel.GlobalFree(handle))
        if failed:
            raise ClipboardUnavailable("Clipboard copy cleanup failed")
