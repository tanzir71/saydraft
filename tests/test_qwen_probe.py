import hashlib
import io
import tarfile

import pytest

from tools import probe_qwen_asr as probe


def archive_fixture(tmp_path, monkeypatch, *, missing=False, linked=False, duplicate=False):
    path = tmp_path / "package.tar.bz2"
    with tarfile.open(path, "w:bz2") as archive:
        for name in probe.FILES[1:] if missing else probe.FILES:
            member = tarfile.TarInfo(f"{probe.PREFIX}/{name}")
            if linked and name == probe.FILES[0]:
                member.type, member.linkname = tarfile.SYMTYPE, "../owner-data"
                archive.addfile(member)
            else:
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
                if duplicate and name == probe.FILES[0]:
                    archive.addfile(member, io.BytesIO(b"y"))
        member = tarfile.TarInfo("../owner-data")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"!"))
    monkeypatch.setattr(probe, "ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    return path


def test_qwen_extraction_writes_only_declared_payloads_and_keeps_existing_paths(tmp_path, monkeypatch):
    archive = archive_fixture(tmp_path, monkeypatch)
    owner = tmp_path / "owner-data"
    owner.write_bytes(b"owner")
    directory = tmp_path / "new-model"
    receipt = probe.extract_package(archive, directory)
    assert owner.read_bytes() == b"owner"
    assert {file["path"] for file in receipt["files"]} == set(probe.FILES)
    assert all((directory / name).read_bytes() == b"x" for name in probe.FILES)
    with pytest.raises(FileExistsError):
        probe.extract_package(archive, directory)


@pytest.mark.parametrize("case", ["missing", "linked", "duplicate"])
def test_qwen_extraction_rejects_incomplete_linked_or_duplicate_payloads(tmp_path, monkeypatch, case):
    archive = archive_fixture(tmp_path, monkeypatch, **{case: True})
    with pytest.raises((ValueError, FileExistsError)):
        probe.extract_package(archive, tmp_path / "new-model")
    assert not (tmp_path / "new-model" / "probe-receipt.json").exists()


def test_qwen_checksum_rejection_creates_no_output_directory(tmp_path, monkeypatch):
    archive = archive_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(probe, "ARCHIVE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="pinned"):
        probe.extract_package(archive, tmp_path / "new-model")
    assert not (tmp_path / "new-model").exists()
