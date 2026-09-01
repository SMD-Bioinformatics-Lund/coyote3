"""Tests for safe staging of uploaded ingest ZIP archives."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from api.application.ingest.upload_archive import extract_uploaded_archive


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
