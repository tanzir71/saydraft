"""Format-aware ownership, native-size bounds and allocation failure cleanup."""

import ctypes as ct
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from saydraft.insert.clipboard_handles import (MAX_SNAPSHOT_BYTES, Bitmap, ClipboardHandles,
    ClipboardUnavailable, MetafilePicture, SnapshotTooLarge, StoredFormat)


def api():
    instance = ClipboardHandles.__new__(ClipboardHandles)
    calls = []
    picture = MetafilePicture(1, 100, 100, 41)
    def bitmap(handle, size, pointer):
        assert size == ct.sizeof(Bitmap)
        pointer._obj.width, pointer._obj.height, pointer._obj.width_bytes = 10, 20, 40
        return size
    def duplicate(handle, kind, flags):
        calls.append(("duplicate", handle, kind, flags))
        return 101
    instance.kernel = SimpleNamespace(GlobalSize=lambda handle: 128,
        GlobalLock=lambda handle: ct.addressof(picture),
        GlobalUnlock=lambda handle: calls.append(("unlock", handle)),
        GlobalFree=lambda handle: calls.append(("global_free", handle)))
    instance.gdi = SimpleNamespace(GetObjectW=bitmap, GetPaletteEntries=lambda *args: 256,
        GetEnhMetaFileBits=lambda *args: 256, GetMetaFileBitsEx=lambda *args: 128,
        CopyEnhMetaFileW=lambda handle, path: calls.append(("copy_enhanced", handle, path)) or 102,
        DeleteObject=lambda handle: calls.append(("delete_object", handle)) or True,
        DeleteEnhMetaFile=lambda handle: calls.append(("delete_enhanced", handle)) or True,
        DeleteMetaFile=lambda handle: calls.append(("delete_metafile", handle)) or True)
    instance.ole = SimpleNamespace(OleDuplicateData=duplicate)
    instance._test_picture = picture  # Keep the fake lock buffer alive.
    return instance, calls


@pytest.mark.parametrize("format,kind,size,cleanup", [(13, 13, 128, "global_free"),
    (0xC001, 0xC001, 128, "global_free"), (0x300, 0x300, 128, "global_free"),
    (2, 2, 800, "delete_object"), (0x82, 2, 800, "delete_object"),
    (9, 9, 1028, "delete_object"), (14, 14, 256, "delete_enhanced"),
    (0x8E, 14, 256, "delete_enhanced"),
    (3, 3, ct.sizeof(MetafilePicture) + 128, "global_free"),
    (0x83, 3, ct.sizeof(MetafilePicture) + 128, "global_free")])
def test_duplicate_and_free_use_actual_handle_type_including_display_variants(format, kind, size, cleanup):
    handles, calls = api()
    saved = handles.duplicate(format, 1)
    assert saved.size == size and saved.format == format and saved.handle != 1
    if kind == 14:
        assert ("copy_enhanced", 1, None) in calls
        assert not any(row[0] == "duplicate" for row in calls)
    else:
        assert ("duplicate", 1, kind, 2) in calls
    copy = saved.handle
    saved.close()
    assert (cleanup, copy) in calls and saved.handle == 0
    if kind == 3:
        assert ("delete_metafile", 41) in calls
    before = list(calls)
    saved.close()
    assert calls == before  # Never double free.


def test_transferred_memory_is_not_freed_by_the_previous_owner():
    handles, calls = api()
    saved = handles.duplicate(13, 1)
    saved.transfer()
    saved.close()
    assert not any(row[0] == "global_free" for row in calls)


@pytest.mark.parametrize("format", [0, -1, 0x10000, True, "13"])
def test_invalid_format_identifiers_cannot_wrap_into_a_different_native_format(format):
    handles, calls = api()
    with pytest.raises(ClipboardUnavailable, match="identifier"):
        handles.duplicate(format, 1)
    assert not calls


def test_cleanup_failures_are_reported_without_a_second_free_of_the_same_handle():
    handles, calls = api()
    saved = handles.duplicate(2, 1)
    handles.gdi.DeleteObject = lambda handle: False
    with pytest.raises(ClipboardUnavailable, match="cleanup"):
        saved.close()
    assert saved.handle == 0
    saved.close()


