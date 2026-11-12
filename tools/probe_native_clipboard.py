"""Exercise real Windows clipboard transactions on a separate, invisible window station."""

import argparse
import ctypes as ct
import hashlib
import json
import struct
import subprocess
import time
import uuid
from contextlib import contextmanager
from ctypes import wintypes as wt
from pathlib import Path
from types import SimpleNamespace


@contextmanager
def isolated_clipboard(report):
    user, kernel = ct.WinDLL("user32", use_last_error=True), ct.WinDLL("kernel32", use_last_error=True)
    signatures = (
        ("GetProcessWindowStation", [], wt.HANDLE), ("GetThreadDesktop", [wt.DWORD], wt.HANDLE),
        ("CreateWindowStationW", [wt.LPCWSTR, wt.DWORD, wt.DWORD, ct.c_void_p], wt.HANDLE),
        ("SetProcessWindowStation", [wt.HANDLE], wt.BOOL),
        ("CreateDesktopW", [wt.LPCWSTR, wt.LPCWSTR, ct.c_void_p, wt.DWORD, wt.DWORD, ct.c_void_p], wt.HANDLE),
        ("SetThreadDesktop", [wt.HANDLE], wt.BOOL), ("CloseDesktop", [wt.HANDLE], wt.BOOL),
        ("CloseWindowStation", [wt.HANDLE], wt.BOOL))
    for name, args, result in signatures:
        function = getattr(user, name)
        function.argtypes, function.restype = args, result
    kernel.GetCurrentThreadId.restype = wt.DWORD
    old_station, old_desktop = user.GetProcessWindowStation(), user.GetThreadDesktop(kernel.GetCurrentThreadId())
    station = desktop = None
    try:
        station = user.CreateWindowStationW("SaydraftQA_" + uuid.uuid4().hex, 1, 0x2F, None)
        if not station or not user.SetProcessWindowStation(station):
            raise OSError(f"Private window station unavailable: {ct.get_last_error()}")
        desktop = user.CreateDesktopW("SaydraftQA", None, None, 0, 0x83, None)
        if not desktop or not user.SetThreadDesktop(desktop):
            raise OSError(f"Private desktop unavailable: {ct.get_last_error()}")
        report["isolated_window_station"] = user.GetProcessWindowStation() != old_station
        assert report["isolated_window_station"]
        yield
    finally:
        restored = bool(user.SetProcessWindowStation(old_station) and user.SetThreadDesktop(old_desktop))
        report["private_desktop_closed"] = bool(not desktop or user.CloseDesktop(desktop))
        report["private_station_closed"] = bool(not station or user.CloseWindowStation(station))
        report["original_surface_restored"] = restored
        if not (restored and report["private_desktop_closed"] and report["private_station_closed"]):
            raise OSError("Private test surface did not retire")


