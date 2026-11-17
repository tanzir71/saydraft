"""Pinned archive reads must never extract reports or trust rewritten evidence."""

import hashlib
import gzip
import io
import json
import tarfile

import pytest

from tools import check_cleanup_evidence as evidence


def packed(tmp_path, *, members=None, entries=None):
    raw = json.dumps({"git_commit": "a" * 40}).encode()
    names = ("cpu/report.json", "pro/report.json")
    archive = tmp_path / "evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for name, content, kind in members or [(name, raw, "file") for name in names]:
            member = tarfile.TarInfo(name)
            if kind == "link":
                member.type, member.linkname = tarfile.SYMTYPE, "outside.json"
                output.addfile(member)
            else:
                member.size = len(content)
                output.addfile(member, io.BytesIO(content))
    index = {"schema_version": 2, "source_commit": "a" * 40, "selection_performed": False,
             "archive": archive.name, "archive_sha256": evidence.digest(archive.read_bytes()),
             "reports": entries or [
                 {"report": name, "member": member, "report_sha256": evidence.digest(raw)}
                 for name, member in zip(evidence.PAIR, names)]}
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    return path, index, archive


def write_index(path, index):
    path.write_text(json.dumps(index))


def test_reads_pinned_members_without_creating_extracted_files(tmp_path):
    path, _, _ = packed(tmp_path)
    assert evidence.reports(path, root=tmp_path) == {
        name: {"git_commit": "a" * 40} for name in evidence.PAIR}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["evidence.tar.gz", "index.json"]


def test_changed_archive_is_refused_even_when_report_contents_are_unchanged(tmp_path):
    path, _, archive = packed(tmp_path)
    archive.write_bytes(archive.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="archive bytes changed"):
        evidence.reports(path, root=tmp_path)


def test_rehashed_archive_still_needs_original_report_digest(tmp_path):
    raw = json.dumps({"git_commit": "a" * 40}).encode() + b"\n"
    path, _, _ = packed(tmp_path, members=[(name, raw, "file") for name in ("cpu/report.json", "pro/report.json")])
    with pytest.raises(ValueError, match="Native report bytes changed"):
        evidence.reports(path, root=tmp_path)


@pytest.mark.parametrize("name", ["../outside.tar.gz", "/outside.tar.gz", "C:/outside.tar.gz"])
def test_archive_path_cannot_escape_the_explicit_evidence_root(tmp_path, name):
    path, index, _ = packed(tmp_path)
    index["archive"] = name
    write_index(path, index)
    with pytest.raises(ValueError, match="Unsafe evidence archive"):
        evidence.reports(path, root=tmp_path)


@pytest.mark.parametrize("member", ["../outside.json", "/outside.json", "C:/outside.json"])
def test_member_path_must_be_safe_even_though_nothing_is_extracted(tmp_path, member):
    path, index, _ = packed(tmp_path)
    index["reports"][0]["member"] = member
    write_index(path, index)
    with pytest.raises(ValueError, match="archive report member"):
        evidence.reports(path, root=tmp_path)


def test_duplicate_archive_entries_cannot_replace_pinned_content(tmp_path):
    raw = json.dumps({"git_commit": "a" * 40}).encode()
    path, _, _ = packed(tmp_path, members=[(name, raw, "file") for name in
                         ("cpu/report.json", "pro/report.json", "cpu/report.json")])
    with pytest.raises(ValueError, match="Duplicate or excessive"):
        evidence.reports(path, root=tmp_path)


def test_link_member_cannot_read_another_file(tmp_path):
    raw = json.dumps({"git_commit": "a" * 40}).encode()
    path, _, _ = packed(tmp_path, members=[("cpu/report.json", b"", "link"), ("pro/report.json", raw, "file")])
    with pytest.raises(ValueError, match="Invalid or oversized archive report"):
        evidence.reports(path, root=tmp_path)


def test_oversized_member_is_refused_before_reading_report_json(tmp_path):
    path, _, _ = packed(tmp_path, members=[("cpu/report.json", b" " * (2 * 1024**2 + 1), "file")])
    with pytest.raises(ValueError, match="oversized archive report"):
        evidence.reports(path, root=tmp_path)


def test_missing_member_cannot_earn_evidence_credit(tmp_path):
    raw = json.dumps({"git_commit": "a" * 40}).encode()
    path, _, _ = packed(tmp_path, members=[("cpu/report.json", raw, "file")])
    with pytest.raises(ValueError, match="member missing"):
        evidence.reports(path, root=tmp_path)


def test_unselected_large_member_cannot_bypass_the_unpacking_bound(tmp_path):
    path, index, archive = packed(tmp_path)
    member = tarfile.TarInfo("ignored.bin")
    member.size = 64 * 1024**2 + 1
    with gzip.open(archive, "wb") as output:
        output.write(member.tobuf() + b"\0" * 1024)
    index["archive_sha256"] = evidence.digest(archive.read_bytes())
    write_index(path, index)
    with pytest.raises(ValueError, match="Unpacked evidence archive exceeds bound"):
        evidence.reports(path, root=tmp_path)


def test_same_member_cannot_stand_in_for_both_candidates(tmp_path):
    path, index, _ = packed(tmp_path)
    index["reports"][1]["member"] = index["reports"][0]["member"]
    write_index(path, index)
    with pytest.raises(ValueError, match="duplicate archive report member"):
        evidence.reports(path, root=tmp_path)


def test_original_archived_failures_remain_pinned_when_the_implementation_changes():
    # Historical data stays immutable; current source qualification is a separate
    # check and must become stale when the measured implementation changes.
    folder = evidence.ROOT / "eval/cleanup/results/2026-11-16-qualification"
    policy = evidence.reports(folder / "policy-index.json")
    forced = evidence.reports(folder / "forced-index.json")
    assert forced["qwen08-cpu.json"]["suites"]["golden"]["regressions"] == ["balanced-chat-05"]
    assert len(forced["qwen2-vulkan1.json"]["suites"]["golden"]["regressions"]) == 3
    assert policy["qwen08-cpu.json"]["suites"]["golden"]["accepted_replies"] == 0
    assert policy["qwen2-vulkan1.json"]["suites"]["golden"]["accepted_replies"] == 269


def test_archive_identity_and_reports_are_pinned_independently():
    # This verifies the checked-in pointers, without duplicating/extracting reports.
    index = evidence.load(evidence.POLICY_INDEX)
    archive = evidence.ROOT / index["archive"]
    with archive.open("rb") as source:
        assert hashlib.file_digest(source, "sha256").hexdigest() == index["archive_sha256"]
    assert len(evidence.reports(evidence.POLICY_INDEX)) == 2
