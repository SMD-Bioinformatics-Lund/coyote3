"""SnpEff DNA structural annotation eligibility and HGNC transcript selection."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from api.config.constants import TRANSCRIPT_SELECTION_ORDER
from api.domain.core.dna.transcript_payloads import (
    hgnc_doc_for_transcript,
    matches_mane_source,
)

STRUCTURAL_CONSEQUENCES = frozenset(
    {
        "gene_fusion",
        "bidirectional_gene_fusion",
        "feature_fusion",
        "frameshift_variant",
        "transcript_ablation",
    }
)
STRUCTURAL_TYPES = frozenset({"BND", "DEL", "DUP"})
MANE_SELECTORS = {
    "ncbi_mane_plus_clinical": ("refseq_mane_plus_clinical", "ncbi"),
    "ensembl_mane_plus_clinical": ("ensembl_mane_plus_clinical", "ensembl"),
    "ncbi_mane_select": ("refseq_mane_select", "ncbi"),
    "ensembl_mane_select": ("ensembl_mane_select", "ensembl"),
}
_ACCESSION = re.compile(r"(?<![A-Za-z0-9_])(?:ENST\d+|N[MR]_\d+)(?:\.\d+)?(?![A-Za-z0-9_])")


def annotation_key(annotation: dict[str, Any]) -> str:
    """Identify an exact embedded row independently of its current order.

    Args:
        annotation: Original SnpEff annotation without display enrichment.

    Returns:
        SHA-256 digest of its canonical JSON representation.
    """
    return hashlib.sha256(json.dumps(annotation, sort_keys=True).encode()).hexdigest()


def structural_transcript_rows(
    annotations: list[dict[str, Any]], by_id: dict[str, Any], by_symbol: dict[str, Any]
) -> list[dict[str, Any]]:
    """Expose separate partners and HGNC MANE matches without changing stored annotations.

    Args:
        annotations: Embedded SnpEff combinations in stored order.
        by_id: HGNC documents indexed by ID.
        by_symbol: HGNC documents indexed by gene symbol.

    Returns:
        Rows with stable selection keys and ordered partner metadata. Missing
        partner transcripts remain blank rather than being inferred.
    """
    rows = []
    for annotation in annotations:
        genes = str(annotation.get("Gene_Name") or "").split("&")
        transcripts = str(annotation.get("Feature_ID") or "").split("&")
        partners = []
        for index, gene in enumerate(genes):
            transcript = transcripts[index] if index < len(transcripts) else ""
            document = hgnc_doc_for_transcript({"SYMBOL": gene}, by_id, by_symbol)
            flags = [
                selector
                for selector, (key, namespace) in MANE_SELECTORS.items()
                if document
                and transcript
                and matches_mane_source(
                    {"Feature": transcript}, document, hgnc_key=key, namespace=namespace
                )
            ]
            partners.append({"gene": gene, "transcript": transcript, "mane_flags": flags})
        rows.append(
            {
                "annotation_key": annotation_key(annotation),
                "annotation": annotation,
                "partners": partners,
            }
        )
    return rows


def eligible_annotation(annotation: dict[str, Any]) -> bool:
    """Accept supported SnpEff effects outside explicitly annotated pseudogenes.

    Args:
        annotation: Normalized embedded SnpEff annotation.

    Returns:
        Whether the annotation can qualify a structural finding for ingestion.
        Other annotations remain embedded for traceability.
    """
    biotypes = str(annotation.get("Transcript_BioType") or "").split("&")
    return "pseudogene" not in biotypes and bool(
        STRUCTURAL_CONSEQUENCES.intersection(annotation.get("Annotation") or [])
    )


def _matches_mane(
    annotation: dict[str, Any], selector: str, by_id: dict[str, Any], by_symbol: dict[str, Any]
) -> bool:
    """Require an HGNC MANE accession for every annotated gene partner.

    Args:
        annotation: SnpEff annotation with transcript IDs in Feature_ID or HGVS.
        selector: Supported MANE selector from the shared transcript hierarchy.
        by_id: Internal HGNC ID lookup.
        by_symbol: Internal approved, previous and alias symbol lookup.

    Returns:
        True only when every partner resolves and matches a complete accession;
        substring matches and annotations without transcript evidence do not qualify.
    """
    key, namespace = MANE_SELECTORS[selector]
    symbols = str(annotation.get("Gene_Name") or "").split("&")
    genes = str(annotation.get("Gene_ID") or "").split("&")
    if not symbols or len(symbols) != len(genes):
        return False
    for index, (symbol, gene) in enumerate(zip(symbols, genes, strict=True)):
        evidence = []
        for field in ("Feature_ID", "HGVSc", "HGVSp"):
            partners = str(annotation.get(field) or "").split("&")
            if len(partners) == len(genes):
                evidence.append(partners[index])
        accessions = _ACCESSION.findall(" ".join(evidence))
        document = hgnc_doc_for_transcript(
            {"SYMBOL": symbol, "HGNC_ID": gene if gene.startswith("HGNC:") else None},
            by_id,
            by_symbol,
        )
        if not document or not any(
            matches_mane_source({"Feature": accession}, document, hgnc_key=key, namespace=namespace)
            for accession in accessions
        ):
            return False
    return True


def select_structural_annotation(
    annotations: list[dict[str, Any]], by_id: dict[str, Any], by_symbol: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """Select embedded SnpEff evidence using the application transcript hierarchy.

    Args:
        annotations: Eligible SnpEff annotations in stable input order.
        by_id: HGNC ID metadata supplied by the ingest service.
        by_symbol: HGNC symbol metadata supplied by the ingest service.

    Returns:
        Selected annotation and selection criterion. Impact ordering uses SnpEff
        HIGH, MODERATE, LOW, MODIFIER, then unspecified impact. The VEP canonical
        step is inapplicable to SnpEff and is skipped without inventing a flag.

    Raises:
        ValueError: No eligible annotations were supplied.
    """
    impacts: dict[str | None, int] = {
        name: index for index, name in enumerate(("HIGH", "MODERATE", "LOW", "MODIFIER"))
    }
    ordered = sorted(annotations, key=lambda row: impacts.get(row.get("Annotation_Impact"), 4))
    for selector in TRANSCRIPT_SELECTION_ORDER:
        for annotation in ordered:
            if selector in MANE_SELECTORS:
                matches = _matches_mane(annotation, selector, by_id, by_symbol)
            elif selector == "first_protein_coding":
                matches = set(str(annotation.get("Transcript_BioType") or "").split("&")) == {
                    "protein_coding"
                }
            else:
                matches = selector == "first_available"
            if matches:
                return annotation, selector
    raise ValueError("No eligible SnpEff annotations for transcript selection")


def snpeff_consequence_metadata(findings: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Describe embedded SnpEff terms without consulting VEP reference data.

    Args:
        findings: DNA structural findings with embedded ANN rows.

    Returns:
        Term labels and source descriptions. Impact remains annotation-specific
        rather than being inferred from a different annotation database.
    """
    terms = {
        term
        for finding in findings
        for ann in (finding.get("INFO") or {}).get("ANN", [])
        for term in ann.get("Annotation", [])
    }
    return {
        term: {
            "display_name": term.replace("_", " "),
            "description": f"SnpEff consequence: {term}. See the annotation for its reported impact.",
        }
        for term in sorted(terms)
    }
