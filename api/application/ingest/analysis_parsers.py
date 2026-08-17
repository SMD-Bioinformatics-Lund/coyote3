"""DNA and RNA analysis-file parsers for sample ingest."""

from __future__ import annotations

import json
from typing import Any

from pysam import VariantFile

from api.config.constants import primary_analysis_file_key
from api.domain.common.parsers import cmdvcf
from api.domain.core.dna.transcript_payloads import compact_selected_csq
from api.domain.core.dna.variant_identity import ensure_variant_identity_fields

from .parsers import (
    _build_anno_vep_docs,
    _build_transcript_vault_rows,
    _emulate_perl,
    _infer_cnv_type,
    _normalize_biomarkers_doc,
    _normalize_callers_field,
    _normalize_cnv_ratio,
    _normalize_fusion_docs,
    _normalize_nprobes_field,
    _normalize_transloc_doc,
    _parse_transcripts,
    _pick_af_fields,
    _select_csq,
    require_exists,
    runtime_file_path,
)


def _normalize_pgx_document(payload: Any) -> dict[str, Any]:
    """Preserve one sample-scoped PGX payload regardless of its JSON root shape."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("PGX JSON arrays must contain objects")
        return {"records": payload}
    raise ValueError("PGX JSON must decode to an object or an array of objects")


class DnaIngestParser:
    """Parse DNA ingest payloads by reading VCF, CNV, biomarker, and coverage files."""

    def __init__(
        self,
        *,
        hgnc_by_id: dict[str, dict[str, Any]] | None = None,
        hgnc_by_symbol: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialise the parser with transcript and HGNC reference metadata.

        Args:
            hgnc_by_id: HGNC metadata keyed by ``HGNC:<id>``.
            hgnc_by_symbol: HGNC metadata keyed by approved, previous, and alias symbols.
        """
        self.hgnc_by_id = hgnc_by_id or {}
        self.hgnc_by_symbol = hgnc_by_symbol or {}

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
        vcf = runtime_file_path(args, primary_analysis_file_key("dna", "SNV"))
        if vcf:
            require_exists("VCF", vcf)
            snvs = self._parse_snvs_only(vcf)
            preload["snvs"] = snvs
            anno_vep = _build_anno_vep_docs(
                snvs,
                (args.get("database_versions") or {}).get("vep"),
            )
            if anno_vep:
                preload["anno_vep"] = anno_vep
            for variant in snvs:
                (variant.get("INFO") or {}).pop("CSQ", None)

        cnv_path = runtime_file_path(args, primary_analysis_file_key("dna", "CNV"))
        if cnv_path:
            require_exists("CNV JSON", cnv_path)
            with open(cnv_path, "r", encoding="utf-8") as handle:
                cnv_doc = json.load(handle)
            preload["cnvs"] = self._parse_cnvs_only(cnv_doc)

        biomarkers_path = runtime_file_path(args, primary_analysis_file_key("dna", "BIOMARKER"))
        if biomarkers_path:
            require_exists("Biomarkers JSON", biomarkers_path)
            with open(biomarkers_path, "r", encoding="utf-8") as handle:
                preload["biomarkers"] = _normalize_biomarkers_doc(json.load(handle))

        transloc_path = runtime_file_path(args, primary_analysis_file_key("dna", "TRANSLOCATION"))
        if transloc_path:
            require_exists("DNA translocations VCF", transloc_path)
            preload["transloc"] = self._parse_transloc_only(transloc_path)

        cov_path = runtime_file_path(args, primary_analysis_file_key("dna", "COVERAGE"))
        if cov_path:
            require_exists("Coverage JSON", cov_path)
            with open(cov_path, "r", encoding="utf-8") as handle:
                preload["cov"] = json.load(handle)

        pgx_path = runtime_file_path(args, primary_analysis_file_key("dna", "PGX"))
        if pgx_path:
            require_exists("PGX data", pgx_path)
            with open(pgx_path, "r", encoding="utf-8") as handle:
                preload["pgx"] = _normalize_pgx_document(json.load(handle))

        return preload

    @staticmethod
    def _parse_cnvs_only(cnv_doc: Any) -> list[dict[str, Any]]:
        """Normalize pipeline CNV JSON into a list of contract-shaped CNV docs."""
        if isinstance(cnv_doc, list):
            rows = [dict(row) for row in cnv_doc if isinstance(row, dict)]
        elif isinstance(cnv_doc, dict):
            rows = []
            for key, value in cnv_doc.items():
                if not isinstance(value, dict):
                    continue
                row = dict(value)
                row.setdefault("_pipeline_key", key)
                rows.append(row)
        else:
            raise ValueError("CNV JSON must decode to an object or list of objects")

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            normalized = dict(row)
            normalized["callers"] = _normalize_callers_field(normalized.get("callers"))
            normalized["nprobes"] = _normalize_nprobes_field(normalized.get("nprobes"))
            normalized["ratio"] = _normalize_cnv_ratio(normalized.get("ratio"))
            if normalized.get("type") in {None, ""}:
                normalized["type"] = _infer_cnv_type(normalized.get("ratio"))
            normalized_rows.append(normalized)
        return normalized_rows

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
                consequence_terms,
            ) = _parse_transcripts(var_csq)
            vault_csq = _build_transcript_vault_rows(
                var_csq,
                slim_csq,
            )

            selected_csq, selected_source = _select_csq(
                slim_csq,
                hgnc_by_id=self.hgnc_by_id,
                hgnc_by_symbol=self.hgnc_by_symbol,
            )
            # Build the immutable VEP vault from the complete transcript set.
            # It is removed from the mutable variant document after staging.
            var_dict["INFO"]["CSQ"] = vault_csq
            # ``Annotation`` is an unstructured pipeline INFO passthrough. It
            # is not part of the DNA finding contract; structured VEP evidence
            # is held by the selected CSQ and immutable annotation vault.
            var_dict["INFO"].pop("Annotation", None)
            var_dict["INFO"]["selected_CSQ"] = compact_selected_csq(selected_csq)
            var_dict["INFO"]["selected_CSQ_criteria"] = selected_source
            var_dict["selected_csq_feature"] = selected_csq["Feature"]
            var_dict["HGVSp"] = prot_list
            var_dict["HGVSc"] = cdna_list
            var_dict["genes"] = genes_list
            var_dict["transcripts"] = transcripts_list
            var_dict["cosmic_ids"] = cosmic_list
            var_dict["dbsnp_id"] = dbsnp
            var_dict["pubmed_ids"] = pubmed_list
            var_dict["hotspots"] = [hotspots]
            var_dict["consequence_terms"] = consequence_terms
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

        Processes ANN fields, extracts supported fusion annotations, and retains only
        variants annotated as ``gene_fusion`` or ``bidirectional_gene_fusion``.

        Args:
            infile: Absolute path to the translocation VCF file.

        Returns:
            A list of variant dicts representing confirmed gene fusions.
        """
        mane: dict[str, dict[str, str]] = {}
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
                filtered_data.append(_normalize_transloc_doc(var_dict))

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
        fusions = runtime_file_path(args, primary_analysis_file_key("rna", "FUSION"))
        if fusions:
            require_exists("Fusions JSON", fusions)
            with open(fusions, "r", encoding="utf-8") as handle:
                preload["fusions"] = _normalize_fusion_docs(json.load(handle))

        expr_path = runtime_file_path(args, primary_analysis_file_key("rna", "EXPRESSION"))
        if expr_path:
            require_exists("Expression JSON", expr_path)
            with open(expr_path, "r", encoding="utf-8") as handle:
                preload["rna_expr"] = json.load(handle)
        class_path = runtime_file_path(args, primary_analysis_file_key("rna", "CLASSIFICATION"))
        if class_path:
            require_exists("Classification JSON", class_path)
            with open(class_path, "r", encoding="utf-8") as handle:
                preload["rna_class"] = json.load(handle)
        qc_path = runtime_file_path(args, primary_analysis_file_key("rna", "QC"))
        if qc_path:
            require_exists("QC JSON", qc_path)
            with open(qc_path, "r", encoding="utf-8") as handle:
                preload["rna_qc"] = json.load(handle)

        pgx_path = runtime_file_path(args, primary_analysis_file_key("rna", "PGX"))
        if pgx_path:
            require_exists("PGX data", pgx_path)
            with open(pgx_path, "r", encoding="utf-8") as handle:
                preload["pgx"] = _normalize_pgx_document(json.load(handle))

        return preload
