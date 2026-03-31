"""Parser helpers for internal DNA/RNA ingest payloads."""

from __future__ import annotations

import csv
import gzip
import json
import os
from typing import Any

from pysam import VariantFile

import config
from api.contracts.schemas.samples import DNA_SAMPLE_FILE_KEYS, RNA_SAMPLE_FILE_KEYS
from api.core.dna.variant_identity import ensure_variant_identity_fields
from api.parsers import cmdvcf


def _exists(path: str | None) -> bool:
    return bool(path) and os.path.exists(path)


def require_exists(label: str, path: str | None) -> None:
    if not _exists(path):
        raise FileNotFoundError(f"{label} missing or not readable: {path}")


def runtime_file_path(args: dict[str, Any], key: str) -> str | None:
    runtime = args.get("_runtime_files")
    if isinstance(runtime, dict):
        value = runtime.get(key)
        if value:
            return str(value)
    value = args.get(key)
    return str(value) if value else None


def infer_omics_layer(args: dict[str, Any]) -> str | None:
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
