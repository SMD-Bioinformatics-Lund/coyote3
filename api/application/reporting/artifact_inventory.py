"""Read-only reconciliation of committed report references and report artifacts."""

import time
from pathlib import Path


def inspect_report_artifacts(root, records, *, minimum_age_seconds=86400):
    """Identify missing references and old unreferenced files without deleting anything.

    Fresh files are excluded because report generation precedes the database commit.
    An unreferenced artifact can also belong to a deliberately deleted sample.
    """
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Report root must be a directory")
    referenced = set()
    missing, outside, unreferenced = [], [], []
    for record in records:
        for field in ("filepath", "pdf_filepath"):
            value = record.get(field)
            if not value:
                continue
            path = Path(value).resolve()
            if not path.is_relative_to(root):
                outside.append({"report_oid": str(record["_id"]), "field": field})
                continue
            referenced.add(path)
            if not path.is_file():
                missing.append(
                    {
                        "report_oid": str(record["_id"]),
                        "field": field,
                        "path": str(path.relative_to(root)),
                    }
                )
    cutoff = time.time() - max(0, minimum_age_seconds)
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".html", ".pdf"} or path.is_symlink():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or resolved in referenced or not path.is_file():
            continue
        if path.stat().st_mtime <= cutoff:
            unreferenced.append(str(path.relative_to(root)))
    return {"missing": missing, "outside_root": outside, "unreferenced": sorted(unreferenced)}