def replay(output, report, *, factory=None, start_guard=lambda api: None, marker_guard=lambda api: None,
           clear_after=True):
    # Import GUI-capable application modules only after isolation has succeeded.
    from saydraft.core.interfaces import TargetContext
    from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
    from saydraft.dictation import DictationContext
    from saydraft.history import DictationHistoryStore
    from saydraft.insert._clipboard_win32 import NativeClipboardApi
    from saydraft.insert.clipboard_win import WindowsClipboard
    from saydraft.insert.inserter import Inserter

    factory = factory or NativeClipboardApi
    api, clipboard, delivered = factory(), WindowsClipboard(api_factory=factory), []
    api.kernel.GetCurrentProcess.restype = wt.HANDLE
    api.user.GetGuiResources.argtypes, api.user.GetGuiResources.restype = [wt.HANDLE, wt.DWORD], wt.DWORD
    process = api.kernel.GetCurrentProcess()
    def gdi():
        ct.set_last_error(0)
        value = api.user.GetGuiResources(process, 0)
        if not value and ct.get_last_error():
            raise OSError("GDI count unavailable")
        return value
    def read(format):
        handle = api.get(format)
        size = api.kernel.GlobalSize(handle)
        if not 0 < size <= 64 * 1024 * 1024:
            raise OSError("Public clipboard fixture is unreadable")
        pointer = api.kernel.GlobalLock(handle)
        if not pointer:
            raise OSError("Public clipboard fixture is unreadable")
        try:
            return ct.string_at(pointer, size)
        finally:
            api.kernel.GlobalUnlock(handle)
    rtf = api.user.RegisterClipboardFormatW("Rich Text Format")
    fixtures = {rtf: br"{\rtf1 public \b rich\b0 text}" + bytes(1),
        8: struct.pack("<IiiHHIIiiII", 40, 1, 1, 1, 32, 0, 4, 0, 0, 0, 0) + bytes((0, 0, 255, 0)),
        13: "Public copied text\0".encode("utf-16-le")}
    history = DictationHistoryStore(output / "history.db")
    before = gdi()
    try:
        report["stage"] = "publish_public_fixtures"
        with api.window() as hwnd, api.opened(hwnd):
            start_guard(api)
            api.empty()
            for format in api.privacy:
                api.put(api.memory(format, bytes(4)))
            for format, data in fixtures.items():
                api.put(api.memory(format, data))
        with api.window() as hwnd, api.opened(hwnd):
            original = {format: read(format) for format in fixtures}
        def paste(key):
            report["stage"] = "read_private_dictation_and_history"
            assert key == "ctrl+v" and len(history.list_recent(limit=20)) == len(delivered) + 1
            with api.window() as hwnd, api.opened(hwnd):
                assert all(read(format) == bytes(4) for format in api.privacy[:3])
                assert read(13).decode("utf-16-le").rstrip("\0") == "Public dictation fixture"
            delivered.append(True)
        def no_typing(text):
            raise AssertionError("Native transaction unexpectedly fell back to typing")
        inserter = Inserter(clipboard=clipboard, keyboard=SimpleNamespace(send=paste, write=no_typing),
            focus_provider=lambda: 123, delivery_guard=lambda target: "", sleep=lambda delay: None)
        processor = TranscriptProcessor(cleaner=SimpleNamespace(process_transcript=lambda text, context: text),
            formatter=IdentityFormatter(), history=history, inserter=inserter)
        for _ in range(10):
            report["stage"] = "dictation_transaction"
            with api.window() as hwnd, api.opened(hwnd):
                marker_guard(api)
            result = processor.process("Public dictation fixture", target=TargetContext(123, "Fixture"),
                context=DictationContext(mode="raw", profile="notes"), model="clipboard-fixture")
            report["last_insertion"] = {"status": result.insertion.status, "method": result.insertion.method,
                                         "reason": result.insertion.reason}
            assert result.insertion.status == "inserted" and result.insertion.method == "paste"
            assert not result.insertion.clipboard_pending and clipboard.pending is None
            with api.window() as hwnd, api.opened(hwnd):
                marker_guard(api)
                assert all(read(format) == data for format, data in original.items())
        report["stage"] = "private_history_copy"
        clipboard.setText("Public History copy")
        with api.window() as hwnd, api.opened(hwnd):
            assert all(read(format) == bytes(4) for format in api.privacy[:3])
            assert read(13).decode("utf-16-le").rstrip("\0") == "Public History copy"
        report.update(iterations=10, deliveries=len(delivered), history_rows=len(history.list_recent(limit=20)),
            exact_restored_formats=len(original), private_copy_verified=True,
            fixture_sha256={str(format): hashlib.sha256(data).hexdigest() for format, data in original.items()})
    finally:
        if clear_after:
            with api.window() as hwnd, api.opened(hwnd):
                api.empty()  # Release only this probe's private clipboard objects.
        report["gdi_before"], report["gdi_after_replay"] = before, gdi()


def fingerprint(api, copy):
    from saydraft.insert.clipboard_handles import _BASE_FORMAT, Bitmap
    kind, handle, prefix = _BASE_FORMAT.get(copy.format, copy.format), copy.handle, b""
    if kind == 2:
        api.gdi.GetBitmapBits.argtypes, api.gdi.GetBitmapBits.restype = [wt.HANDLE, wt.LONG, ct.c_void_p], wt.LONG
        bitmap = Bitmap()
        assert api.gdi.GetObjectW(handle, ct.sizeof(bitmap), ct.byref(bitmap)) == ct.sizeof(bitmap)
        prefix = struct.pack("<iiiiHH", bitmap.type, bitmap.width, bitmap.height,
                             bitmap.width_bytes, bitmap.planes, bitmap.bits_pixel)
        size, reader = bitmap.width_bytes * abs(bitmap.height), api.gdi.GetBitmapBits
    elif kind == 9:
        count = api.gdi.GetPaletteEntries(handle, 0, 0, None)
        buffer = ct.create_string_buffer(count * 4)
        assert api.gdi.GetPaletteEntries(handle, 0, count, buffer) == count
        return hashlib.sha256(buffer.raw).digest()
    elif kind in (3, 14):
        if kind == 3:
            picture = api._picture(handle)
            handle = picture.metafile
            prefix = struct.pack("<iii", picture.mapping_mode, picture.x_extent, picture.y_extent)
        reader = api.gdi.GetMetaFileBitsEx if kind == 3 else api.gdi.GetEnhMetaFileBits
        size = reader(handle, 0, None)
    else:
        size = api.kernel.GlobalSize(handle)
        assert 0 < size <= 64 * 1024 * 1024
        pointer = api.kernel.GlobalLock(handle)
        assert pointer
        try:
            return hashlib.sha256(ct.string_at(pointer, size)).digest()
        finally:
            api.kernel.GlobalUnlock(handle)
    buffer = ct.create_string_buffer(size)
    assert reader(handle, size, buffer) == size
    return hashlib.sha256(prefix + buffer.raw).digest()


