"""Tests for safe staging of uploaded ingest ZIP archives."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from coyote3.application.ingest.upload_archive import extract_uploaded_archive
from coyote3.application.ingest.upload_bundle import prepare_uploaded_bundle


def test_archive_rejects_unsupported_compression_before_extracting(tmp_path):
    """Unsupported ZIP algorithms fail validation before any members are written."""
    path = _archive(tmp_path / "bundle.zip", ("first.txt", b"first"), ("last.txt", b"last"))
    content = bytearray(path.read_bytes())
    local = content.find(b"PK\x03\x04", 4)
    central = content.find(b"PK\x01\x02", content.find(b"PK\x01\x02") + 4)
    content[local + 8 : local + 10] = (99).to_bytes(2, "little")
    content[central + 10 : central + 12] = (99).to_bytes(2, "little")
    path.write_bytes(content)
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="compression"):
        extract_uploaded_archive(archive_path=path, destination=destination)
    assert list(destination.rglob("*")) == []


def test_corrupt_deflate_is_an_invalid_upload(tmp_path):
    """Broken compression streams are user input errors rather than internal failures."""
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("input.txt", b"synthetic" * 100)
    content = bytearray(path.read_bytes())
    data_offset = 30 + len("input.txt")
    content[data_offset] = 0x07  # Reserved DEFLATE block type.
    path.write_bytes(content)
    with pytest.raises(ValueError, match="corrupt"):
        extract_uploaded_archive(archive_path=path, destination=tmp_path / "staged")


@pytest.mark.parametrize("reference", [r"inputs\case.vcf", r"C:\pipeline\case.vcf"])
def test_uploaded_manifest_resolves_windows_paths(tmp_path, reference):
    """Manifest paths use the same separator normalization as archive entries."""
    path = _archive(tmp_path / "source.zip", ("inputs/case.vcf", b"synthetic"))
    service = SimpleNamespace(
        parse_yaml_payload=lambda _: {"asp_id": "synthetic", "vcf_files": reference},
        _assay_file_policy=lambda **_: ({"vcf_files"}, {"vcf_files"}),
    )
    result = prepare_uploaded_bundle(
        yaml_file=SimpleNamespace(filename="sample.yaml", file=BytesIO(b"synthetic")),
        data_archive=SimpleNamespace(filename="bundle.zip", file=BytesIO(path.read_bytes())),
        staging_dir=tmp_path,
        ingest_service=service,
    )
    assert Path(result["_runtime_files"]["vcf_files"]).read_bytes() == b"synthetic"


def _archive(path: Path, *entries: tuple[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return path


def test_extract_uploaded_archive_indexes_unique_basename(tmp_path: Path):
    archive_path = _archive(tmp_path / "bundle.zip", ("inputs/case.vcf", b"vcf"))

    result = extract_uploaded_archive(archive_path=archive_path, destination=tmp_path / "staged")

    assert result.exact["inputs/case.vcf"].endswith("inputs/case.vcf")
    assert result.basename["case.vcf"] == result.exact["inputs/case.vcf"]
    assert result.checksums[result.exact["inputs/case.vcf"]]


def test_archive_rejects_encrypted_members_before_extracting(tmp_path):
    """Password-protected inputs are unsupported and must fail preflight validation."""
    path = _archive(tmp_path / "bundle.zip", ("first.txt", b"first"), ("secret.txt", b"second"))
    content = bytearray(path.read_bytes())
    local = content.find(b"PK\x03\x04", 4)
    central = content.find(b"PK\x01\x02", content.find(b"PK\x01\x02") + 4)
    content[local + 6] |= 1
    content[central + 8] |= 1
    path.write_bytes(content)
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="encrypted"):
        extract_uploaded_archive(archive_path=path, destination=destination)
    assert list(destination.rglob("*")) == []


def test_archive_rejects_corrupt_member_as_invalid_upload(tmp_path: Path):
    """CRC failures in member contents are input errors, not internal server errors."""
    archive_path = _archive(tmp_path / "bundle.zip", ("input.txt", b"synthetic-content"))
    archive_path.write_bytes(
        archive_path.read_bytes().replace(b"synthetic-content", b"corrupted-content")
    )
    with pytest.raises(ValueError, match="corrupt"):
        extract_uploaded_archive(archive_path=archive_path, destination=tmp_path / "staged")


def test_extract_uploaded_archive_rejects_duplicate_member_path(tmp_path: Path):
    archive_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("case.vcf", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("case.vcf", b"second")

    with pytest.raises(ValueError, match="duplicate path"):
        extract_uploaded_archive(archive_path=archive_path, destination=tmp_path / "staged")


def test_extract_uploaded_archive_rejects_unsafe_member_path(tmp_path: Path):
    archive_path = _archive(tmp_path / "unsafe.zip", ("../case.vcf", b"vcf"))

    with pytest.raises(ValueError, match="unsafe path"):
        extract_uploaded_archive(archive_path=archive_path, destination=tmp_path / "staged")


@pytest.mark.parametrize("alias", ["inputs/./case.vcf", "inputs//case.vcf", "inputs\\case.vcf"])
def test_archive_rejects_path_aliases_before_extracting_any_files(tmp_path, alias):
    archive_path = _archive(
        tmp_path / "bundle.zip", ("inputs/case.vcf", b"first"), (alias, b"second")
    )
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="duplicate path"):
        extract_uploaded_archive(archive_path=archive_path, destination=destination)
    assert list(destination.rglob("*")) == []


def test_archive_rejects_file_directory_collision_before_extracting(tmp_path):
    archive_path = _archive(tmp_path / "bundle.zip", ("inputs", b"file"), ("inputs/a", b"a"))
    with pytest.raises(ValueError, match="conflicting"):
        extract_uploaded_archive(archive_path=archive_path, destination=tmp_path / "staged")
    assert list((tmp_path / "staged").rglob("*")) == []
