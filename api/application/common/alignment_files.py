"""Resolve sample-declared alignments before consulting the BAM-service catalog."""

from collections.abc import Callable
from typing import Any


def alignment_files_payload(
    sample: dict[str, Any],
    sample_ids: dict[str, str],
    lookup: Callable[[dict[str, str]], dict[str, list[str]]],
) -> dict[str, Any]:
    """Keep explicit paths authoritative and look up only roles without a BAM."""
    bams: dict[str, list[str]] = {}
    indexes: dict[str, str] = {}
    missing: dict[str, str] = {}
    for role, sample_id in sample_ids.items():
        details = sample.get(role) or {}
        bam = str(details.get("bam") or "").strip()
        bai = str(details.get("bai") or "").strip()
        if bam:
            bams[sample_id] = [bam]
            if bai:
                indexes[bam] = bai
        else:
            missing[role] = sample_id
    fallback = (lookup(missing) or {}) if missing else {}
    for role, sample_id in missing.items():
        paths = fallback.get(sample_id) or []
        if paths:
            bams[sample_id] = paths
            bai = str((sample.get(role) or {}).get("bai") or "").strip()
            # A single explicit index cannot identify one of several fallback BAMs.
            if bai and len(paths) == 1:
                indexes[paths[0]] = bai
    return {"bam_id": bams, "bai_id": indexes}