def backed_up_replay(output, report):
    from saydraft.insert._clipboard_win32 import NativeClipboardApi
    from saydraft.insert.clipboard_win import Snapshot, WindowsClipboard
    marker, nonce = None, uuid.uuid4().bytes
    def factory():
        nonlocal marker
        api = NativeClipboardApi()
        marker = api.user.RegisterClipboardFormatW("Saydraft.NativeClipboardProbe.Marker")
        assert marker
        memory = api.memory
        api.memory = lambda format, data: memory(format, nonce if format == marker else data)
        api.privacy = (*api.privacy, marker)
        opened = api.opened
        @contextmanager
        def observed(hwnd):
            with opened(hwnd):
                try:
                    yield
                finally:
                    before_close = api.sequence()
            after_close = api.sequence()
            key = f"delta={(after_close - before_close) & 0xFFFFFFFF},owned={api.owner() == hwnd}"
            counts = report.setdefault("close_observation_counts", {})
            counts[key] = counts.get(key, 0) + 1
        api.opened = observed
        return api
    api, original, expected, sequence = factory(), None, {}, 0
    def ours(current):
        handle = current.get(marker)
        if not handle or current.kernel.GlobalSize(handle) != len(nonce):
            return False
        pointer = current.kernel.GlobalLock(handle)
        if not pointer:
            return False
        try:
            return ct.string_at(pointer, len(nonce)) == nonce
        finally:
            current.kernel.GlobalUnlock(handle)
    def start(current):
        assert current.sequence() == sequence, "Clipboard changed before the probe began"
    def guard(current):
        assert ours(current), "A new user copy superseded the probe"
    report["owner_clipboard_accessed"], report["backed_up_mode"] = True, True
    try:
        with api.window() as hwnd, api.opened(hwnd):
            assert marker not in list(api.formats()), "Another clipboard probe is active"
            original = Snapshot.take(api)
            assert not original.skipped, "Owner clipboard could not be backed up completely"
            expected = {copy.format: fingerprint(api, copy) for copy in original.copies}
            sequence = api.sequence()
        replay(output, report, factory=factory, start_guard=start, marker_guard=guard, clear_after=False)
    finally:
        if original is not None:
            try:
                with api.window() as hwnd:
                    started, announced = time.monotonic(), False
                    while True:
                        try:
                            with api.opened(hwnd):
                                if not (ours(api) or api.owner() == hwnd):
                                    report["new_user_copy_preserved"] = True
                                    break
                                assert WindowsClipboard()._restore_locked(api, original), "Owner restoration failed"
                                restored = Snapshot.take(api)
                                try:
                                    actual = {copy.format: fingerprint(api, copy) for copy in restored.copies}
                                    assert not restored.skipped and actual == expected, "Owner clipboard verification failed"
                                    report["owner_clipboard_restored_exactly"] = True
                                    break
                                finally:
                                    restored.close()
                        except (Exception, KeyboardInterrupt):
                            report["owner_restore_retries"] = report.get("owner_restore_retries", 0) + 1
                            if time.monotonic() - started > 30 and not announced:
                                print("Waiting to restore the clipboard; complete backup remains in RAM.", flush=True)
                                announced = True
                            time.sleep(.1)
            finally:
                original.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backed-up-clipboard", action="store_true",
                        help="Use a complete RAM backup and probe marker on the current clipboard")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "owner_clipboard_accessed": False, "input_injected": False, "microphone_used": False,
        "asr_performed": False, "win_v_acceptance_performed": False, "delivery": "clipboard-reading stub only"}
    try:
        if args.backed_up_clipboard:
            backed_up_replay(args.output, report)
        else:
            with isolated_clipboard(report):
                replay(args.output, report)
    except Exception as error:
        report["error_type"], report["error"] = type(error).__name__, str(error)
    report["probe_complete"] = bool(not report.get("error_type") and report.get("deliveries") == 10
        and report.get("history_rows") == 10 and report.get("exact_restored_formats") == 3
        and report.get("private_copy_verified") and (report.get("owner_clipboard_restored_exactly")
        if args.backed_up_clipboard else report.get("isolated_window_station") and report.get("private_desktop_closed")
        and report.get("private_station_closed") and report.get("original_surface_restored")
        and report.get("gdi_before") == report.get("gdi_after_replay")))
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
