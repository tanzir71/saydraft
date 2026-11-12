"""Round-trip public in-memory clipboard objects without touching the clipboard."""

import argparse
import ctypes as ct
import json
import subprocess
from ctypes import wintypes as wt
from pathlib import Path

from saydraft.insert.clipboard_handles import Bitmap, ClipboardHandles, MetafilePicture, StoredFormat


def roundtrip(on_live=None):
    api, sources, copies = ClipboardHandles(), [], []
    signatures = (
        ("CreateBitmap", [ct.c_int, ct.c_int, wt.UINT, wt.UINT, ct.c_void_p], wt.HANDLE),
        ("GetBitmapBits", [wt.HANDLE, wt.LONG, ct.c_void_p], wt.LONG),
        ("CreatePalette", [ct.c_void_p], wt.HANDLE),
        ("CreateEnhMetaFileW", [wt.HANDLE, wt.LPCWSTR, ct.c_void_p, wt.LPCWSTR], wt.HANDLE),
        ("CloseEnhMetaFile", [wt.HANDLE], wt.HANDLE),
        ("CreateMetaFileW", [wt.LPCWSTR], wt.HANDLE),
        ("CloseMetaFile", [wt.HANDLE], wt.HANDLE))
    for name, args, result in signatures:
        function = getattr(api.gdi, name)
        function.argtypes, function.restype = args, result
    def owned(format, handle):
        if not handle:
            raise OSError("Public GDI fixture creation failed")
        value = StoredFormat(format, handle, 0, api)
        sources.append(value)
        return value
    def bits(format, handle):
        if format in (2, 0x82):
            bitmap = Bitmap()
            assert api.gdi.GetObjectW(handle, ct.sizeof(bitmap), ct.byref(bitmap)) == ct.sizeof(bitmap)
            size, reader = bitmap.width_bytes * abs(bitmap.height), api.gdi.GetBitmapBits
            buffer = ct.create_string_buffer(size)
            assert reader(handle, size, buffer) == size
            return buffer.raw
        if format == 9:
            buffer = ct.create_string_buffer(8)
            assert api.gdi.GetPaletteEntries(handle, 0, 2, buffer) == 2
            return buffer.raw
        if format in (14, 0x8E):
            reader = api.gdi.GetEnhMetaFileBits
        elif format in (3, 0x83):
            handle, reader = api._picture(handle).metafile, api.gdi.GetMetaFileBitsEx
        else:
            pointer = api.kernel.GlobalLock(handle)
            if not pointer:
                raise OSError("Public memory fixture could not be read")
            try:
                return ct.string_at(pointer, api.kernel.GlobalSize(handle))
            finally:
                api.kernel.GlobalUnlock(handle)
        size = reader(handle, 0, None)
        buffer = ct.create_string_buffer(size)
        assert reader(handle, size, buffer) == size
        return buffer.raw
    try:
        for format, data in ((13, "public fixture\0".encode("utf-16-le")),
                             (0xC001, b"{\\rtf1 public rich fixture}\0")):
            sources.append(api.memory(format, data))
        pixels = ct.create_string_buffer(bytes((0, 0, 255, 0, 0, 255, 0, 0,
                                               255, 0, 0, 0, 255, 255, 255, 0)))
        owned(2, api.gdi.CreateBitmap(2, 2, 1, 32, pixels))
        palette = ct.create_string_buffer(b"\0\3\2\0\0\0\0\0\xff\xff\xff\0")
        owned(9, api.gdi.CreatePalette(palette))
        owned(14, api.gdi.CloseEnhMetaFile(api.gdi.CreateEnhMetaFileW(None, None, None, None)))
        metafile = api.gdi.CloseMetaFile(api.gdi.CreateMetaFileW(None))
        if not metafile:
            raise OSError("Public metafile fixture creation failed")
        try:
            sources.append(api.memory(3, bytes(MetafilePicture(1, 20, 20, metafile))))
        except BaseException:
            api.gdi.DeleteMetaFile(metafile)
            raise
        rows, expected = [], []
        for source in sources:
            formats = {2: (2, 0x82), 3: (3, 0x83), 14: (14, 0x8E)}.get(source.format, (source.format,))
            for format in formats:
                duplicate = api.duplicate(format, source.handle)
                copies.append(duplicate)
                data = bits(format, source.handle)
                assert data == bits(format, duplicate.handle)
                expected.append(data)
                rows.append({"format": format, "bytes": duplicate.size, "exact": True})
        if on_live is not None:
            on_live()
        for source in sources:
            source.close()
        for copy, data, row in zip(copies, expected, rows):
            assert bits(copy.format, copy.handle) == data
            row["survives_source_release"] = True
        return rows
    finally:
        for value in reversed(copies + sources):
            value.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "clipboard_accessed": False, "input_injected": False, "fixtures": "public in-memory objects only"}
    try:
        api = ClipboardHandles()
        user = ct.WinDLL("user32", use_last_error=True)
        user.GetGuiResources.argtypes, user.GetGuiResources.restype = [wt.HANDLE, wt.DWORD], wt.DWORD
        api.kernel.GetCurrentProcess.restype = wt.HANDLE
        process = api.kernel.GetCurrentProcess()
        def count():
            ct.set_last_error(0)
            value = user.GetGuiResources(process, 0)
            if not value and ct.get_last_error():
                raise OSError("GDI resource count is unavailable")
            return value
        roundtrip()  # Prime native resource caches before the baseline.
        report["gdi_before"] = count()
        live = []
        for _ in range(10):
            report["formats"] = roundtrip(on_live=lambda: live.append(count()))
        report["gdi_live_min"], report["gdi_live_max"] = min(live), max(live)
        report["gdi_after"] = count()
        report["iterations"] = 10
    except Exception as error:
        report["error_type"] = type(error).__name__
    report["probe_complete"] = bool(not report.get("error_type") and len(report.get("formats", [])) == 9
        and report["gdi_live_min"] > report["gdi_before"] == report["gdi_after"])
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
