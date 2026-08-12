"""Stable payload boundaries for selected and versioned VEP transcripts."""

from typing import Any

# The mutable variant collection stores only the compact transcript selected for
# review. Transcript provenance and every alternate transcript belong to the
# immutable, versioned ``anno_vep`` collection.
SELECTED_CSQ_FIELDS = frozenset(
    {
        "Feature",
        "HGNC_ID",
        "SYMBOL",
        "PolyPhen",
        "SIFT",
        "Consequence",
        "ENSP",
        "BIOTYPE",
        "INTRON",
        "EXON",
        "CANONICAL",
        "STRAND",
        "IMPACT",
        "CADD_PHRED",
        "CLIN_SIG",
        "VARIANT_CLASS",
        "HGVSc",
        "HGVSp",
    }
)

# These properties are derived from the current HGNC dataset.  They must never
# be retained in ``anno_vep`` because a later HGNC refresh can change them
# without changing the VEP evidence itself.
DYNAMIC_TRANSCRIPT_FIELDS = frozenset(
    {
        "VEP_SYMBOL",
        "HGNC_MATCHED",
        "HGNC_MATCH_SOURCE",
        "transcript_tags",
        "canonical_source",
        "is_canonical",
    }
)


def feature_without_version(value: Any) -> str:
    """Return a transcript accession without its version suffix."""
    return str(value or "").split(".")[0]


def hgnc_lookup_key(value: Any) -> str:
    """Normalize an HGNC identifier for repository and in-memory lookups."""
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return normalized if normalized.startswith("HGNC:") else f"HGNC:{normalized}"


def build_hgnc_lookup_maps(
    documents: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build HGNC ID and symbol lookup maps from current HGNC documents."""
    by_id: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}
    for document in documents:
        hgnc_id = hgnc_lookup_key(document.get("hgnc_id") or document.get("_id"))
        if hgnc_id:
            by_id[hgnc_id] = document
        for key in ("hgnc_symbol", "prev_symbol", "alias_symbol"):
            values = document.get(key)
            if isinstance(values, str):
                values = [values]
            for value in values or []:
                symbol = str(value or "").strip()
                if symbol:
                    by_symbol[symbol] = document
                    by_symbol[symbol.upper()] = document
    return by_id, by_symbol


def hgnc_doc_for_transcript(
    transcript: dict[str, Any],
    hgnc_by_id: dict[str, dict[str, Any]] | None = None,
    hgnc_by_symbol: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Resolve HGNC metadata by ID, approved symbol, previous symbol, or alias."""
    by_id = hgnc_by_id or {}
    by_symbol = hgnc_by_symbol or {}
    hgnc_id = hgnc_lookup_key(transcript.get("HGNC_ID"))
    if hgnc_id and hgnc_id in by_id:
        return by_id[hgnc_id]
    symbol = str(transcript.get("SYMBOL") or "").strip()
    return by_symbol.get(symbol) or by_symbol.get(symbol.upper())


def _hgnc_transcripts(document: dict[str, Any] | None, key: str) -> set[str]:
    values = (document or {}).get(key)
    if isinstance(values, str):
        values = [values]
    return {feature_without_version(value) for value in values or [] if str(value or "").strip()}


def matches_mane_source(
    transcript: dict[str, Any],
    hgnc_document: dict[str, Any] | None,
    *,
    hgnc_key: str,
    namespace: str,
) -> bool:
    """Match a transcript to its native HGNC MANE source namespace."""
    feature = feature_without_version(transcript.get("Feature"))
    configured = _hgnc_transcripts(hgnc_document, hgnc_key)
    if namespace == "ncbi":
        return feature.startswith(("NM_", "NR_")) and feature in configured
    return feature.startswith("ENST") and feature in configured


def annotate_transcript_provenance(
    transcripts: list[dict[str, Any]],
    *,
    hgnc_by_id: dict[str, dict[str, Any]] | None = None,
    hgnc_by_symbol: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Derive current HGNC/MANE and VEP-canonical display metadata."""
    annotated: list[dict[str, Any]] = []
    for raw in transcripts:
        transcript = strip_dynamic_transcript_fields(raw)
        document = hgnc_doc_for_transcript(transcript, hgnc_by_id, hgnc_by_symbol)
        tags: list[str] = []
        for tag, key, namespace in (
            ("ncbi_mane_plus_clinical", "refseq_mane_plus_clinical", "ncbi"),
            ("ensembl_mane_plus_clinical", "ensembl_mane_plus_clinical", "ensembl"),
            ("ncbi_mane_select", "refseq_mane_select", "ncbi"),
            ("ensembl_mane_select", "ensembl_mane_select", "ensembl"),
        ):
            if matches_mane_source(transcript, document, hgnc_key=key, namespace=namespace):
                tags.append(tag)
        canonical_source = "vep_canonical" if transcript.get("CANONICAL") == "YES" else None
        if canonical_source:
            tags.append(canonical_source)
        # Omit empty presentation state. The fields are generated only when
        # the current HGNC record or VEP declares a designation.
        if tags:
            transcript["transcript_tags"] = tags
            transcript["canonical_source"] = canonical_source
            transcript["is_canonical"] = bool(canonical_source)
        annotated.append(transcript)
    return annotated


def strip_dynamic_transcript_fields(transcript: dict[str, Any]) -> dict[str, Any]:
    """Remove mutable HGNC display fields from a stored or parsed transcript."""
    return {key: value for key, value in transcript.items() if key not in DYNAMIC_TRANSCRIPT_FIELDS}


def canonicalize_selected_transcript_symbol(
    transcript: dict[str, Any],
    hgnc_by_id: dict[str, dict[str, Any]] | None,
    hgnc_by_symbol: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Use the current approved HGNC symbol for the compact selected transcript."""
    document = hgnc_doc_for_transcript(transcript, hgnc_by_id, hgnc_by_symbol)
    if not document:
        return transcript
    normalized = dict(transcript)
    approved_symbol = str(document.get("hgnc_symbol") or "").strip()
    if approved_symbol:
        normalized["SYMBOL"] = approved_symbol
    hgnc_id = hgnc_lookup_key(document.get("hgnc_id") or document.get("_id"))
    if hgnc_id:
        normalized["HGNC_ID"] = hgnc_id
    return normalized


def compact_selected_csq(csq: dict[str, Any]) -> dict[str, Any]:
    """Return the review-safe selected-transcript projection.

    The input may be a VEP vault row or a freshly parsed transcript. Fields
    that explain transcript selection are intentionally excluded because they
    are versioned annotation evidence, not mutable variant state.
    """
    return {key: value for key, value in csq.items() if key in SELECTED_CSQ_FIELDS}
