"""Resolve alignment filenames using ASP folders or the BAM catalog."""

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit


def _filename(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    parsed = urlsplit(raw)
    name = PurePosixPath(parsed.path if parsed.scheme in {"http", "https"} else raw).name
    return "" if name in {".", ".."} else name


def alignment_files_payload(
    sample: dict[str, Any],
    sample_ids: dict[str, str],
    lookup: Callable[[dict[str, str]], dict[str, list[str]]],
    *,
    asp: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prefer ASP folders with explicit filenames; otherwise retain catalog lookup."""
    bams: dict[str, list[str]] = {}
    indexes: dict[str, str] = {}
    settings = (asp or {}).get("igv") or {}
    base = settings.get("base_folder")
    folder = PurePosixPath(base, settings.get("bam_subfolder") or "") if base else None
    missing = {
        role: sid
        for role, sid in sample_ids.items()
        if folder is None or not _filename((sample.get(role) or {}).get("bam"))
    }
    catalog = (lookup(missing) or {}) if missing else {}
    for role, sample_id in sample_ids.items():
        details = sample.get(role) or {}
        bam = _filename(details.get("bam"))
        bai = _filename(details.get("bai"))
        if folder is not None and bam:
            path = str(folder / bam)
            bams[sample_id] = [path]
            if bai:
                indexes[path] = str(folder / bai)
            continue
        for catalog_path in catalog.get(sample_id) or []:
            original = PurePosixPath(catalog_path.replace("\\", "/"))
            path = str(original.with_name(bam)) if bam else str(original)
            paths = bams.setdefault(sample_id, [])
            if path not in paths:
                paths.append(path)
            if bai:
                # Without an explicit BAM, one index cannot select among several files.
                if bam or len(catalog[sample_id]) == 1:
                    indexes[path] = str(original.with_name(bai))
    beds = (
        [str(PurePosixPath(base, settings["design_bed"]))]
        if base and settings.get("design_bed")
        else []
    )
    return {"bam_id": bams, "bai_id": indexes, "design_bed_paths": beds}
