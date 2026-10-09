"""Parse DNA structural VCFs with embedded SnpEff evidence and mate provenance."""

from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from pysam import VariantFile

from api.domain.common.parsers import cmdvcf
from api.domain.core.dna.structural_annotations import (
    MANE_SELECTORS,
    STRUCTURAL_TYPES,
    eligible_annotation,
    select_structural_annotation,
)


def _custom_annotations(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return eligible custom feature annotations requiring breakend pairing.

    Args:
        record: Normalized structural VCF record.

    Returns:
        Every matching annotation, including mixed consequence lists.
    """
    return [
        ann
        for ann in record["INFO"]["ANN"]
        if eligible_annotation(ann)
        and "feature_fusion" in ann.get("Annotation", [])
        and ann.get("Feature_Type") == "CUSTOM&sorted"
    ]


def _feature(annotation: dict[str, Any]) -> tuple[str, str]:
    """Extract a declared custom gene and identifier without supplying defaults.

    Args:
        annotation: Custom feature annotation with GENE_IDENTIFIER in Feature_ID.

    Returns:
        Source gene symbol and source identifier.

    Raises:
        ValueError: The custom identifier is missing or malformed.
    """
    symbol, separator, identifier = str(annotation.get("Feature_ID") or "").partition("_")
    if not separator or not symbol or not identifier or "&" in symbol + identifier:
        raise ValueError("Custom feature_fusion requires a single GENE_IDENTIFIER Feature_ID")
    return symbol, identifier


def _combine(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Combine reciprocal custom annotations without asserting biological direction.

    Args:
        left: Annotation from the deterministically selected first breakend.
        right: Annotation from its reciprocal mate.

    Returns:
        Derived partner annotation. Unknown or conflicting impact stays null;
        every original annotation remains in the embedded source records.
    """
    gene1, id1 = _feature(left)
    gene2, id2 = _feature(right)
    return {
        "Allele": left["Allele"],
        "Annotation": ["feature_fusion"],
        "Annotation_Impact": left.get("Annotation_Impact")
        if left.get("Annotation_Impact") == right.get("Annotation_Impact")
        else None,
        "Gene_Name": f"{gene1}&{gene2}",
        "Gene_ID": f"{id1}&{id2}",
        "Feature_Type": "CUSTOM&sorted",
        "Feature_ID": f"{left['Feature_ID']}&{right['Feature_ID']}",
        "HGVSc": (
            ";".join(str(ann.get("HGVSc") or "") for ann in (left, right))
            if left.get("HGVSc") or right.get("HGVSc")
            else None
        ),
    }


def parse_translocations(
    path: str, *, hgnc_by_id: dict, hgnc_by_symbol: dict, warnings: list[str]
) -> list[dict[str, Any]]:
    """Read PASS BND/DEL/DUP findings, pairing eligible custom breakends safely.

    Args:
        path: Local SnpEff-annotated DNA VCF path.
        hgnc_by_id: Internal HGNC metadata keyed by ID.
        hgnc_by_symbol: Internal HGNC metadata keyed by approved and alias symbols.
        warnings: Receives aggregate exclusion counts and missing-reference notices.

    Returns:
        Contract-ready findings without SAMPLE_ID. All SnpEff transcripts remain
        embedded; paired findings also retain both original records. ANN[0] is the
        selected annotation; MANE_ANN is set only for an actual MANE match.

    Raises:
        ValueError: Required annotation data, unique IDs, reciprocal mate links or
            explicit symbolic-event end coordinates are invalid. No partial result
            is returned for an invalid file.
    """
    # Imported at call time to preserve the existing parser facade's import order.
    from .parsers import _normalize_transloc_doc

    records: dict[str, dict[str, Any]] = {}
    retained: list[dict[str, Any]] = []
    excluded = {"unsupported_svtype": 0, "not_pass": 0, "no_eligible_annotation": 0}
    with VariantFile(path) as source:
        for record in source:
            if not record.alts:
                raise ValueError("DNA structural VCF records require an ALT allele")
            raw = _normalize_transloc_doc(cmdvcf.parse_variant(record, source.header))
            identifier = raw["ID"]
            if identifier != "." and identifier in records:
                raise ValueError(f"Duplicate DNA structural VCF record ID: {identifier}")
            # pysam reserves END: it is available through stop, not record.info.
            explicit_end = next(
                (
                    item[4:]
                    for item in str(record).split("\t")[7].split(";")
                    if item.startswith("END=")
                ),
                None,
            )
            if explicit_end is not None:
                raw["END"] = int(explicit_end)
                if raw["END"] < raw["POS"]:
                    raise ValueError("Structural END must be at or after POS")
            if (
                raw["ALT"].startswith("<")
                and raw["INFO"].get("SVTYPE") in {"DEL", "DUP"}
                and explicit_end is None
            ):
                raise ValueError("Symbolic DEL/DUP records require an explicit END coordinate")
            if identifier != ".":
                records[identifier] = raw
            if raw["INFO"].get("SVTYPE") not in STRUCTURAL_TYPES:
                excluded["unsupported_svtype"] += 1
                continue
            if raw["FILTER"] != ["PASS"]:
                excluded["not_pass"] += 1
                continue
            if not raw["INFO"]["ANN"]:
                raise ValueError("PASS DNA structural records require SnpEff ANN annotations")
            for ann in raw["INFO"]["ANN"]:
                if any(
                    key not in ann
                    for key in ("Allele", "Gene_Name", "Gene_ID", "Feature_Type", "Feature_ID")
                ):
                    raise ValueError("SnpEff ANN is missing required gene or feature identifiers")
                is_custom = (
                    "feature_fusion" in ann.get("Annotation", [])
                    and ann.get("Feature_Type") == "CUSTOM&sorted"
                )
                if (
                    eligible_annotation(ann)
                    and not is_custom
                    and any(not ann.get(key) for key in ("Gene_Name", "Gene_ID", "Feature_ID"))
                ):
                    raise ValueError(
                        "Eligible SnpEff annotations require gene and feature identifiers"
                    )
            if not any(eligible_annotation(ann) for ann in raw["INFO"]["ANN"]):
                excluded["no_eligible_annotation"] += 1
                continue
            retained.append(raw)
    retained_ids = {row["ID"] for row in retained}
    consumed: set[str] = set()
    result = []
    for row in sorted(retained, key=lambda item: (item["CHROM"], item["POS"], item["ID"])):
        if row["ID"] in consumed:
            continue
        custom = _custom_annotations(row)
        candidates = [
            ann for ann in row["INFO"]["ANN"] if eligible_annotation(ann) and ann not in custom
        ]
        if custom:
            mate_id = row["INFO"].get("MATEID")
            mate = records.get(mate_id)
            if (
                row["ID"] == "."
                or row["INFO"].get("SVTYPE") != "BND"
                or not mate
                or mate_id == row["ID"]
                or mate_id not in retained_ids
                or mate_id in consumed
                or mate["INFO"].get("SVTYPE") != "BND"
                or mate["INFO"].get("MATEID") != row["ID"]
            ):
                raise ValueError(
                    f"Custom feature_fusion {row['ID']}: requires a distinct, reciprocal PASS BND mate ({mate_id})"
                )
            mate_custom = _custom_annotations(mate)
            if not mate_custom:
                raise ValueError("Custom feature_fusion mate has no eligible custom annotation")
            source_records = deepcopy([row, mate])
            combined = [_combine(left, right) for left, right in product(custom, mate_custom)]
            row = deepcopy(row)
            row["source_records"] = source_records
            row["INFO"]["ANN"] = combined + row["INFO"]["ANN"] + mate["INFO"]["ANN"]
            candidates = (
                combined
                + candidates
                + [
                    ann
                    for ann in mate["INFO"]["ANN"]
                    if eligible_annotation(ann) and ann not in mate_custom
                ]
            )
            consumed.add(mate_id)
        selected, criterion = select_structural_annotation(candidates, hgnc_by_id, hgnc_by_symbol)
        annotations = row["INFO"]["ANN"]
        selected_index = annotations.index(selected)
        row["INFO"]["ANN"] = (
            [selected] + annotations[:selected_index] + annotations[selected_index + 1 :]
        )
        row["INFO"]["ANN_selection_source"] = criterion
        row["INFO"].pop("MANE_ANN", None)
        if criterion in MANE_SELECTORS:
            row["INFO"]["MANE_ANN"] = selected
        result.append(row)
        if row["ID"] != ".":
            consumed.add(row["ID"])
    for reason, count in excluded.items():
        if count:
            warnings.append(f"DNA structural VCF: {count} records excluded ({reason})")
    if result and not (hgnc_by_id or hgnc_by_symbol):
        warnings.append(
            "DNA structural VCF: HGNC metadata unavailable; selection uses SnpEff fallback criteria"
        )
    return result
