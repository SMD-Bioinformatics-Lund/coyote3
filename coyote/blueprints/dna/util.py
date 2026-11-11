#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
This module provides utility functions and classes for processing, annotating, and reporting DNA variants.
It includes methods for variant classification, consequence selection, CNV handling, annotation text generation, and report preparation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from coyote.util.common_utility import CommonUtility
from coyote.util.report.report_util import ReportUtility
from coyote.blueprints.rna.util import RNAUtility
from coyote.util.report.report_documents import build_dna_document
from coyote.util.report.shared_renderer import render_report, render_preview
from flask import current_app as app, url_for
from flask_login import current_user
from coyote.extensions import store
from typing import Any, Dict, List, Optional, Tuple
from coyote.blueprints.dna.varqueries import build_query
from copy import deepcopy
import os
from pprint import pformat
import base64


class DNAUtility:
    """
    DNAUtility provides static utility methods for processing, annotating, and reporting DNA variants.
    It includes functions for variant classification, consequence selection, CNV handling, annotation text generation, and report preparation.
    """

    @staticmethod
    def get_protein_coding_genes(var_iter: list) -> tuple[list, list]:
        """
        Extracts protein-coding genes from a list of variant dictionaries.

        Args:
            var_iter (list): List of variant dictionaries, each containing INFO and CSQ annotations.

        Returns:
            tuple[list, list]: A tuple containing:
                - The list of variants (unchanged from input).
                - A list of unique gene symbols annotated as protein_coding.
        """
        genes = set()
        variants = []
        for var in var_iter:
            if var["INFO"].get("selected_CSQ", {}).get("BIOTYPE") == "protein_coding":
                genes.add(var["INFO"]["selected_CSQ"]["SYMBOL"])
            for csq in var["INFO"]["CSQ"]:
                if csq["BIOTYPE"] == "protein_coding":
                    genes.add(csq["SYMBOL"])
            variants.append(var)

        return variants, list(genes)

    @staticmethod
    def hotspot_variant(variants: list) -> list[dict]:
        """
        Return variants that are hotspots.

        Args:
            variants (list): A list of variant dictionaries.

        Returns:
            list[dict]: A list of variant dictionaries that are hotspots.
        """
        hotspots = []
        for variant in variants:
            hotspot_dict = variant.get("hotspots", [{}])[0]
            if hotspot_dict:
                for hotspot_key, hotspot_elem in hotspot_dict.items():
                    if any("COS" in elem for elem in hotspot_elem):
                        variant.setdefault("INFO", {}).setdefault("HOTSPOT", []).append(hotspot_key)
            hotspots.append(variant)
        return hotspots

    @staticmethod
    def get_filter_conseq_terms(checked: list) -> list:
        """
        Returns a list of consequence terms mapped from the provided checked fields.

        Args:
            checked (list): List of field names to check against the consequence terms mapper.

        Returns:
            list: List of consequence terms corresponding to the checked fields.
        """

        filter_conseq = []
        conf = app.config.get("CONSEQ_TERMS_MAPPER")
        try:
            for fieldname in checked:
                if fieldname in conf:
                    filter_conseq.extend(conf.get(fieldname))
        except KeyError or TypeError:
            pass

        return filter_conseq

    @staticmethod
    def create_cnveffectlist(cnvtype: list) -> list:
        """
        Translates CNV filter types from user-friendly terms to annotation codes.

        The filter in the template uses 'loss' or 'gain', but CNV variants are annotated as 'DEL' (deletion) or 'AMP' (amplification).
        This function maps 'loss' to 'DEL' and 'gain' to 'AMP' for filtering purposes.
        """
        types = []
        for name in cnvtype:
            if name == "loss":
                types.append("DEL")
            if name == "gain":
                types.append("AMP")
        return types

    @staticmethod
    def format_pon(variant: dict) -> defaultdict:
        """
        Formats PON (Panel of Normals) information from a variant's INFO field into a nested defaultdict.

        Args:
            variant (dict): A variant dictionary containing an INFO field with PON-related keys.

        Returns:
            defaultdict: A nested dictionary where the first key is the variant class (vc), and the second key is the number type (numtype), mapping to the corresponding value from the INFO field.
        """
        pon = defaultdict(dict)
        for i in variant["INFO"]:
            if "PON_" in i:
                part = i.split("_")
                if len(part) == 3:
                    numtype = part[1]
                    vc = part[2]
                    pon[vc][numtype] = variant["INFO"][i]
        return pon

    @staticmethod
    def has_exact_context_tier(variant: dict, assay: str, subpanel: str | None) -> bool:
        """Check whether a DNA finding has a numeric tier for its selected context.

        Args:
            variant: Annotated DNA finding with its selected transcript.
            assay: Current assay group, following the analysis-page matching policy.
            subpanel: Current subpanel; equality is required for solid assays.

        Returns:
            True for a Tier I-IV classification matching the selected transcript
            and assay context. Legacy assay-less classifications remain supported
            only for myeloid and tumwgs, as on the analysis page. Alternative and
            other-context classifications never establish an exact match.
        """
        classification = variant.get("classification") or {}
        selected = (variant.get("INFO") or {}).get("selected_CSQ") or {}
        tier = classification.get("class")
        if type(tier) is not int or tier not in (1, 2, 3, 4):
            return False
        if not selected.get("Feature") or classification.get("transcript") != selected["Feature"]:
            return False
        if "assay" not in classification:
            return assay in ("myeloid", "tumwgs")
        if classification["assay"] != assay:
            return False
        return assay != "solid" or classification.get("subpanel") == subpanel

    @staticmethod
    def is_reportable_context_tier(variant: dict, assay: str, subpanel: str | None) -> bool:
        """Apply existing report exclusions to an exact analysis-context match.

        Args:
            variant: Annotated DNA finding.
            assay: Current assay group.
            subpanel: Current subpanel, or None when no subpanel is selected.

        Returns:
            True for a matching finding that is not blacklisted, false positive,
            irrelevant, Tier IV, or a gmsonco Tier III finding.
        """
        return (
            DNAUtility.has_exact_context_tier(variant, assay, subpanel)
            and not variant.get("blacklist")
            and not variant.get("fp")
            and not variant.get("irrelevant")
            and variant["classification"]["class"] != 4
            and not (assay == "gmsonco" and variant["classification"]["class"] == 3)
        )

    @staticmethod
    def add_global_annotations(variants: list, assay: str, subpanel: str) -> tuple[list, list]:
        """
        Add global annotations to each variant in the provided list.

        This method iterates over the list of variant dictionaries, retrieves global annotations,
        classification, other classification, and interesting annotations for each variant using
        the annotation handler from the store, and updates the variant accordingly. It also adds
        alternative classifications based on the specified assay and subpanel.

        Args:
            variants (list): List of variant dictionaries to annotate.
            assay (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering.

        Returns:
            tuple: All annotated findings and findings eligible for generated summary
                text. DNA summary eligibility uses the report's exact context and
                tier exclusions; indication-only findings remain in the analysis list.
        """
        selected_variants = []
        for var_idx, var in enumerate(variants):
            selected_call = RNAUtility.get_selected_fusioncall(var)
            lookup = selected_call if selected_call is not None else var  # RNA → call, DNA → var

            (
                var["global_annotations"],
                var["classification"],
                var["other_classification"],
                var["annotations_interesting"],
            ) = store.annotation_handler.get_global_annotations(lookup, assay, subpanel)

            class_value = (var["classification"] or {}).get("class")
            if "selected_CSQ" in (var.get("INFO") or {}):
                var["has_exact_context_tier"] = DNAUtility.has_exact_context_tier(
                    var, assay, subpanel
                )
                if DNAUtility.is_reportable_context_tier(var, assay, subpanel):
                    selected_variants.append(var)
            elif (
                class_value is not None
                and class_value < 999
                and not var.get("blacklist")
                and not var.get("fp")
                and not var.get("irrelevant")
            ):
                selected_variants.append(var)

            if selected_call is None:

                variants[var_idx] = DNAUtility.add_alt_class(var, assay, subpanel)
            else:

                alt = DNAUtility.add_alt_class(dict(selected_call), assay, subpanel)
                var["additional_classification"] = alt["additional_classification"]

        return variants, selected_variants

    @staticmethod
    def add_alt_class(variant: dict, assay: str, subpanel: str) -> dict:
        """
        Add alternative classifications to a variant based on the specified assay and subpanel.

        Args:
            variant (dict): A dictionary representing a variant to be annotated.
            assay (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when assay is 'solid'.

        Returns:
            dict: The variant dictionary with additional classifications added.
        """
        additional_classifications = store.annotation_handler.get_additional_classifications(
            variant, assay, subpanel
        )
        if additional_classifications:
            additional_classifications[0].pop("author", None)
            additional_classifications[0].pop("time_created", None)
            additional_classifications[0]["class"] = int(additional_classifications[0]["class"])
            variant["additional_classification"] = additional_classifications[0]
        else:
            variant["additional_classification"] = None

        return variant

    @staticmethod
    def filter_variants_for_report(
        variants: list, filter_genes: list, assay: str, subpanel: str | None = None
    ) -> list:
        """
        Filters variants for inclusion in the report based on gene, blacklist status, classification, and assay-specific rules.

        Args:
            variants (list): List of variant dictionaries to filter.
            filter_genes (list): List of gene symbols to include. If empty, all genes are included.
            assay (str): Assay type, used for additional filtering logic.
            subpanel (str | None): Selected subpanel for context matching. Defaults to None.

        Returns:
            list: Filtered and sorted list of variant dictionaries suitable for reporting.
        """
        filtered_sorted_variants = sorted(
            [
                var
                for var in variants
                if (
                    var.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL") in filter_genes
                    or len(filter_genes) == 0
                )
                and DNAUtility.is_reportable_context_tier(var, assay, subpanel)
            ],
            key=lambda var: var.get("classification", {}).get("class", 0),
        )

        return filtered_sorted_variants

    @staticmethod
    def sort_by_class_and_af(data: list[dict]) -> list[dict]:
        """
        Sort a list of variant-like dicts by classification and allele frequency.

        Sort order:
        - primary: 'class' ascending (lower class value first)
        - secondary: 'af' descending (higher allele frequency first)

        Args:
            data (list[dict]): Each dict should contain at least the keys 'class' and 'af'.

        Returns:
            list[dict]: A new list sorted by the specified criteria.
        """
        return sorted(data, key=lambda d: (d["class"], -d["af"]))

    @staticmethod
    def get_simple_variants_for_report(variants: list, assay_config: dict) -> list:
        """
        Generate a simplified list of variant dictionaries for reporting.

        Args:
            variants (list): List of variant dictionaries to process.
            assay_config (dict): Assay configuration dictionary used for formatting and annotation.

        Returns:
            list: A list of dictionaries, each containing essential fields (chromosome, position, alleles, type, classification, consequence, cDNA/protein changes, and annotations) for reporting.

        Description:
            Processes a list of variant dictionaries, extracting and formatting key information for inclusion in clinical or research reports.
        """
        translation = ReportUtility.VARIANT_CLASS_TRANSLATION
        class_short_desc_list = ReportUtility.TIER_SHORT_DESC
        class_long_desc_list = ReportUtility.TIER_DESC
        one_letter_p = app.jinja_env.filters["one_letter_p"]
        standard_HGVS = app.jinja_env.filters["standard_HGVS"]

        simple_variants = []

        for var in variants:
            cdna = ""
            protein_changes = []

            indel_size = len(var.get("ALT")) - len(var.get("REF"))
            selected_CSQ = var.get("INFO", {}).get("selected_CSQ", {})
            var_type = "snv"
            variant_class = var.get("classification", {}).get("class")
            if indel_size > 20 or indel_size < -20:
                var_type = "indel"

                if indel_size < 0:
                    variant = cdna = f"{abs(indel_size)}bp DEL"
                else:
                    variant = cdna = f"{indel_size}bp INS"
            elif selected_CSQ.get("HGVSc"):
                variant = cdna = selected_CSQ.get("HGVSc")
            elif var.get("INFO", {}).get("SVTYPE"):
                var_type = "sv"
                variant = cdna = (
                    f"{var.get("INFO", {}).get("SVLEN")}bp {translation[var.get("INFO", {}).get('SVTYPE')]}"
                )
            else:
                variant = "?"

            # if there is a protein change and not long indel then replace the variant
            if selected_CSQ.get("HGVSp", None):
                if indel_size <= 20 or indel_size >= -20:
                    var_type = "snv"
                    variant = standard_HGVS(one_letter_p(selected_CSQ.get("HGVSp")))
                    protein_changes = [
                        standard_HGVS(one_letter_p(selected_CSQ.get("HGVSp"))),
                        standard_HGVS(selected_CSQ.get("HGVSp")),
                    ]
                else:
                    protein_changes = [
                        one_letter_p(selected_CSQ.get("HGVSp")),
                        selected_CSQ.get("HGVSp"),
                    ]

            # Vairant class short description
            if variant_class in class_short_desc_list:
                variant_class_short = class_short_desc_list[variant_class]
            else:
                variant_class_short = "-"

            # Vairant class long description
            if variant_class in class_short_desc_list:
                variant_class_long = class_long_desc_list[variant_class]
            else:
                variant_class_long = "-"

            # Classification/variant type
            if var.get("INFO", {}).get("MYELOID_GERMLINE") == 1 or "GERMLINE" in var.get(
                "FILTER", []
            ):
                class_type = "Konstitutionell"
            else:
                class_type = "Somatisk"

            # consequence
            all_conseq = selected_CSQ.get("Consequence", [])
            consequence = ""
            if all_conseq and isinstance(all_conseq, list):
                for c in all_conseq:
                    if c in translation:
                        consequence = translation[c]
                        break
                    else:
                        consequence = c
            elif all_conseq and isinstance(all_conseq, str):
                for c in all_conseq.split("&"):
                    if c in translation:
                        consequence = translation[c]
                        break
                    else:
                        consequence = c

            # Allele Freq
            if var.get("INFO", {}).get("SVTYPE") and selected_CSQ.get("SYMBOL") == "FLT3":
                AF = "N/A"
            else:
                for gt in var.get("GT"):
                    if gt.get("type") == "case":
                        AF = gt.get("AF")
                        break

            exon_raw = selected_CSQ.get("EXON") or ""
            exons = [
                e
                for e in (exon_raw.split("/") if isinstance(exon_raw, str) else [])
                if e and e.strip()
            ]
            intron_raw = selected_CSQ.get("INTRON") or ""
            introns = [
                i
                for i in (intron_raw.split("/") if isinstance(intron_raw, str) else [])
                if i and i.strip()
            ]

            simple_variants.append(
                {
                    "chr": var.get("CHROM"),
                    "pos": var.get("POS"),
                    "ref": var.get("REF"),
                    "alt": var.get("ALT"),
                    "variant": variant,
                    "indel_size": indel_size,
                    "af": AF,
                    "symbol": selected_CSQ.get("SYMBOL"),
                    "exon": exons,
                    "intron": introns,
                    "class": variant_class,
                    "class_short_desc": variant_class_short,
                    "class_long_desc": variant_class_long,
                    "hotspot": var.get("INFO", {}).get("HOTSPOT"),
                    "var_type": var_type,
                    "class_type": class_type,
                    "var_class": var.get("variant_class", ""),
                    "feature": selected_CSQ.get("Feature", ""),
                    "consequence": consequence,
                    "cdna": cdna,
                    "protein_changes": protein_changes,
                    "global_annotations": var.get("global_annotations", []),
                    "annotations_interesting": var.get("annotations_interesting", []),
                    "comments": var.get("comments", []),
                }
            )
        return simple_variants

    @staticmethod
    def get_variant_nomenclature(data: dict) -> tuple[str, str]:
        """
        Get the nomenclature for the variant based on the following priority order:
        1. var_p (protein change)
        2. var_c (coding DNA change)
        3. var_g (genomic change)
        4. fusionpoints (fusion breakpoints)
        5. translocpoints (translocation breakpoints)
        6. cnvvar (copy number variant)
        Returns:
            tuple: A tuple containing the nomenclature and the variant value.
        """
        nomenclature = "p"  # default
        variant = ""  # default value in case nothing is found

        var_nomenclature = {
            "var_p": "p",  # priority 1
            "var_c": "c",  # priority 2
            "var_g": "g",  # priority 3
            "fusionpoints": "f",
            "translocpoints": "t",
            "cnvvar": "cn",
        }

        for key, value in var_nomenclature.items():
            variant_value = data.get(key)
            if variant_value:  # this checks for both None and empty string
                nomenclature = value
                variant = variant_value
                break

        return nomenclature, variant

    @staticmethod
    def cnvtype_variant(cnvs: list, checked_effects: list) -> list:
        """
        Filter CNVs by type.

        This function filters a list of CNV (Copy Number Variant) dictionaries based on the provided list of checked effects.

        Args:
         cnvs (list): List of CNV dictionaries to filter.
         checked_effects (list): List of CNV effect types to include (e.g., 'DEL', 'AMP').

        Returns:
         list: Filtered list of CNV dictionaries matching the specified effects.

        Note:
         This function is marked as deprecated and may be removed in future versions.
        """
        filtered_cnvs = []
        for var in cnvs:
            if var["ratio"] > 0:
                effect = "AMP"
            elif var["ratio"] < 0:
                effect = "DEL"
            if effect in checked_effects:
                filtered_cnvs.append(var)
        return filtered_cnvs

    @staticmethod
    def cnv_organizegenes(cnvs: list) -> list:
        """
        Organize CNV genes.

        This function processes a list of CNV (Copy Number Variant) dictionaries and organizes the gene information
        for each CNV. It can be used to extract, group, or format gene data associated with CNVs for downstream analysis
        or reporting.

        Args:
            cnvs (list): List of CNV dictionaries, each containing gene information.

        Returns:
            list: A list of organized gene data extracted or processed from the input CNVs.
        """
        fixed_cnvs_genes = []
        for var in cnvs:
            var["other_genes"] = []
            for gene in var["genes"]:
                if "class" in gene:
                    if "panel_gene" in var:
                        var["panel_gene"].append(gene["gene"])
                    else:
                        var["panel_gene"] = [gene["gene"]]
                else:
                    var["other_genes"].append(gene["gene"])
            fixed_cnvs_genes.append(var)
        return fixed_cnvs_genes

    @staticmethod
    def get_report_timestamp() -> str:
        """
        This function returns the current timestamp, formatted as a string, which can be used to indicate when a report was generated. The timestamp includes the date and time down to the second.

        Returns:
            str: A string representing the current timestamp in the format 'YYYY-MM-DD HH:MM:SS'.
        """
        return CommonUtility.utc_now().strftime("%y%m%d%H%M%S")

    @staticmethod
    def build_dna_report_payload(
        sample: dict,
        assay_config: dict,
        save: int = 0,
        include_snapshot: bool = False,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Build the DNA report payload for a sample.

        This function performs the complete DNA report construction workflow:
        variant retrieval, filtering, annotation, tiering, and transformation into
        a renderable HTML report. Optionally, it also produces a lightweight,
        immutable snapshot of the reported variants suitable for persistence.

        The function is intentionally side-effect free and is reused by both the
        report preview and report save endpoints to guarantee that previewed and
        persisted reports are identical.

        Parameters
        ----------
        sample : dict
            Sample document as retrieved from the database.

        assay_config : dict
            Assay configuration defining filters, reporting sections, and display
            behavior for the DNA report.

        save : int, optional
            A value of 1 returns standalone shared-template HTML for saving.
            Other values return the Flask preview container with separate actions.
            This flag does not trigger persistence.

        include_snapshot : bool, optional
            If True, return a list of reported-variant snapshot rows corresponding
            exactly to the variants included in the report. If False, snapshot data
            is not generated.

        Returns
        -------
        html : str
            Rendered HTML representation of the DNA report.

        snapshot_rows : list[dict] | None
            List of reported-variant snapshot rows, each representing a single
            variant included in the report along with its tier at report time.
            Returns None when `include_snapshot` is False.

        Notes
        -----
        - This function executes the full report-building logic exactly once.
        - Snapshot rows are derived from the final set of variants included in the
          report, ensuring strict consistency between rendered content and persisted
          snapshots.
        - No database writes or filesystem operations are performed here.
        - Persistence, error handling, and rollback logic are handled by the caller.
        """

        sample_assay = sample.get("assay")
        assay_group: str = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        report_sections = assay_config.get("reporting", {}).get("report_sections", [])
        report_sections_data: Dict[str, Any] = {}

        app.logger.debug(f"Assay group: {assay_group} - DNA config: {pformat(report_sections)}")
        app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

        assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

        insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(sample_assay, is_active=True)
        all_panel_genelist_names = CommonUtility.get_assay_genelist_names(insilico_panel_genelists)

        if not sample.get("filters"):
            sample = CommonUtility.merge_sample_settings_with_assay_config(sample, assay_config)

        sample_filters = deepcopy(sample.get("filters", {}))

        checked_genelists = sample_filters.get("genelists", [])
        checked_genelists_genes_dict: list[dict] = store.isgl_handler.get_isgl_by_ids(
            checked_genelists
        )
        genes_covered_in_panel, filter_genes = CommonUtility.get_sample_effective_genes(
            sample, assay_panel_doc, checked_genelists_genes_dict
        )

        filter_conseq = DNAUtility.get_filter_conseq_terms(
            sample_filters.get("vep_consequences", [])
        )

        disp_pos = []
        if assay_config.get("verification_samples"):
            if sample["name"] in assay_config["verification_samples"]:
                disp_pos = assay_config["verification_samples"][sample["name"]]

        query = build_query(
            assay_group,
            {
                "id": str(sample["_id"]),
                "max_freq": sample_filters["max_freq"],
                "min_freq": sample_filters["min_freq"],
                "max_control_freq": sample_filters["max_control_freq"],
                "min_depth": sample_filters["min_depth"],
                "min_alt_reads": sample_filters["min_alt_reads"],
                "max_popfreq": sample_filters["max_popfreq"],
                "filter_conseq": filter_conseq,
                "filter_genes": filter_genes,
                "disp_pos": disp_pos,
                "fp": {"$ne": True},
                "irrelevant": {"$ne": True},
            },
        )

        variants = list(store.variant_handler.get_case_variants(query))
        variants = store.blacklist_handler.add_blacklist_data(variants, assay=assay_group)

        variants, tiered_variants = DNAUtility.add_global_annotations(
            variants, assay_group, subpanel
        )

        variants = DNAUtility.hotspot_variant(variants)
        variants = DNAUtility.filter_variants_for_report(
            variants, filter_genes, assay_group, subpanel
        )

        # latest sample comment
        latest_sample_comment = store.sample_handler.get_latest_sample_comment(
            sample_id=str(sample["_id"])
        )

        # IMPORTANT: snapshot should be based on the SAME "reported variants set"
        # If your filter_variants_for_report is the final "reported set", snapshot these.
        snapshot_rows: Optional[List[Dict[str, Any]]] = None
        if include_snapshot:
            # Build minimal snapshot rows needed for insertion later.
            # Keep this lightweight; do NOT write to DB here.
            snapshot_rows = []
            now_utc = datetime.utcnow()

            for v in variants:
                annotations_interesting = v.get("annotations_interesting", {})
                annotations_interesting_assay_specific = (
                    annotations_interesting.get(assay_group)
                    or annotations_interesting.get(f"{assay_group}:{subpanel}")
                    or {}
                )
                sel = (v.get("INFO", {}) or {}).get("selected_CSQ", {}) or {}
                snapshot_rows.append(
                    {
                        "var_oid": v.get("_id"),
                        "annotation_oid": v.get("classification", {}).get("_id", None),
                        "annotation_text_oid": annotations_interesting_assay_specific.get(
                            "_id", None
                        ),
                        "sample_comment_oid": (
                            latest_sample_comment.get("_id") if latest_sample_comment else None
                        ),
                        "var_type": v.get("variant_class"),
                        "simple_id": v.get("simple_id"),
                        "simple_id_hash": v.get("simple_id_hash"),
                        "tier": v.get("classification", {}).get("class"),
                        "gene": sel.get("SYMBOL") or (v.get("gene") or None),
                        "transcript": sel.get("Feature") or v.get("selected_csq_feature"),
                        "hgvsp": sel.get("HGVSp") or v.get("hgvsp"),
                        "hgvsc": sel.get("HGVSc") or v.get("hgvsc"),
                        "variant": v.get("classification", {}).get("variant"),
                        "created_on": now_utc,
                    }
                )

        # transform for report rendering (safe — snapshot already captured)
        variants_simple = DNAUtility.get_simple_variants_for_report(variants, assay_config)
        report_sections_data["snvs"] = DNAUtility.sort_by_class_and_af(variants_simple)

        if "CNV" in report_sections:
            report_sections_data["cnvs"] = list(
                store.cnv_handler.get_interesting_sample_cnvs(sample_id=str(sample["_id"]))
            )

        if "CNV_PROFILE" in report_sections:
            cnv_path = sample.get("cnvprofile")
            cnv_b64 = None
            if cnv_path and os.path.isfile(cnv_path):
                with open(cnv_path, "rb") as fh:
                    cnv_b64 = base64.b64encode(fh.read()).decode("utf-8")
            elif cnv_path:
                cnv_b64 = CommonUtility.get_plot(os.path.basename(cnv_path), assay_config)

            if not cnv_b64:
                app.logger.warning(f"CNV profile could not be loaded: {cnv_path}")
            report_sections_data["cnv_profile_base64"] = cnv_b64

        if "BIOMARKER" in report_sections:
            report_sections_data["biomarkers"] = list(
                store.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
            )

        if "TRANSLOCATION" in report_sections:
            report_sections_data["translocs"] = (
                store.transloc_handler.get_interesting_sample_translocations(
                    sample_id=str(sample["_id"])
                )
            )

        if "FUSION" in report_sections:
            fusions = store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
            report_sections_data["fusions"] = fusions
            # Backward-compatible alias for templates that still read translocs.
            report_sections_data.setdefault("translocs", fusions)

        assay_config["reporting"]["report_header"] = CommonUtility.get_report_header(
            assay_group,
            sample,
            assay_config["reporting"].get("report_header", "Unknown"),
        )

        report_date = datetime.now().date()
        report_timestamp: str = DNAUtility.get_report_timestamp()

        document = build_dna_document(
            assay_config=assay_config,
            report_sections=report_sections,
            report_sections_data=report_sections_data,
            sample=sample,
            report_date=report_date,
            report_timestamp=report_timestamp,
            assay_group=assay_group,
            genes_covered_in_panel=genes_covered_in_panel,
            author=current_user.fullname,
            asp_url=url_for("public_bp.asp_genes", asp_id=sample_assay, _external=True),
            accredited=bool((assay_panel_doc or {}).get("accredited", False)),
        )
        html = render_report(document)
        if save != 1:
            panel_export = None
            if assay_group != "tumwgs":
                fernet = app.config["FERNET"]
                panel_export = dict(
                    panel=CommonUtility.encrypt_json(assay_panel_doc, fernet),
                    genelists=CommonUtility.encrypt_json(genes_covered_in_panel, fernet),
                    filters=CommonUtility.encrypt_json(sample_filters, fernet),
                )
            html = render_preview(html, sample, "dna", panel_export)

        return html, snapshot_rows
