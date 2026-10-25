"""Stage uploaded bundles and resolve inputs exclusively against their archive."""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Protocol

from coyote3.application.ingest.parsers import runtime_file_path
from coyote3.application.ingest.service import InternalIngestService
from coyote3.application.ingest.upload_archive import UploadedFileIndex, extract_uploaded_archive
from coyote3.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS


class BinaryUpload(Protocol):
    """Named binary stream supplied by an upload transport."""

    filename: str | None
    file: BinaryIO


def save_upload(upload: BinaryUpload, destination: Path) -> str:
    """Copy the remaining upload bytes to disk and compute their SHA-256 digest.

    Args:
        upload: Upload read from its current file position in one-mebibyte chunks.
        destination: File to create or truncate; its parent directory must exist.

    Returns:
        Hexadecimal SHA-256 digest of the bytes copied.

    Raises:
        OSError: If opening, reading, writing, or closing a file fails.

    Notes:
        Consumes the upload stream without closing it. A failed copy may leave
        a truncated or partially written destination file.
    """
    digest = sha256()
    with destination.open("wb") as handle:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def prepare_uploaded_bundle(
    *,
    yaml_file: BinaryUpload,
    data_archive: BinaryUpload | None,
    staging_dir: Path,
    ingest_service: InternalIngestService,
    preflight=None,
) -> dict:
    """Parse a manifest and resolve declared paths against one uploaded ZIP archive."""
    logger = logging.getLogger(__name__)
    logger.info("Parsing YAML manifest: %s", yaml_file.filename)
    yaml_content = yaml_file.file.read().decode("utf-8")
    source_payload = ingest_service.parse_yaml_payload(yaml_content)
    if preflight is not None:
        logger.info("Checking sample permissions and duplicate-name policy")
        preflight(source_payload)
    logger.info("Resolving ASP expected and required files")
    expected_keys, required_keys = ingest_service._assay_file_policy(
        assay_name=source_payload.get("asp_id"),
        asp_category=source_payload.get("asp_category"),
    )

    archive_index = UploadedFileIndex(exact={}, basename={}, checksums={})
    if data_archive is not None:
        if not data_archive.filename:
            raise ValueError("data_archive must include a filename")
        archive_path = staging_dir / Path(str(data_archive.filename)).name
        logger.info("Staging and extracting archive: %s", data_archive.filename)
        save_upload(data_archive, archive_path)
        archive_index = extract_uploaded_archive(
            archive_path=archive_path,
            destination=staging_dir / "files",
        )

    runtime_files: dict[str, str] = {}
    checksums: dict[str, str] = {}
    missing: list[str] = []
    ambiguous: list[str] = []
    warnings: list[str] = []
    for key in SAMPLE_SOURCE_PATH_KEYS:
        raw_value = runtime_file_path(source_payload, key)
        if not raw_value or not raw_value.strip():
            continue
        path_value = raw_value.strip()
        if key not in expected_keys:
            warnings.append(
                f"Ignored '{key}': ASP '{source_payload.get('asp_id')}' does not accept this file."
            )
            source_payload.pop(key, None)
            for container in ("files", "_runtime_files", "_uploaded_file_checksums"):
                if isinstance(source_payload.get(container), dict):
                    source_payload[container].pop(key, None)
            continue
        resolved = archive_index.exact.get(path_value)
        if not resolved:
            basename = Path(path_value).name
            if basename in archive_index.basename and archive_index.basename[basename] is None:
                ambiguous.append(f"{key}:{path_value}")
                continue
            resolved = archive_index.basename.get(basename)
        if resolved:
            runtime_files[key] = resolved
            checksum = archive_index.checksums.get(resolved)
            if checksum:
                checksums[key] = checksum
            continue
        missing.append(f"{key}:{path_value}")
        # Uploaded manifests may only name uploaded files, including optional inputs.
        source_payload.pop(key, None)
        for container in ("files", "_runtime_files", "_uploaded_file_checksums"):
            if isinstance(source_payload.get(container), dict):
                source_payload[container].pop(key, None)

    if ambiguous:
        raise ValueError(
            "Ambiguous archive filenames for YAML references: "
            + ", ".join(sorted(ambiguous))
            + ". Use unique basenames or archive paths matching the YAML values."
        )
    required_missing = [entry for entry in missing if entry.split(":", 1)[0] in required_keys]
    if required_missing:
        raise ValueError(
            "Missing required files for YAML references: "
            + ", ".join(sorted(required_missing))
            + ". Provide one ZIP containing matching files."
        )
    source_payload["_runtime_files"] = runtime_files
    source_payload["_uploaded_file_checksums"] = checksums
    if warnings:
        source_payload["_ingest_warnings"] = warnings
        for warning in warnings:
            logger.warning("%s", warning)
    logger.info(
        "File resolution complete: readable=%s, missing optional=%s", sorted(runtime_files), missing
    )
    return source_payload
