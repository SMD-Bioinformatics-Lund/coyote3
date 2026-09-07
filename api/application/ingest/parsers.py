"""Parser helpers for internal DNA/RNA ingest payloads."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from api.config.constants import TRANSCRIPT_SELECTION_ORDER
from api.contracts.schemas.normalizers import normalize_ampersand_terms
from api.contracts.schemas.samples import DNA_SAMPLE_FILE_KEYS, RNA_SAMPLE_FILE_KEYS
from api.domain.core.dna.transcript_payloads import (
    canonicalize_selected_transcript_symbol,
    hgnc_doc_for_transcript,
    matches_mane_source,
)
from api.domain.core.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)


def _exists(path: str | None) -> bool:
    """Return True if path is non-empty and points to an existing filesystem entry.

    Args:
        path: Filesystem path to check, may be None.

    Returns:
        True if the path exists, False otherwise.
    """
    return bool(path) and os.path.exists(path)


def require_exists(label: str, path: str | None) -> None:
    """Raise FileNotFoundError if path does not exist or is not readable.

    Args:
        label: Human-readable name used in the error message.
        path: Filesystem path to validate.

    Raises:
        FileNotFoundError: If path is None, empty, or does not exist.
    """
    if not _exists(path):
        raise FileNotFoundError(f"{label} missing or not readable: {path}")


def runtime_file_path(args: dict[str, Any], key: str) -> str | None:
    """Resolve a file path for key from the runtime override dict or the payload directly.

    Checks ``args['_runtime_files'][key]`` first (upload-time resolved paths),
    then falls back to ``args[key]`` (static paths from YAML payloads).

    Args:
        args: Validated sample payload dict.
        key: File key to resolve (e.g. ``vcf_files``, ``cnv``).

    Returns:
        The resolved path string, or None if the key is absent in both locations.
    """
    runtime = args.get("_runtime_files")
    if isinstance(runtime, dict):
        value = runtime.get(key)
        if value:
            return str(value)
    files = args.get("files")
    if isinstance(files, dict):
        file_doc = files.get(key)
        if isinstance(file_doc, dict) and file_doc.get("path"):
            return str(file_doc.get("path"))
        if isinstance(file_doc, str) and file_doc:
            return file_doc
    value = args.get(key)
    return str(value) if value else None


def infer_omics_layer(args: dict[str, Any]) -> str | None:
    """Detect the omics layer (DNA or RNA) from file keys present in the payload.

    Args:
        args: Validated sample payload dict.

    Returns:
        ``"dna"`` or ``"rna"`` if exactly one layer is detected, None if neither.

    Raises:
        ValueError: If both DNA and RNA file keys are present simultaneously.
    """
    files = args.get("files") if isinstance(args.get("files"), dict) else {}
    has_dna = any(bool(args.get(key)) or key in files for key in DNA_SAMPLE_FILE_KEYS)
    has_rna = any(bool(args.get(key)) or key in files for key in RNA_SAMPLE_FILE_KEYS)
    if has_dna and has_rna:
        raise ValueError("Data types conflict: both RNA and DNA detected.")
    if has_dna:
        return "dna"
    if has_rna:
        return "rna"
    return None


def _split_on_colon(value: str | None) -> str | None:
    """Return the right-hand side of a colon-delimited value, or the original if no colon.

    Args:
        value: Input string, may be None.

    Returns:
        The substring after the first colon, or the original value unchanged.
    """
    if not value:
        return value
    parts = value.split(":")
    return parts[1] if len(parts) > 1 else value


def _split_on_ampersand(found: dict[str, int], raw: str) -> dict[str, int]:
    """Accumulate ampersand-delimited pieces from raw into the found dict.

    Args:
        found: Running accumulator of seen values.
        raw: Ampersand-delimited string to split.

    Returns:
        The updated found dict with each piece set to 1.
    """
    try:
        for piece in raw.split("&"):
            found[piece] = 1
        return found
    except Exception:
        found[str(raw)] = 1
        return found


def _collect_dbsnp(found: dict[str, int], raw: str) -> dict[str, int]:
    """Collect rsXXX identifiers from an ampersand-delimited string into found.

    Args:
        found: Running accumulator of seen rsIDs.
        raw: Ampersand-delimited string potentially containing rsXXX entries.

    Returns:
        The updated found dict with each rsXXX entry set to 1.
    """
    for snp in raw.split("&"):
        if snp.startswith("rs"):
            found[snp] = 1
    return found


def _collect_hotspots(hotspot_dict: dict[str, list]) -> dict[str, list]:
    """Filter hotspot_dict to only entries with non-empty, deduplicated ID lists.

    Args:
        hotspot_dict: Raw mapping of hotspot type to lists of IDs (may contain None/duplicates).

    Returns:
        A cleaned dict with empty or all-None entries removed.
    """
    cleaned: dict[str, list] = {}
    for hotspot, ids in hotspot_dict.items():
        formatted = list(set(filter(None, ids)))
        if formatted:
            cleaned[hotspot] = formatted
    return cleaned


def _is_float(value: str) -> bool:
    """Detect whether value is a decimal float string (contains a dot and parses as float).

    Args:
        value: String to inspect.

    Returns:
        True if value is a float with a decimal point, False otherwise.
    """
    try:
        float(value)
        return len(value.split(".")) > 1
    except Exception:
        return False


def _normalize_callers_field(value: Any) -> list[str]:
    """Normalize caller payloads from pipeline CNV JSON to list[str]."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        raw = value.replace("|", ",").replace(";", ",")
        return [token.strip().lower() for token in raw.split(",") if token.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    text = str(value).strip().lower()
    return [text] if text else []


def _normalize_nprobes_field(value: Any) -> int:
    """Normalize optional nprobes values, defaulting missing pipeline rows to zero."""
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_fusion_docs(payload: Any) -> list[dict[str, Any]]:
    """Expand sparse pipeline fusion calls into the canonical stored shape.

    The RNA fusion aggregator marks the chosen call with ``selected: 1`` and
    omits the field from alternative calls. Stored fusion documents require an
    explicit integer selection state on every call, so omitted values become
    zero at the ingest boundary.
    """
    if not isinstance(payload, list):
        raise ValueError("Fusion JSON must decode to a list of fusion records")

    normalized_fusions: list[dict[str, Any]] = []
    for fusion_index, fusion in enumerate(payload):
        if not isinstance(fusion, dict):
            raise ValueError(f"Fusion record {fusion_index} must be an object")

        calls = fusion.get("calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"Fusion record {fusion_index} must contain at least one call")

        normalized_calls: list[dict[str, Any]] = []
        for call_index, call in enumerate(calls):
            if not isinstance(call, dict):
                raise ValueError(
                    f"Fusion record {fusion_index} call {call_index} must be an object"
                )
            normalized_call = dict(call)
            raw_selected = normalized_call.get("selected", 0)
            try:
                selected = int(raw_selected)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Fusion record {fusion_index} call {call_index} has invalid selected value"
                ) from exc
            if selected not in {0, 1}:
                raise ValueError(
                    f"Fusion record {fusion_index} call {call_index} selected must be 0 or 1"
                )
            normalized_call["selected"] = selected
            normalized_call.setdefault("effect", "")
            normalized_call.setdefault("commonreads", 0)
            normalized_call.setdefault("desc", "")
            normalized_calls.append(normalized_call)

        selected_count = sum(call["selected"] for call in normalized_calls)
        if selected_count != 1:
            genes = str(fusion.get("genes") or f"record {fusion_index}")
            raise ValueError(
                f"Fusion '{genes}' must contain exactly one selected call; found {selected_count}"
            )

        normalized_fusion = dict(fusion)
        normalized_fusion["calls"] = normalized_calls
        normalized_fusions.append(normalized_fusion)

    return normalized_fusions


def _normalize_cnv_ratio(value: Any) -> float | None:
    """Normalize pipeline CNV ratio values to the internal numeric representation."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().upper()
    symbolic = {
        "DEL": -1.0,
        "LOSS": -1.0,
        "AMP": 1.0,
        "DUP": 0.5,
        "GAIN": 0.5,
    }
    if raw in symbolic:
        return symbolic[raw]
    try:
        return float(raw)
    except ValueError:
        return None


def _infer_cnv_type(ratio: float | None) -> str | None:
    """Infer a stable CNV event type from normalized numeric ratio values."""
    if ratio is None:
        return None
    if ratio > 1:
        return "AMP"
    if ratio > 0:
        return "DUP"
    if ratio < 0:
        return "DEL"
    return None


def _emulate_perl(var_dict: dict[str, Any]) -> dict[str, Any]:
    """Collapse ampersand-delimited numeric CSQ values to their maximum.

    For each transcript in INFO/CSQ, any string field containing ampersand-delimited
        float values is collapsed to the numeric maximum.

    Args:
        var_dict: Parsed variant dict with INFO/CSQ list populated.

    Returns:
        The same var_dict with float CSQ fields collapsed to their maximum value.
    """
    for transcript in var_dict["INFO"]["CSQ"]:
        for key in list(transcript.keys()):
            if isinstance(transcript[key], str):
                data = transcript[key].split("&")
                if _is_float(data[0]):
                    transcript[key] = float(max(float(x) for x in data))
    return var_dict


def _parse_allele_freq(freq_str: str | None, allele: str) -> float:
    """Extract allele frequency for allele from a colon:ampersand-delimited frequency string.

    Args:
        freq_str: String in the format ``ALLELE:FREQ&ALLELE:FREQ&...``, or None.
        allele: The allele identifier to look up.

    Returns:
        The frequency as a float, or 0.0 if allele is not found or freq_str is falsy.
    """
    if freq_str:
        for item in freq_str.split("&"):
            parts = item.split(":")
            if parts[0] == allele:
                return float(parts[1])
    return 0.0


def _max_gnomad(gnomad: str | None) -> float | str | None:
    """Return the maximum gnomAD frequency from an ampersand-delimited string.

    Args:
        gnomad: Ampersand-delimited gnomAD frequency string, or None.

    Returns:
        The maximum value as a float, the original string if parsing fails, or None if falsy.
    """
    if not gnomad:
        return None
    try:
        return float(max(gnomad.split("&")))
    except Exception:
        return gnomad


def _pick_af_fields(var: dict[str, Any]) -> dict[str, Any]:
    """Extract gnomAD, ExAC, and 1000G allele frequencies from the first CSQ entry.

    Args:
        var: Parsed variant dict with ALT allele and INFO/CSQ list populated.

    Returns:
        A dict with keys ``gnomad_frequency``, ``gnomad_max``, ``exac_frequency``,
        and ``thousandG_frequency``.
    """
    af: dict[str, Any] = {
        "gnomad_frequency": "",
        "gnomad_max": "",
        "exac_frequency": "",
        "thousandG_frequency": "",
    }
    allele = var["ALT"]
    exac = _parse_allele_freq(var["INFO"]["CSQ"][0].get("ExAC_MAF"), allele)
    thousand_g = _parse_allele_freq(var["INFO"]["CSQ"][0].get("GMAF"), allele)
    gnomad = var["INFO"]["CSQ"][0].get("gnomAD_AF", 0)
    gnomad_genome = var["INFO"]["CSQ"][0].get("gnomADg_AF", 0)
    gnomad_max = var["INFO"]["CSQ"][0].get("MAX_AF", 0)

    if gnomad:
        af["gnomad_frequency"] = _max_gnomad(gnomad)
        if gnomad_max:
            af["gnomad_max"] = gnomad_max
    elif gnomad_genome:
        af["gnomad_frequency"] = gnomad_genome
        if gnomad_max:
            af["gnomad_max"] = gnomad_max
    if exac:
        af["exac_frequency"] = exac
    if thousand_g:
        af["thousandG_frequency"] = thousand_g
    return af


def _parse_transcripts(csq: list[dict[str, Any]]) -> tuple[Any, ...]:
    """Parse a CSQ annotation list into slim transcripts and aggregated annotation sets.

    Extracts a subset of VEP consequence fields per transcript and accumulates
    cross-transcript sets of COSMIC IDs, dbSNP rsIDs, PubMed IDs, transcript IDs,
    HGVSc/HGVSp notations, gene symbols, and hotspot identifiers.

    Args:
        csq: List of VEP CSQ dicts from a parsed VCF variant.

    Returns:
        A 10-tuple of:
            (slim_transcripts, cosmic_ids, dbsnp_first, pubmed_ids,
             transcript_ids, hgvsc_ids, hgvsp_ids, gene_symbols, hotspots,
             consequence_terms)
    """
    transcripts: list[dict[str, Any]] = []
    pubmed: dict[str, int] = {}
    cosmic: dict[str, int] = {}
    dbsnp: dict[str, int] = {}
    transcript_ids: dict[str, int] = {}
    hgvsc_ids: dict[str, int] = {}
    hgvsp_ids: dict[str, int] = {}
    gene_symbols: dict[str, int] = {}
    hotspots: dict[str, list] = {}
    consequence_terms: dict[str, int] = {}

    for transcript in csq:
        slim: dict[str, Any] = {}
        feature = transcript.get("Feature")
        slim["Feature"] = feature
        tid = str(feature).split(".")[0] if feature else ""
        if tid:
            transcript_ids[tid] = 1

        slim["HGNC_ID"] = transcript.get("HGNC_ID")
        symbol = transcript.get("SYMBOL")
        slim["SYMBOL"] = symbol
        if symbol:
            gene_symbols[symbol] = 1

        for key in (
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
        ):
            slim[key] = transcript.get(key)
        slim["CLIN_SIG"] = normalize_ampersand_terms(transcript.get("CLIN_SIG"))

        raw_consequences = transcript.get("Consequence")
        if isinstance(raw_consequences, str):
            for term in raw_consequences.split("&"):
                if term:
                    consequence_terms[term] = 1
        elif isinstance(raw_consequences, (list, tuple, set)):
            for term in raw_consequences:
                normalized_term = str(term or "").strip()
                if normalized_term:
                    consequence_terms[normalized_term] = 1

        protein = _split_on_colon(transcript.get("HGVSp"))
        slim["HGVSp"] = protein
        if protein:
            hgvsp_ids[protein] = 1

        cdna = _split_on_colon(transcript.get("HGVSc"))
        slim["HGVSc"] = cdna
        if cdna:
            hgvsc_ids[cdna] = 1

        cosmic_value = transcript.get("COSMIC")
        if cosmic_value:
            cosmic = _split_on_ampersand(cosmic, cosmic_value)
        ev = transcript.get("Existing_variation")
        if ev:
            dbsnp = _collect_dbsnp(dbsnp, ev)
        pm = transcript.get("PUBMED")
        if pm:
            pubmed = _split_on_ampersand(pubmed, pm)

        for trk in list(transcript.keys()):
            for hotspot in ["d", "gi", "lu", "cns", "mm", "co"]:
                if f"{hotspot}hotspot_OID" in trk:
                    value = transcript.get(trk)
                    if value:
                        hotspots.setdefault(hotspot, []).append(value)

        transcripts.append(slim)

    dbsnp_list = list(dbsnp.keys())
    dbsnp_first = dbsnp_list[0] if dbsnp_list else ""
    return (
        transcripts,
        list(cosmic.keys()),
        dbsnp_first,
        list(pubmed.keys()),
        [x for x in transcript_ids.keys() if x],
        [x for x in hgvsc_ids.keys() if x],
        [x for x in hgvsp_ids.keys() if x],
        [x for x in gene_symbols.keys() if x],
        _collect_hotspots(hotspots),
        list(consequence_terms),
    )


def _build_transcript_vault_rows(
    raw_csq: list[dict[str, Any]],
    slim_csq: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build immutable VEP transcript rows without mutable HGNC display state."""
    vault_rows: list[dict[str, Any]] = []
    for raw, slim in zip(raw_csq, slim_csq, strict=True):
        row = dict(slim)
        row["MANE_SELECT"] = raw.get("MANE_SELECT")
        row["MANE_PLUS_CLINICAL"] = raw.get("MANE_PLUS_CLINICAL")
        vault_rows.append(row)
    return vault_rows


def _build_anno_vep_docs(variants: list[dict[str, Any]], vep_version: Any) -> list[dict[str, Any]]:
    """Build immutable transcript-vault documents from normalized variant rows."""
    version = str(vep_version or "").strip().lstrip("vV")
    if not version:
        return []
    docs: list[dict[str, Any]] = []
    for variant in variants:
        simple_id = normalize_simple_id(variant.get("simple_id"))
        if not simple_id:
            continue
        info = variant.get("INFO") or {}
        selected = info.get("selected_CSQ")
        transcripts = [dict(csq) for csq in info.get("CSQ") or [] if isinstance(csq, dict)]
        if isinstance(selected, dict):
            selected_feature = str(selected.get("Feature") or "").strip()
            if selected_feature and not any(
                str(csq.get("Feature") or "").strip() == selected_feature for csq in transcripts
            ):
                transcripts.insert(0, dict(selected))
        docs.append(
            {
                "simple_id": simple_id,
                "simple_id_hash": build_simple_id_hash_from_simple_id(simple_id),
                "vep_version": version,
                "variant_class": variant.get("variant_class"),
                "CSQ": transcripts,
            }
        )
    return docs


def _first_csq_by_impact(
    csq_arr: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> int:
    """Return the first CSQ index matching a predicate in clinical impact order."""
    for impact in ["HIGH", "MODERATE", "LOW", "MODIFIER"]:
        for idx, csq in enumerate(csq_arr):
            if csq.get("IMPACT") == impact and predicate(csq):
                return idx
    return -1


def _select_csq(
    csq_arr: list[dict[str, Any]],
    hgnc_by_id: dict[str, dict[str, Any]] | None = None,
    hgnc_by_symbol: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    """Select the canonical transcript from a slim CSQ array using a priority hierarchy.

    The ordered selector names are loaded from the center-owned
    ``reporting.transcript_selection_order`` configuration. Each selector is
    evaluated in that declared order; within a selector, rows are evaluated by
    impact (HIGH → MODERATE → LOW → MODIFIER).

    Args:
        csq_arr: List of slim CSQ transcript dicts (output of ``_parse_transcripts``).
    Returns:
        A tuple of selected CSQ document and its configured selector name.
    """
    selectors: dict[str, Callable[[dict[str, Any]], bool]] = {
        "ncbi_mane_plus_clinical": lambda csq: matches_mane_source(
            csq,
            hgnc_doc_for_transcript(csq, hgnc_by_id, hgnc_by_symbol),
            hgnc_key="refseq_mane_plus_clinical",
            namespace="ncbi",
        ),
        "ensembl_mane_plus_clinical": lambda csq: matches_mane_source(
            csq,
            hgnc_doc_for_transcript(csq, hgnc_by_id, hgnc_by_symbol),
            hgnc_key="ensembl_mane_plus_clinical",
            namespace="ensembl",
        ),
        "ncbi_mane_select": lambda csq: matches_mane_source(
            csq,
            hgnc_doc_for_transcript(csq, hgnc_by_id, hgnc_by_symbol),
            hgnc_key="refseq_mane_select",
            namespace="ncbi",
        ),
        "ensembl_mane_select": lambda csq: matches_mane_source(
            csq,
            hgnc_doc_for_transcript(csq, hgnc_by_id, hgnc_by_symbol),
            hgnc_key="ensembl_mane_select",
            namespace="ensembl",
        ),
        "vep_canonical_protein_coding": lambda csq: (
            csq.get("CANONICAL") == "YES" and csq.get("BIOTYPE") == "protein_coding"
        ),
        "first_protein_coding": lambda csq: csq.get("BIOTYPE") == "protein_coding",
        "first_available": lambda _csq: True,
    }
    for selector_name in TRANSCRIPT_SELECTION_ORDER:
        selected_index = _first_csq_by_impact(csq_arr, selectors[selector_name])
        if selected_index >= 0:
            return (
                canonicalize_selected_transcript_symbol(
                    csq_arr[selected_index], hgnc_by_id, hgnc_by_symbol
                ),
                selector_name,
            )
    raise RuntimeError("transcript selection order did not contain a matching fallback")


def _split_string_list(value: Any, separator: str = ";") -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value)
    return [item for item in text.split(separator) if item]


def _normalize_transloc_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize parsed translocation VCF rows to the collection contract."""
    normalized = dict(doc)
    normalized["FILTER"] = _split_string_list(normalized.get("FILTER"))
    normalized["FORMAT"] = _split_string_list(normalized.get("FORMAT"), ":")

    normalized_gt: list[dict[str, Any]] = []
    for gt in normalized.get("GT") or []:
        if not isinstance(gt, dict):
            continue
        gt_doc = dict(gt)
        gt_doc["sample"] = str(gt_doc.get("sample") or gt_doc.get("_sample_id") or "")
        gt_doc["PR"] = str(gt_doc.get("PR") or "")
        gt_doc["SR"] = str(gt_doc.get("SR") or "")
        raw_ur = gt_doc.get("UR")
        gt_doc["UR"] = None if raw_ur in (None, "", ".") else float(raw_ur)
        gt_doc.pop("_sample_id", None)
        normalized_gt.append(gt_doc)
    normalized["GT"] = normalized_gt

    raw_qual = normalized.get("QUAL")
    normalized["QUAL"] = None if raw_qual in (None, "", ".") else float(raw_qual)

    info = normalized.get("INFO")
    if isinstance(info, list):
        info = next((item for item in info if isinstance(item, dict)), {})
    if isinstance(info, dict):
        info_doc = dict(info)
        info_doc["SOMATIC"] = bool(info_doc.get("SOMATIC", False))
        panel = info_doc.get("PANEL") or info_doc.get("set")
        if panel is not None:
            info_doc["PANEL"] = _split_string_list(panel, "|")
        normalized_ann: list[dict[str, Any]] = []
        for ann in info_doc.get("ANN") or []:
            if not isinstance(ann, dict):
                continue
            ann_doc = {
                key.replace(".", "").replace("ERRORS / WARNINGS / INFO", "INFO"): value
                for key, value in ann.items()
            }
            annotation = ann_doc.get("Annotation")
            if isinstance(annotation, str):
                ann_doc["Annotation"] = _split_string_list(annotation, "&")
            normalized_ann.append(ann_doc)
        info_doc["ANN"] = normalized_ann
        mane_ann = info_doc.get("MANE_ANN")
        if isinstance(mane_ann, list):
            mane_ann = next((item for item in mane_ann if isinstance(item, dict)), None)
        if isinstance(mane_ann, dict):
            mane_doc = {
                key.replace(".", "").replace("ERRORS / WARNINGS / INFO", "INFO"): value
                for key, value in mane_ann.items()
            }
            annotation = mane_doc.get("Annotation")
            if isinstance(annotation, str):
                mane_doc["Annotation"] = _split_string_list(annotation, "&")
            info_doc["MANE_ANN"] = mane_doc
        else:
            info_doc.pop("MANE_ANN", None)
        normalized["INFO"] = info_doc
    else:
        normalized["INFO"] = {}
    return normalized


from .analysis_parsers import DnaIngestParser, RnaIngestParser  # noqa: E402

__all__ = ["DnaIngestParser", "RnaIngestParser", "infer_omics_layer"]
