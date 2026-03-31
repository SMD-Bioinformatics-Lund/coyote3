"""Internal sample-ingestion service for API-first ingest flows."""

from __future__ import annotations

import csv
import gzip
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import yaml
from bson.objectid import ObjectId
from pymongo.errors import BulkWriteError, DuplicateKeyError
from pysam import VariantFile

import config
from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
    normalize_collection_document,
    supported_collections,
)
from api.contracts.schemas.samples import (
    DNA_SAMPLE_FILE_KEYS,
    RNA_SAMPLE_FILE_KEYS,
    SAMPLE_SOURCE_PATH_KEYS,
    SamplesDoc,
)
from api.core.dna.variant_identity import ensure_variant_identity_fields
from api.extensions import store
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.parsers import cmdvcf

logger = logging.getLogger(__name__)

_CASE_CONTROL_KEYS = [
    "case_id",
    "control_id",
    "clarity_control_id",
    "clarity_case_id",
    "clarity_case_pool_id",
    "clarity_control_pool_id",
    "case_ffpe",
    "control_ffpe",
    "case_sequencing_run",
    "control_sequencing_run",
    "case_reads",
    "control_reads",
    "case_purity",
    "control_purity",
]


def _exists(path: str | None) -> bool:
    return bool(path) and os.path.exists(path)


def _require_exists(label: str, path: str | None) -> None:
    if not _exists(path):
        raise FileNotFoundError(f"{label} missing or not readable: {path}")


def _validate_yaml_payload_like_import_script(payload: dict[str, Any]) -> None:
    """Mirror `scripts/import_coyote_sample.py::validate_yaml` mandatory-field guard."""
    if (
        ("vcf_files" not in payload or "fusion_files" not in payload)
        and "groups" not in payload
        and "name" not in payload
        and "genome_build" not in payload
    ):
        raise ValueError("YAML is missing mandatory fields: vcf, groups, name or build")