@pytest.mark.parametrize("format", [0x80, 0x200, 0x2FF])
def test_opaque_owner_handles_are_refused_without_dereferencing_them(format):
    handles, calls = api()
    with pytest.raises(ClipboardUnavailable, match="Opaque"):
        handles.duplicate(format, 1)
    assert not calls


@pytest.mark.parametrize("remaining", [0, 127, MAX_SNAPSHOT_BYTES + 1])
def test_snapshot_limit_is_enforced_before_allocating_a_duplicate(remaining):
    handles, calls = api()
    with pytest.raises(SnapshotTooLarge):
        handles.duplicate(13, 1, remaining=remaining)
    assert not calls


def test_exact_limit_is_allowed_and_allocation_or_render_failures_are_distinct():
    handles, calls = api()
    handles.kernel.GlobalSize = lambda handle: MAX_SNAPSHOT_BYTES
    saved = handles.duplicate(13, 1)
    assert saved.size == MAX_SNAPSHOT_BYTES
    saved.close()
    handles.kernel.GlobalSize = lambda handle: 0
    with pytest.raises(ClipboardUnavailable, match="rendered"):
        handles.duplicate(13, 1)
    handles.kernel.GlobalSize = lambda handle: 128
    for copy in (0, 1):
        handles.ole.OleDuplicateData = lambda *args: copy
        with pytest.raises(ClipboardUnavailable, match="duplicated"):
            handles.duplicate(13, 1)
    assert not any(row[0] == "global_free" and row[1] == 1 for row in calls)


@pytest.mark.parametrize("kind", [2, 3, 9, 14])
def test_unrenderable_gdi_objects_are_never_duplicated(kind):
    handles, calls = api()
    handles.gdi.GetObjectW = lambda *args: 0
    handles.gdi.GetPaletteEntries = lambda *args: 0
    handles.gdi.GetEnhMetaFileBits = lambda *args: 0
    handles.kernel.GlobalSize = lambda *args: 0
    with pytest.raises(ClipboardUnavailable):
        handles.duplicate(kind, 1)
    assert not calls


def test_failed_metafile_lock_is_not_read_or_unlocked():
    handles, calls = api()
    handles.kernel.GlobalLock = lambda *args: 0
    with pytest.raises(ClipboardUnavailable):
        handles.duplicate(3, 1)
    assert not calls


def test_new_global_memory_has_exact_payload_and_frees_failed_locks():
    handles, calls = api()
    payload = b"public fixture\0"
    buffer = ct.create_string_buffer(len(payload))
    handles.kernel.GlobalAlloc = lambda flags, size: (calls.append(("alloc", flags, size)) or 200)
    handles.kernel.GlobalLock = lambda handle: ct.addressof(buffer)
    saved = handles.memory(13, payload)
    assert isinstance(saved, StoredFormat) and buffer.raw == payload
    assert ("alloc", 2, len(payload)) in calls and ("unlock", 200) in calls
    saved.close()
    handles.kernel.GlobalLock = lambda handle: 0
    with pytest.raises(ClipboardUnavailable):
        handles.memory(13, payload)
    assert calls.count(("global_free", 200)) == 2
    handles.kernel.GlobalAlloc = lambda *args: 0
    with pytest.raises(ClipboardUnavailable):
        handles.memory(13, payload)


@pytest.mark.parametrize("case", ["null", "text", "empty", "oversize"])
def test_invalid_or_oversize_payloads_are_refused_before_allocating(case):
    handles, calls = api()
    data = b"a" * (MAX_SNAPSHOT_BYTES + 1) if case == "oversize" else {
        "null": None, "text": "text", "empty": b""}[case]
    with pytest.raises(ClipboardUnavailable):
        handles.memory(13, data)
    assert not calls


@pytest.mark.skipif(os.name != "nt", reason="Windows native clipboard-object ABI")
def test_native_format_copies_survive_source_release_and_retire_all_gdi_handles(tmp_path):
    output = tmp_path / "native-objects"
    completed = subprocess.run([sys.executable, "-m", "tools.probe_clipboard_handles", "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0 and report["probe_complete"], report
    assert not report["clipboard_accessed"] and not report["input_injected"]
    assert len(report["formats"]) == 9 and report["iterations"] == 10
    assert all(row["exact"] and row["survives_source_release"] for row in report["formats"])
    assert report["gdi_live_min"] > report["gdi_before"] == report["gdi_after"]
