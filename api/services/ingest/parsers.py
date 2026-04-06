"""Parser helpers for internal DNA/RNA ingest payloads."""

from __future__ import annotations

import csv
import gzip
import json
import os
from typing import Any

from pysam import VariantFile

from api.common.parsers import cmdvcf
from api.contracts.schemas.samples import DNA_SAMPLE_FILE_KEYS, RNA_SAMPLE_FILE_KEYS
from api.core.dna.variant_identity import ensure_variant_identity_fields
from shared import app_config


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
    has_dna = any(bool(args.get(key)) for key in DNA_SAMPLE_FILE_KEYS)
    has_rna = any(bool(args.get(key)) for key in RNA_SAMPLE_FILE_KEYS)
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


def _emulate_perl(var_dict: dict[str, Any]) -> dict[str, Any]:
    """Mimic legacy Perl CSQ field handling: split ampersand-delimited floats and take the max.

    For each transcript in INFO/CSQ, any string field containing ampersand-delimited
    float values is collapsed to the numeric maximum, matching the behaviour of the
    original Perl import script.

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
        A 9-tuple of:
            (slim_transcripts, cosmic_ids, dbsnp_first, pubmed_ids,
             transcript_ids, hgvsc_ids, hgvsp_ids, gene_symbols, hotspots)
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
            "MANE_SELECT",
            "STRAND",
            "IMPACT",
            "CADD_PHRED",
            "CLIN_SIG",
            "VARIANT_CLASS",
        ):
            slim["MANE" if key == "MANE_SELECT" else key] = transcript.get(key)

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
    )


def _selected_transcript_removal(
    csq_arr: list[dict[str, Any]], selected: str
) -> list[dict[str, Any]]:
    """Remove the selected transcript entry from csq_arr in-place by Feature value.

    Args:
        csq_arr: Mutable list of slim CSQ transcript dicts.
        selected: The Feature identifier of the transcript to remove.

    Returns:
        The same list with the first matching entry removed (if found).
    """
    for index, csq in enumerate(csq_arr):
        if csq.get("Feature") == selected:
            del csq_arr[index]
            break
    return csq_arr


def _refseq_no_version(accession: str) -> str:
    """Strip the version suffix from a RefSeq accession (e.g. ``NM_001234.5`` → ``NM_001234``).

    Args:
        accession: RefSeq accession string, with or without a version dot-suffix.

    Returns:
        The accession with everything from the first dot onwards removed.
    """
    return accession.split(".")[0]


def _select_csq(
    csq_arr: list[dict[str, Any]], canonical: dict[str, str]
) -> tuple[dict[str, Any], str]:
    """Select the canonical transcript from a slim CSQ array using a priority hierarchy.

    Priority order:
    1. DB canonical (gene in canonical map and RefSeq matches).
    2. VEP canonical (``CANONICAL == "YES"``).
    3. First protein-coding transcript.
    4. First transcript unconditionally.

    Selection iterates IMPACT order (HIGH → MODERATE → LOW → MODIFIER) before
    descending to lower-priority tiers.

    Args:
        csq_arr: List of slim CSQ transcript dicts (output of ``_parse_transcripts``).
        canonical: Mapping of gene symbol to canonical RefSeq accession (no version).

    Returns:
        A tuple of (selected_csq_dict, selection_source_label) where label is one of
        ``"db"``, ``"vep"``, or ``"random"``.
    """
    db_canonical = -1
    vep_canonical = -1
    first_protein = -1
    for impact in ["HIGH", "MODERATE", "LOW", "MODIFIER"]:
        for idx, csq in enumerate(csq_arr):
            if csq["IMPACT"] != impact:
                continue
            symbol = csq["SYMBOL"]
            feature = csq["Feature"]
            if symbol in canonical and canonical[symbol] == _refseq_no_version(feature):
                db_canonical = idx
                return csq_arr[db_canonical], "db"
            if csq["CANONICAL"] == "YES" and vep_canonical == -1:
                vep_canonical = idx
            if first_protein == -1 and csq["BIOTYPE"] == "protein_coding":
                first_protein = idx
    if vep_canonical >= 0:
        return csq_arr[vep_canonical], "vep"
    if first_protein >= 0:
        return csq_arr[first_protein], "random"
    return csq_arr[0], "random"


def _read_mane(path: str) -> dict[str, dict[str, str]]:
    """Parse a gzipped MANE summary TSV file into a gene-keyed RefSeq/Ensembl mapping.

    Args:
        path: Absolute path to the gzipped MANE summary file.

    Returns:
        A dict mapping Ensembl gene ID (no version) to a sub-dict with keys
        ``"refseq"`` and ``"ensembl"`` (transcript accessions without version).
    """
    mane: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            refseq = row["RefSeq_nuc"].split(".")[0]
            ensembl = row["Ensembl_nuc"].split(".")[0]
            gene = row["Ensembl_Gene"].split(".")[0]
            mane[gene] = {"refseq": refseq, "ensembl": ensembl}
    return mane


class DnaIngestParser:
    """Parse DNA ingest payloads by reading VCF, CNV, biomarker, and coverage files.

    Attributes:
        canonical: Gene-to-RefSeq canonical transcript mapping loaded from DB.
    """

    def __init__(self, canonical: dict[str, str]) -> None:
        """Initialise the parser with a canonical transcript mapping.

        Args:
            canonical: Mapping of gene symbol to canonical RefSeq accession (no version).
        """
        self.canonical = canonical

    def parse(self, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch file-based parsing for all DNA data types present in args.

        Reads VCF (SNVs), CNV JSON, biomarkers JSON, translocation VCF, and
        coverage JSON files according to which keys are populated in args.

        Args:
            args: Validated sample payload dict containing file path keys.

        Returns:
            A preload dict with keys ``snvs``, ``cnvs``, ``biomarkers``,
            ``transloc``, and/or ``cov`` as present in the payload.
        """
        preload: dict[str, Any] = {}
        vcf = runtime_file_path(args, "vcf_files")
        if vcf:
            require_exists("VCF", vcf)
            preload["snvs"] = self._parse_snvs_only(vcf)

        if "cnv" in args:
            cnv_path = runtime_file_path(args, "cnv")
            require_exists("CNV JSON", cnv_path)
            with open(cnv_path, "r", encoding="utf-8") as handle:
                cnv_doc = json.load(handle)
            preload["cnvs"] = [cnv_doc[key] for key in cnv_doc]

        if "biomarkers" in args:
            biomarkers_path = runtime_file_path(args, "biomarkers")
            require_exists("Biomarkers JSON", biomarkers_path)
            with open(biomarkers_path, "r", encoding="utf-8") as handle:
                preload["biomarkers"] = json.load(handle)

        if "transloc" in args:
            transloc_path = runtime_file_path(args, "transloc")
            require_exists("DNA translocations VCF", transloc_path)
            preload["transloc"] = self._parse_transloc_only(transloc_path)

        if "cov" in args:
            cov_path = runtime_file_path(args, "cov")
            require_exists("Coverage JSON", cov_path)
            with open(cov_path, "r", encoding="utf-8") as handle:
                preload["cov"] = json.load(handle)

        return preload

    def _parse_snvs_only(self, infile: str) -> list[dict[str, Any]]:
        """Parse a VEP-annotated SNV VCF into a list of variant dicts.

        Applies FAIL filter exclusions, CSQ transcript selection, allele
        frequency extraction, and variant identity field enrichment.

        Args:
            infile: Absolute path to the SNV VCF file.

        Returns:
            A list of variant dicts ready for persistence.

        Raises:
            ValueError: If a variant record lacks required GT fields (AF/VAF, DP, VD).
        """
        filtered: list[dict[str, Any]] = []
        vcf_object = VariantFile(infile)
        for var in vcf_object.fetch():
            var_dict = cmdvcf.parse_variant(var, vcf_object.header)
            var_csq = var_dict["INFO"]["CSQ"]
            if var_csq:
                all_features = [c.get("Feature") for c in var_csq]
                all_x_genes = [
                    c.get("SYMBOL") for c in var_csq if c.get("Feature", "").startswith("X")
                ]
            else:
                all_features = []
                all_x_genes = []

            if (
                all_features
                and all([f.startswith("X") for f in all_features])
                and not any(
                    g in ["HNF1A", "MZT2A", "SNX9", "KLHDC4", "LMTK3", "PTPA"]
                    for g in list(set(all_x_genes))
                )
            ):
                continue

            if "SVTYPE" in var_dict["INFO"]:
                var_dict["INFO"]["TYPE"] = var_dict["INFO"]["SVTYPE"]
            var_dict = _emulate_perl(var_dict)
            var_dict.update(_pick_af_fields(var_dict))
            var_dict["variant_class"] = var_csq[0].get("VARIANT_CLASS") if var_csq else None

            (
                slim_csq,
                cosmic_list,
                dbsnp,
                pubmed_list,
                transcripts_list,
                cdna_list,
                prot_list,
                genes_list,
                hotspots,
            ) = _parse_transcripts(var_csq)

            selected_csq, selected_source = _select_csq(slim_csq, self.canonical)
            var_dict["INFO"]["CSQ"] = _selected_transcript_removal(
                slim_csq, selected_csq["Feature"]
            )
            var_dict["INFO"]["selected_CSQ"] = selected_csq
            var_dict["INFO"]["selected_CSQ_criteria"] = selected_source
            var_dict["selected_csq_feature"] = selected_csq["Feature"]
            var_dict["HGVSp"] = prot_list
            var_dict["HGVSc"] = cdna_list
            var_dict["genes"] = genes_list
            var_dict["transcripts"] = transcripts_list
            var_dict["INFO"]["CSQ"] = slim_csq
            var_dict["cosmic_ids"] = cosmic_list
            var_dict["dbsnp_id"] = dbsnp
            var_dict["pubmed_ids"] = pubmed_list
            var_dict["hotspots"] = [hotspots]
            var_dict["simple_id"] = (
                f"{var_dict['CHROM']}_{var_dict['POS']}_{var_dict['REF']}_{var_dict['ALT']}"
            )
            var_dict["INFO"]["variant_callers"] = var_dict["INFO"]["variant_callers"].split("|")
            var_dict["FILTER"] = var_dict["FILTER"].split(";")

            filters = set(var_dict["FILTER"])
            if "FAIL_NVAF" in filters or "FAIL_LONGDEL" in filters:
                continue
            if any(f.startswith("FAIL_PON_") for f in filters):
                continue

            del var_dict["FORMAT"]
            for index, sample in enumerate(var_dict["GT"]):
                required = {"AF", "VAF", "DP", "VD", "GT"}
                if not required.intersection(sample.keys()) or "DP" not in sample:
                    raise ValueError("Invalid VCF: expected AF/VAF, DP, VD and GT in GT entries")
                var_dict["GT"][index]["type"] = "case" if index == 0 else "control"
                var_dict["GT"][index]["AF"] = var_dict["GT"][index]["VAF"]
                del var_dict["GT"][index]["VAF"]
                var_dict["GT"][index]["sample"] = var_dict["GT"][index]["_sample_id"]
                del var_dict["GT"][index]["_sample_id"]

            filtered.append(ensure_variant_identity_fields(var_dict))

        return filtered

    @staticmethod
    def _parse_transloc_only(infile: str) -> list[dict[str, Any]]:
        """Parse a translocation VCF into a list of gene-fusion variant dicts.

        Processes ANN fields, extracts MANE select annotations, and retains only
        variants annotated as ``gene_fusion`` or ``bidirectional_gene_fusion``.

        Args:
            infile: Absolute path to the translocation VCF file.

        Returns:
            A list of variant dicts representing confirmed gene fusions.
        """
        mane = _read_mane(app_config.MANE_SUMMARY_PATH)
        filtered_data: list[dict[str, Any]] = []
        vcf_object = VariantFile(infile)
        for var in vcf_object.fetch():
            var_dict = cmdvcf.parse_variant(var, vcf_object.header)
            if "<" in var_dict["ALT"]:
                continue

            keep_variant = 0
            mane_select: dict[str, Any] = {}
            all_new_ann: list[dict[str, Any]] = []
            add_mane = 0

            for ann in var_dict["INFO"]["ANN"]:
                n_mane = 0
                genes = ann["Gene_ID"].split("&")
                for gene in genes:
                    enst = mane.get(gene, {}).get("ensembl", "NO_MANE_TRANSCRIPT")
                    if enst in ann["HGVS.p"]:
                        n_mane += 1

                new_ann: dict[str, Any] = {}
                for key, value in ann.items():
                    if key == "Annotation":
                        for annotation in value:
                            if annotation in {"gene_fusion", "bidirectional_gene_fusion"}:
                                keep_variant = 1
                    new_ann[key.replace(".", "")] = value
                all_new_ann.append(new_ann)

                if n_mane > 0 and n_mane == len(genes):
                    mane_select = new_ann
                    add_mane = 1

            del var_dict["INFO"]["ANN"]
            var_dict["INFO"]["ANN"] = all_new_ann
            if add_mane:
                var_dict["INFO"]["MANE_ANN"] = mane_select
            if keep_variant:
                filtered_data.append(var_dict)

        return filtered_data


