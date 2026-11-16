# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Capture the exact reportable SNV interpretation and review context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from coyote.domain.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)


def _build_snapshot_rows(
    variants: list[dict],
    assay_group: str,
    diagnosis: str | None,
    latest_sample_comment: dict | None,
    intent: str = "somatic",
) -> list[dict[str, Any]]:
    """Build snapshot rows for reported-variant persistence."""
    now_utc = datetime.now(timezone.utc)
    snapshot_rows: list[dict[str, Any]] = []
    for v in variants:
        annotations_interesting = v.get("annotations_interesting", {})
        annotations_interesting_assay_specific = (
            annotations_interesting.get(assay_group)
            or annotations_interesting.get(f"{assay_group}:{diagnosis}")
            or {}
        )
        sel = (v.get("INFO", {}) or {}).get("selected_CSQ", {}) or {}
        simple_id = normalize_simple_id(v.get("simple_id"))
        simple_id_hash = v.get("simple_id_hash") or (
            build_simple_id_hash_from_simple_id(simple_id) if simple_id else None
        )
        snapshot_rows.append(
            {
                "analysis_type": "SNV",
                "finding_type": "small_variant",
                "var_oid": v.get("_id"),
                "annotation_oid": v.get("classification", {}).get("_id", None),
                "annotation_text_oid": annotations_interesting_assay_specific.get("_id", None),
                "sample_comment_oid": (
                    latest_sample_comment.get("_id") if latest_sample_comment else None
                ),
                "var_type": v.get("variant_class"),
                "analysis_intent": intent,
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "nomenclature": v.get("classification", {}).get("nomenclature") or "p",
                "tier": v.get("classification", {}).get("class"),
                "gene": sel.get("SYMBOL") or (v.get("gene") or None),
                "transcript": sel.get("Feature") or v.get("selected_csq_feature"),
                "hgvsp": sel.get("HGVSp") or v.get("hgvsp"),
                "hgvsc": sel.get("HGVSc") or v.get("hgvsc"),
                "genomic": simple_id,
                "variant": v.get("classification", {}).get("variant"),
                "created_on": now_utc,
            }
        )
    return snapshot_rows
