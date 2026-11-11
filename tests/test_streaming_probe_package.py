import hashlib
import io
import tarfile

import pytest

from tools import probe_streaming as probe


def package_fixture(tmp_path, monkeypatch, *, linked_encoder=False):
    archive = tmp_path / "fixture.tar.bz2"
    with tarfile.open(archive, "w:bz2") as package:
        for name in probe.FILES:
            member = tarfile.TarInfo(f"{probe.PREFIX}/{name}")
            content = b"fixture bytes"
            if linked_encoder and name == "encoder.int8.onnx":
                member.type, member.linkname = tarfile.SYMTYPE, "../owner.txt"
                package.addfile(member)
            else:
                member.size = len(content)
                package.addfile(member, io.BytesIO(content))
        outside = tarfile.TarInfo("../owner.txt")
        outside.size = 9
        package.addfile(outside, io.BytesIO(b"overwrite"))
    monkeypatch.setattr(probe, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    return archive


def test_unverified_archive_cannot_create_a_model_directory(tmp_path):
    archive = tmp_path / "untrusted"
    archive.write_bytes(b"untrusted archive")
    with pytest.raises(ValueError, match="pinned GitHub asset"):
        probe.extract_package(archive, tmp_path / "model")
    assert not (tmp_path / "model").exists()


def test_extraction_writes_only_declared_regular_files_and_preserves_outside_data(tmp_path, monkeypatch):
    archive = package_fixture(tmp_path, monkeypatch)
    owner = tmp_path / "owner.txt"
    owner.write_bytes(b"original")
    receipt = probe.extract_package(archive, tmp_path / "model")
    assert {item["path"] for item in receipt["files"]} == set(probe.FILES)
    assert owner.read_bytes() == b"original"
    assert all((tmp_path / "model" / name).read_bytes() == b"fixture bytes" for name in probe.FILES)


def test_named_links_are_rejected_instead_of_followed(tmp_path, monkeypatch):
    archive = package_fixture(tmp_path, monkeypatch, linked_encoder=True)
    owner = tmp_path / "owner.txt"
    owner.write_bytes(b"original")
    with pytest.raises(ValueError, match="Unexpected package entry"):
        probe.extract_package(archive, tmp_path / "model")
    assert owner.read_bytes() == b"original"
    assert not (tmp_path / "model" / "encoder.int8.onnx").exists()


def test_existing_destination_is_never_overwritten(tmp_path, monkeypatch):
    archive = package_fixture(tmp_path, monkeypatch)
    directory = tmp_path / "existing"
    directory.mkdir()
    (directory / "owner.txt").write_bytes(b"original")
    with pytest.raises(FileExistsError):
        probe.extract_package(archive, directory)
    assert (directory / "owner.txt").read_bytes() == b"original"
