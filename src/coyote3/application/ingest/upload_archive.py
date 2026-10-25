"""Safe ZIP extraction and filename indexing for uploaded ingest bundles."""

from __future__ import annotations

import shutil
import stat
import zipfile
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict

MAX_ARCHIVE_FILES = 1_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 20 * 1024 * 1024 * 1024


class UploadedFileIndex(BaseModel):
    """Index staged files by archive name and basename."""

    model_config = ConfigDict(frozen=True)

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
        paths: dict[Path, zipfile.ZipInfo] = {}
        for member in members:
            relative_path = _validated_member_path(member)
            if relative_path in paths:
                raise ValueError(f"data_archive contains a duplicate path: {member.filename!r}")
            paths[relative_path] = member
            total_bytes += member.file_size
            if total_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "data_archive exceeds the maximum uncompressed size "
                    f"({MAX_ARCHIVE_UNCOMPRESSED_BYTES} bytes)"
                )
        for relative_path in paths:
            if any(parent in paths for parent in relative_path.parents):
                raise ValueError("data_archive contains conflicting file and directory paths")
            target = destination / relative_path
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("data_archive extraction target escapes destination")
            if target.exists():
                raise ValueError("data_archive extraction target already exists")

        for relative_path, member in paths.items():
            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256()
            with archive.open(member) as source, target.open("xb") as output:
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
    """Index a staged file under original and slash-normalized archive names.

    Args:
        index: Mutable exact-name index receiving both aliases.
        name: Archive member name; backslashes are normalized to slashes.
        path: Extracted file path associated with both names.

    Raises:
        ValueError: Either name is already indexed, even for the same path.
    """
    normalized = name.replace("\\", "/")
    if name in index or normalized in index:
        raise ValueError(f"data_archive contains a duplicate path: {name!r}")
    index[name] = path
    index[normalized] = path


def _add_basename_entry(index: dict[str, str | None], name: str, path: str) -> None:
    """Index a basename or mark it ambiguous when it refers to different paths.

    Args:
        index: Mutable basename index; None entries remain ambiguous on later calls.
        name: Extracted member basename.
        path: Staged file path to associate with the basename.
    """
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
        """Wrap a byte reader with an externally owned incremental digest.

        Args:
            source: File-like object whose read method returns bytes.
            digest: Hash object updated with every returned byte chunk.
        """
        self._source = source
        self._digest = digest

    def read(self, size: int = -1) -> bytes:
        """Read bytes and add the returned chunk to the configured digest.

        Args:
            size: Byte limit forwarded to the source; -1 requests all remaining bytes.

        Returns:
            Source bytes unchanged, including an empty chunk at end of input.
        """
        value = self._source.read(size)
        self._digest.update(value)
        return value
