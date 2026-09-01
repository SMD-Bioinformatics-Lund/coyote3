"""Safe ZIP extraction and filename indexing for uploaded ingest bundles."""

from __future__ import annotations

import shutil
import stat
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

MAX_ARCHIVE_FILES = 1_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 20 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class UploadedFileIndex:
    """Index staged files by archive name and basename."""

    exact: dict[str, str]
    basename: dict[str, str | None]
    checksums: dict[str, str]


def extract_uploaded_archive(*, archive_path: Path, destination: Path) -> UploadedFileIndex:
    """Extract a ZIP into destination after validating every archive member."""
    if archive_path.suffix.lower() != ".zip":
        raise ValueError("data_archive must be a .zip file")

    destination.mkdir(parents=True, exist_ok=True)
    exact: dict[str, str] = {}
    basename: dict[str, str | None] = {}
    checksums: dict[str, str] = {}
    total_bytes = 0

    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise ValueError("data_archive is not a valid ZIP file") from exc

    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) > MAX_ARCHIVE_FILES:
            raise ValueError(
                f"data_archive contains too many files ({len(members)}; maximum {MAX_ARCHIVE_FILES})"
            )
        for member in members:
            relative_path = _validated_member_path(member)
            total_bytes += member.file_size
            if total_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "data_archive exceeds the maximum uncompressed size "
                    f"({MAX_ARCHIVE_UNCOMPRESSED_BYTES} bytes)"
                )
            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256()
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(_DigestingReader(source, digest), output)

            resolved = str(target)
            checksums[resolved] = digest.hexdigest()
            _add_index_entry(exact, member.filename, resolved)
            _add_basename_entry(basename, relative_path.name, resolved)

    return UploadedFileIndex(exact=exact, basename=basename, checksums=checksums)


def _validated_member_path(member: zipfile.ZipInfo) -> Path:
    """Return a safe relative archive member path or reject unsafe members."""
    raw_path = member.filename.replace("\\", "/")
    relative_path = Path(raw_path)
    if not raw_path or relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"data_archive contains an unsafe path: {member.filename!r}")
    mode = member.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        raise ValueError(f"data_archive contains a symbolic link: {member.filename!r}")
    return relative_path


def _add_index_entry(index: dict[str, str], name: str, path: str) -> None:
    normalized = name.replace("\\", "/")
    if name in index or normalized in index:
        raise ValueError(f"data_archive contains a duplicate path: {name!r}")
    index[name] = path
    index[normalized] = path


def _add_basename_entry(index: dict[str, str | None], name: str, path: str) -> None:
    existing = index.get(name)
    if existing is None and name in index:
        return
    if existing and existing != path:
        index[name] = None
        return
    index[name] = path


class _DigestingReader:
    """File-like reader that updates a digest as shutil copies archive data."""

    def __init__(self, source, digest) -> None:
        self._source = source
        self._digest = digest

    def read(self, size: int = -1) -> bytes:
        value = self._source.read(size)
        self._digest.update(value)
        return value