class RnaIngestParser:
    """Parse RNA ingest payloads by reading fusion, expression, classification, and QC files."""

    @staticmethod
    def parse(args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch file-based parsing for all RNA data types present in args.

        Args:
            args: Validated sample payload dict containing RNA file path keys.

        Returns:
            A preload dict with keys ``fusions``, ``rna_expr``, ``rna_class``,
            and/or ``rna_qc`` as present in the payload.
        """
        preload: dict[str, Any] = {}
        fusions = runtime_file_path(args, "fusion_files")
        if fusions:
            require_exists("Fusions JSON", fusions)
            with open(fusions, "r", encoding="utf-8") as handle:
                preload["fusions"] = json.load(handle)

        if "expression_path" in args:
            expr_path = runtime_file_path(args, "expression_path")
            require_exists("Expression JSON", expr_path)
            with open(expr_path, "r", encoding="utf-8") as handle:
                preload["rna_expr"] = json.load(handle)
        if "classification_path" in args:
            class_path = runtime_file_path(args, "classification_path")
            require_exists("Classification JSON", class_path)
            with open(class_path, "r", encoding="utf-8") as handle:
                preload["rna_class"] = json.load(handle)
        if "qc" in args:
            qc_path = runtime_file_path(args, "qc")
            require_exists("QC JSON", qc_path)
            with open(qc_path, "r", encoding="utf-8") as handle:
                preload["rna_qc"] = json.load(handle)

        return preload