def _normalize_case_control(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = dict(args)
    for key in _CASE_CONTROL_KEYS:
        if key in normalized and (normalized[key] is None or normalized[key] == "null"):
            normalized[key] = None

    case: dict[str, Any] = {}
    control: dict[str, Any] = {}
    for key in _CASE_CONTROL_KEYS:
        if "case" in key:
            case[key.replace("case_", "")] = normalized.get(key)
        elif "control" in key:
            control[key.replace("control_", "")] = normalized.get(key)
    return case, control


def build_sample_meta_dict(args: dict[str, Any]) -> dict[str, Any]:
    sample_dict: dict[str, Any] = {}
    case_dict, control_dict = _normalize_case_control(args)
    blocked = {
        "load",
        "command_selection",
        "debug_logger",
        "quiet",
        "increment",
        "update",
        "dev",
        "_runtime_files",
    }
    for key, value in args.items():
        if key in blocked:
            continue
        if key in _CASE_CONTROL_KEYS and key not in {"case_id", "control_id"}:
            continue
        sample_dict[key] = value

    sample_dict["case"] = case_dict
    if args.get("control_id"):
        sample_dict["control"] = control_dict
    return sample_dict


def _runtime_file_path(args: dict[str, Any], key: str) -> str | None:
    runtime = args.get("_runtime_files")
    if isinstance(runtime, dict):
        value = runtime.get(key)
        if value:
            return str(value)
    value = args.get(key)
    return str(value) if value else None


def _normalize_uploaded_checksums(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in payload.items():
        checksum_key = str(key or "").strip()
        checksum_val = str(value or "").strip().lower()
        if not checksum_key or not checksum_val:
            continue
        normalized[checksum_key] = checksum_val
    return normalized


def _infer_omics_layer(args: dict[str, Any]) -> str | None:
    has_dna = any(bool(args.get(key)) for key in DNA_SAMPLE_FILE_KEYS)
    has_rna = any(bool(args.get(key)) for key in RNA_SAMPLE_FILE_KEYS)
    if has_dna and has_rna:
        raise ValueError("Data types conflict: both RNA and DNA detected.")
    if has_dna:
        return "dna"
    if has_rna:
        return "rna"
    return None


def _catch_left_right(case_id: str, name: str) -> tuple[str, str, str]:
    pattern = rf"(.*)({re.escape(case_id)})(.*)"
    match = re.match(pattern, name)
    if not match:
        return "", "", ""
    return match.group(1), match.group(3), match.group(2)


def _next_unique_name(case_id: str, increment: bool) -> str:
    existing_exact = list(store.sample_handler.get_collection().find({"name": case_id}))
    if not existing_exact:
        return case_id
    if not increment:
        raise ValueError("Sample already exists; set increment=true to auto-suffix")

    suffixes: list[str] = []
    true_matches = 0
    for doc in store.sample_handler.get_collection().find({"name": {"$regex": case_id}}):
        left, right, true = _catch_left_right(case_id, doc["name"])
        if right and not left and true:
            suffixes.append(right)
            true_matches += 1

    max_suffix = 1
    if true_matches:
        if not suffixes:
            raise ValueError("Multiple exact matches found for sample name")
        for suffix in suffixes:
            match = re.match(r"-\d+", suffix)
            if match:
                number = int(suffix.replace("-", ""))
                if number > max_suffix:
                    max_suffix = number

    return f"{case_id}-{max_suffix + 1}"


def _split_on_colon(value: str | None) -> str | None:
    if not value:
        return value
    parts = value.split(":")
    return parts[1] if len(parts) > 1 else value


def _split_on_ampersand(found: dict[str, int], raw: str) -> dict[str, int]:
    try:
        for piece in raw.split("&"):
            found[piece] = 1
        return found
    except Exception:
        found[str(raw)] = 1
        return found


def _collect_dbsnp(found: dict[str, int], raw: str) -> dict[str, int]:
    for snp in raw.split("&"):
        if snp.startswith("rs"):
            found[snp] = 1
    return found


def _collect_hotspots(hotspot_dict: dict[str, list]) -> dict[str, list]:
    cleaned: dict[str, list] = {}
    for hotspot, ids in hotspot_dict.items():
        formatted = list(set(filter(None, ids)))
        if formatted:
            cleaned[hotspot] = formatted
    return cleaned


def _is_float(value: str) -> bool:
    try:
        float(value)
        return len(value.split(".")) > 1
    except Exception:
        return False


def _emulate_perl(var_dict: dict[str, Any]) -> dict[str, Any]:
    for transcript in var_dict["INFO"]["CSQ"]:
        for key in list(transcript.keys()):
            if isinstance(transcript[key], str):
                data = transcript[key].split("&")
                if _is_float(data[0]):
                    transcript[key] = float(max(float(x) for x in data))
    return var_dict


def _parse_allele_freq(freq_str: str | None, allele: str) -> float:
    if freq_str:
        for item in freq_str.split("&"):
            parts = item.split(":")
            if parts[0] == allele:
                return float(parts[1])
    return 0.0


def _max_gnomad(gnomad: str | None) -> float | str | None:
    if not gnomad:
        return None
    try:
        return float(max(gnomad.split("&")))
    except Exception:
        return gnomad


def _pick_af_fields(var: dict[str, Any]) -> dict[str, Any]:
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
    for index, csq in enumerate(csq_arr):
        if csq.get("Feature") == selected:
            del csq_arr[index]
            break
    return csq_arr


def _refseq_no_version(accession: str) -> str:
    return accession.split(".")[0]


def _select_csq(
    csq_arr: list[dict[str, Any]], canonical: dict[str, str]
) -> tuple[dict[str, Any], str]:
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
    def __init__(self, canonical: dict[str, str]) -> None:
        self.canonical = canonical

    def parse(self, args: dict[str, Any]) -> dict[str, Any]:
        preload: dict[str, Any] = {}
        vcf = _runtime_file_path(args, "vcf_files")
        if vcf:
            _require_exists("VCF", vcf)
            preload["snvs"] = self._parse_snvs_only(vcf)

        if "cnv" in args:
            cnv_path = _runtime_file_path(args, "cnv")
            _require_exists("CNV JSON", cnv_path)
            with open(cnv_path, "r", encoding="utf-8") as handle:
                cnv_doc = json.load(handle)
            preload["cnvs"] = [cnv_doc[key] for key in cnv_doc]

        if "biomarkers" in args:
            biomarkers_path = _runtime_file_path(args, "biomarkers")
            _require_exists("Biomarkers JSON", biomarkers_path)
            with open(biomarkers_path, "r", encoding="utf-8") as handle:
                preload["biomarkers"] = json.load(handle)

        if "transloc" in args:
            transloc_path = _runtime_file_path(args, "transloc")
            _require_exists("DNA translocations VCF", transloc_path)
            preload["transloc"] = self._parse_transloc_only(transloc_path)

        if "cov" in args:
            cov_path = _runtime_file_path(args, "cov")
            _require_exists("Coverage JSON", cov_path)
            with open(cov_path, "r", encoding="utf-8") as handle:
                preload["cov"] = json.load(handle)

        return preload

    def _parse_snvs_only(self, infile: str) -> list[dict[str, Any]]:
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
        mane = _read_mane(config.mane)
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
    @staticmethod
    def parse(args: dict[str, Any]) -> dict[str, Any]:
        preload: dict[str, Any] = {}
        fusions = _runtime_file_path(args, "fusion_files")
        if fusions:
            _require_exists("Fusions JSON", fusions)
            with open(fusions, "r", encoding="utf-8") as handle:
                preload["fusions"] = json.load(handle)

        if "expression_path" in args:
            expr_path = _runtime_file_path(args, "expression_path")
            _require_exists("Expression JSON", expr_path)
            with open(expr_path, "r", encoding="utf-8") as handle:
                preload["rna_expr"] = json.load(handle)
        if "classification_path" in args:
            class_path = _runtime_file_path(args, "classification_path")
            _require_exists("Classification JSON", class_path)
            with open(class_path, "r", encoding="utf-8") as handle:
                preload["rna_class"] = json.load(handle)
        if "qc" in args:
            qc_path = _runtime_file_path(args, "qc")
            _require_exists("QC JSON", qc_path)
            with open(qc_path, "r", encoding="utf-8") as handle:
                preload["rna_qc"] = json.load(handle)

        return preload


class InternalIngestService:
    """API-side service that ingests a fresh sample plus analysis data atomically."""

    @staticmethod
    def _invalidate_dashboard_cache_after_ingest() -> None:
        """Refresh dashboard caches after ingest writes into sample/variant collections."""
        try:
            store.variant_handler.invalidate_dashboard_metrics_cache()
        except Exception as exc:
            logger.warning("ingest_dashboard_variant_cache_invalidate_failed error=%s", exc)
        try:
            invalidate_dashboard_summary_cache(store)
        except Exception as exc:
            logger.warning("ingest_dashboard_summary_cache_invalidate_failed error=%s", exc)

    @staticmethod
    def list_supported_collections() -> list[str]:
        """List collection names that can be validated/inserted via ingest APIs."""
        return supported_collections()

    @staticmethod
    def _resolve_collection(name: str):
        """Resolve collection by ingest alias from store handlers or raw DB."""
        handler_map = {
            "variants": "variant_handler",
            "cnvs": "cnv_handler",
            "biomarkers": "biomarker_handler",
            "transloc": "transloc_handler",
            "panel_coverage": "coverage_handler",
            "fusions": "fusion_handler",
            "rna_expression": "rna_expression_handler",
            "rna_classification": "rna_classification_handler",
            "rna_qc": "rna_qc_handler",
        }
        handler_name = handler_map.get(name)
        if handler_name and hasattr(store, handler_name):
            return getattr(store, handler_name).get_collection()
        return store.coyote_db[name]

    @staticmethod
    def parse_yaml_payload(yaml_content: str) -> dict[str, Any]:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            raise ValueError("YAML body must decode to an object")
        _validate_yaml_payload_like_import_script(parsed)
        return parsed

    @staticmethod
    def _canonical_map() -> dict[str, str]:
        mapping: dict[str, str] = {}
        for doc in store.coyote_db["refseq_canonical"].find({}):
            gene = doc.get("gene")
            canonical = doc.get("canonical")
            if gene and canonical:
                mapping[gene] = canonical
        return mapping

    @classmethod
    def _parse_preload(cls, args: dict[str, Any]) -> dict[str, Any]:
        omics_layer = str(args.get("omics_layer") or "").strip().lower()
        if not omics_layer:
            omics_layer = _infer_omics_layer(args) or ""
        if omics_layer == "dna":
            return DnaIngestParser(cls._canonical_map()).parse(args)
        if omics_layer == "rna":
            return RnaIngestParser.parse(args)
        raise ValueError("Could not determine data type (DNA/RNA) from payload")

    @classmethod
    def _normalize_collection_docs(
        cls, collection: str, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for doc in docs:
            normalized.append(normalize_collection_document(collection, doc))
        return normalized

    @classmethod
    def _write_dependents(
        cls,
        *,
        preload: dict[str, Any],
        sample_id: ObjectId,
        sample_name: str,
    ) -> dict[str, int]:
        sid = str(sample_id)
        written: dict[str, int] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in preload:
                continue
            payload = preload[key]
            col = cls._resolve_collection(col_name)

            if key in INGEST_SINGLE_DOCUMENT_KEYS:
                if not isinstance(payload, dict):
                    raise TypeError(f"{key} expected dict, got {type(payload).__name__}")
                doc = dict(payload)
                doc["SAMPLE_ID"] = sid
                if key == "cov":
                    doc["sample"] = sample_name
                normalized_doc = cls._normalize_collection_docs(col_name, [doc])[0]
                col.insert_one(normalized_doc)
                written[key] = 1
                continue

            if not isinstance(payload, (list, tuple)):
                raise TypeError(f"{key} expected list, got {type(payload).__name__}")
            docs: list[dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    raise TypeError(f"{key} contains non-dict item")
                doc = dict(item)
                doc["SAMPLE_ID"] = sid
                if key == "snvs":
                    doc = ensure_variant_identity_fields(doc)
                docs.append(doc)
            normalized_docs = cls._normalize_collection_docs(col_name, docs)
            if normalized_docs:
                col.insert_many(normalized_docs)
            written[key] = len(normalized_docs)
        return written

    @classmethod
    def ingest_dependents(
        cls,
        *,
        sample_id: str,
        sample_name: str,
        delete_existing: bool,
        preload: dict[str, Any],
    ) -> dict[str, int]:
        """Insert dependent analysis payload for an existing sample id."""
        sid = str(sample_id)
        written: dict[str, int] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in preload:
                continue
            col = cls._resolve_collection(col_name)
            if delete_existing:
                col.delete_many({"SAMPLE_ID": sid})

            raw_payload: Any = preload[key]
            if key in INGEST_SINGLE_DOCUMENT_KEYS:
                if not isinstance(raw_payload, dict):
                    raise ValueError(f"{key} expected dict payload")
                doc = dict(raw_payload)
                doc["SAMPLE_ID"] = sid
                if key == "cov":
                    doc["sample"] = sample_name
                normalized_doc = cls._normalize_collection_docs(col_name, [doc])[0]
                col.insert_one(normalized_doc)
                written[key] = 1
                continue

            if not isinstance(raw_payload, (list, tuple)):
                raise ValueError(f"{key} expected list payload")
            docs: list[dict[str, Any]] = []
            for item in raw_payload:
                if not isinstance(item, dict):
                    raise ValueError(f"{key} contains non-dict item")
                doc = dict(item)
                doc["SAMPLE_ID"] = sid
                if key == "snvs":
                    doc = ensure_variant_identity_fields(doc)
                docs.append(doc)
            normalized_docs = cls._normalize_collection_docs(col_name, docs)
            if normalized_docs:
                col.insert_many(normalized_docs)
            written[key] = len(normalized_docs)
        return written

    @classmethod
    def _cleanup(cls, sample_id: ObjectId) -> None:
        sid = str(sample_id)
        for collection in INGEST_DEPENDENT_COLLECTIONS.values():
            try:
                store.coyote_db[collection].delete_many({"SAMPLE_ID": sid})
            except Exception:
                pass
        try:
            store.sample_handler.get_collection().delete_one({"_id": sample_id})
        except Exception:
            pass

    @staticmethod
    def _data_counts(preload: dict[str, Any]) -> dict[str, int | bool]:
        return {
            key: (len(preload[key]) if isinstance(preload[key], list) else bool(preload[key]))
            for key in preload
        }

    @classmethod
    def _snapshot_dependents(
        cls, *, sample_id: ObjectId, keys: set[str]
    ) -> dict[str, list[dict[str, Any]]]:
        sid = str(sample_id)
        backup: dict[str, list[dict[str, Any]]] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key in keys:
                backup[key] = list(store.coyote_db[col_name].find({"SAMPLE_ID": sid}))
        return backup

    @classmethod
    def _restore_dependents(
        cls, *, sample_id: ObjectId, sample_name: str, backup: dict[str, list[dict[str, Any]]]
    ) -> None:
        sid = str(sample_id)
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in backup:
                continue
            col = store.coyote_db[col_name]
            col.delete_many({"SAMPLE_ID": sid})
            docs = backup[key]
            if docs:
                restored: list[dict[str, Any]] = []
                for doc in docs:
                    d = dict(doc)
                    d.pop("_id", None)
                    if key == "cov":
                        d["sample"] = sample_name
                    restored.append(d)
                col.insert_many(restored)

    @classmethod
    def _replace_dependents(
        cls, *, preload: dict[str, Any], sample_id: ObjectId, sample_name: str
    ) -> dict[str, int]:
        sid = str(sample_id)
        keys_to_replace = set(preload.keys())
        backup = cls._snapshot_dependents(sample_id=sample_id, keys=keys_to_replace)
        try:
            for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
                if key in keys_to_replace:
                    store.coyote_db[col_name].delete_many({"SAMPLE_ID": sid})
            return cls._write_dependents(
                preload=preload, sample_id=sample_id, sample_name=sample_name
            )
        except Exception:
            cls._restore_dependents(sample_id=sample_id, sample_name=sample_name, backup=backup)
            raise

    @classmethod
    def _prepare_update_payload(
        cls, *, sample_doc: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        normalized = dict(payload)
        existing_layer = str(sample_doc.get("omics_layer") or "").strip().lower()
        if existing_layer not in {"dna", "rna"}:
            existing_layer = _infer_omics_layer(sample_doc) or ""
        if existing_layer not in {"dna", "rna"}:
            raise ValueError("Cannot determine existing sample data type for update")

        requested_layer = str(normalized.get("omics_layer") or existing_layer).strip().lower()
        if requested_layer != existing_layer:
            raise ValueError(
                f"Sample omics_layer is '{existing_layer}' and cannot be changed to '{requested_layer}'"
            )

        forbidden_keys = RNA_SAMPLE_FILE_KEYS if existing_layer == "dna" else DNA_SAMPLE_FILE_KEYS
        bad_keys = [key for key in forbidden_keys if normalized.get(key)]
        if bad_keys:
            raise ValueError(
                f"Cannot add {'RNA' if existing_layer == 'dna' else 'DNA'} data to an existing {existing_layer.upper()} sample"
            )

        normalized["omics_layer"] = existing_layer
        return normalized

    @classmethod
    def _update_meta_fields(
        cls,
        *,
        sample_id: ObjectId,
        payload_meta: dict[str, Any],
        block_fields: set[str],
    ) -> None:
        sample_col = store.sample_handler.get_collection()
        current = sample_col.find_one({"_id": sample_id}) or {}
        update_fields: dict[str, Any] = {}
        for key, value in payload_meta.items():
            if key in {"_id", "name"}:
                continue
            if key in current and current[key] != value:
                if key in block_fields:
                    raise ValueError(f"No support to update {key} as of yet")
                update_fields[key] = value
            elif key not in current:
                update_fields[key] = value
        if update_fields:
            sample_col.update_one({"_id": sample_id}, {"$set": update_fields}, upsert=False)

    @classmethod
    def _ingest_update(cls, payload: dict[str, Any]) -> dict[str, Any]:
        sample_col = store.sample_handler.get_collection()

        if not payload:
            raise ValueError("sample payload is required")
        if not payload.get("name"):
            raise ValueError("name is required for update")

        current_doc = sample_col.find_one({"name": payload["name"]})
        if not current_doc:
            raise ValueError("Sample not found for update")

        sample_id = current_doc["_id"]

        # Prepare update payload using existing sample context
        parsed_payload = cls._prepare_update_payload(
            sample_doc=current_doc,
            payload=dict(payload),
        )

        # Strip DB-managed / operation-only fields before validation
        parsed_payload.pop("_id", None)
        parsed_payload.pop("data_counts", None)
        parsed_payload.pop("time_added", None)
        parsed_payload.pop("ingest_status", None)
        parsed_payload.pop("report_num", None)
        parsed_payload.pop("increment", None)
        parsed_payload.pop("update_existing", None)
        uploaded_checksums = _normalize_uploaded_checksums(
            parsed_payload.pop("_uploaded_file_checksums", None)
        )

        # Validate merged document shape through the strict contract.
        merged_doc = dict(current_doc)
        merged_doc.update(parsed_payload)
        if uploaded_checksums:
            existing_checksums = _normalize_uploaded_checksums(
                current_doc.get("uploaded_file_checksums", {})
            )
            existing_checksums.update(uploaded_checksums)
            merged_doc["uploaded_file_checksums"] = existing_checksums
        validated_merged = SamplesDoc.model_validate(merged_doc)
        validated_payload = validated_merged.model_dump(exclude_none=True)

        preload_payload: dict[str, Any] = {"omics_layer": validated_payload["omics_layer"]}
        runtime_files = parsed_payload.get("_runtime_files")
        if isinstance(runtime_files, dict) and runtime_files:
            preload_payload["_runtime_files"] = dict(runtime_files)
        for key in SAMPLE_SOURCE_PATH_KEYS:
            if key in parsed_payload and parsed_payload.get(key):
                preload_payload[key] = parsed_payload[key]

        preload = cls._parse_preload(preload_payload)
        data_counts = dict(current_doc.get("data_counts") or {})
        data_counts.update(cls._data_counts(preload))

        # Keep the same update flow ordering as scripts/import_coyote_sample.py:
        # update sample metadata + counts/status first, then rewrite dependents.
        merged_doc["name"] = current_doc["name"]
        merged_doc["data_counts"] = data_counts
        merged_doc["ingest_status"] = "ready"

        cls._update_meta_fields(
            sample_id=sample_id,
            payload_meta=build_sample_meta_dict(validated_merged.model_dump(exclude_none=True)),
            block_fields={"assay"},
        )

        sample_col.update_one(
            {"_id": sample_id},
            {"$set": {"ingest_status": "ready", "data_counts": data_counts}},
            upsert=False,
        )

        written = cls._replace_dependents(
            preload=preload,
            sample_id=sample_id,
            sample_name=str(current_doc["name"]),
        )

        cls._invalidate_dashboard_cache_after_ingest()

        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": str(current_doc["name"]),
            "written": written,
            "data_counts": data_counts,
        }

    @classmethod
    def ingest_sample_bundle(
        cls,
        payload: dict[str, Any],
        *,
        allow_update: bool = False,
        increment: bool = False,
    ) -> dict[str, Any]:
        if not payload:
            raise ValueError("sample payload is required")

        parsed_payload = dict(payload)
        parsed_payload.pop("_id", None)
        parsed_payload.pop("data_counts", None)
        parsed_payload.pop("time_added", None)
        parsed_payload.pop("ingest_status", None)
        parsed_payload.pop("report_num", None)
        parsed_payload.pop("increment", None)
        parsed_payload.pop("update_existing", None)
        uploaded_checksums = _normalize_uploaded_checksums(
            parsed_payload.pop("_uploaded_file_checksums", None)
        )

        if not parsed_payload.get("name"):
            raise ValueError("name is required")

        if allow_update:
            return cls._ingest_update(parsed_payload)

        validated_sample = SamplesDoc.model_validate(parsed_payload)
        validated_payload = validated_sample.model_dump(exclude_none=True)

        preload = cls._parse_preload(validated_payload)
        sample_name = _next_unique_name(str(validated_payload["name"]), bool(increment))
        sample_id = ObjectId()
        data_counts = cls._data_counts(preload)

        try:
            written = cls._write_dependents(
                preload=preload,
                sample_id=sample_id,
                sample_name=sample_name,
            )

            meta = build_sample_meta_dict(validated_payload)
            meta.update(
                {
                    "_id": sample_id,
                    "name": sample_name,
                    "data_counts": data_counts,
                    "time_added": datetime.now(timezone.utc),
                    "ingest_status": "ready",
                }
            )
            if uploaded_checksums:
                meta["uploaded_file_checksums"] = uploaded_checksums

            final_sample = SamplesDoc.model_validate(meta)
            store.sample_handler.get_collection().insert_one(
                final_sample.model_dump(exclude_none=True)
            )

            cls._invalidate_dashboard_cache_after_ingest()

        except Exception:
            cls._cleanup(sample_id)
            raise

        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": sample_name,
            "written": written,
            "data_counts": data_counts,
        }

    @classmethod
    def insert_collection_document(
        cls, *, collection: str, document: dict[str, Any], ignore_duplicate: bool = False
    ) -> dict[str, Any]:
        """Validate and insert one document into a supported collection."""
        normalized_doc = normalize_collection_document(collection, document)
        try:
            result = cls._resolve_collection(collection).insert_one(dict(normalized_doc))
        except DuplicateKeyError:
            if ignore_duplicate:
                return {
                    "status": "ok",
                    "collection": collection,
                    "inserted_count": 0,
                }
            raise
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": str(result.inserted_id),
        }

    @classmethod
    def insert_collection_documents(
        cls, *, collection: str, documents: list[dict[str, Any]], ignore_duplicates: bool = False
    ) -> dict[str, Any]:
        """Validate and insert many documents into a supported collection."""
        if not documents:
            return {"status": "ok", "collection": collection, "inserted_count": 0}
        normalized_docs = cls._normalize_collection_docs(collection, documents)
        inserted_count = 0
        try:
            result = cls._resolve_collection(collection).insert_many(
                [dict(doc) for doc in normalized_docs], ordered=False
            )
            inserted_count = len(result.inserted_ids)
        except BulkWriteError as exc:
            if not ignore_duplicates:
                raise
            details = exc.details or {}
            inserted_count = int(details.get("nInserted", 0))
            write_errors = details.get("writeErrors", []) or []
            non_duplicate_errors = [w for w in write_errors if w.get("code") != 11000]
            if non_duplicate_errors:
                raise
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": inserted_count,
        }

    @classmethod
    def upsert_collection_document(
        cls,
        *,
        collection: str,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        """Validate and replace one document in a supported collection."""
        if not isinstance(match, dict) or not match:
            raise ValueError("match must be a non-empty object")
        normalized_doc = normalize_collection_document(collection, document)
        result = cls._resolve_collection(collection).replace_one(
            filter=match,
            replacement=normalized_doc,
            upsert=bool(upsert),
        )
        return {
            "status": "ok",
            "collection": collection,
            "matched_count": int(result.matched_count or 0),
            "modified_count": int(result.modified_count or 0),
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }
