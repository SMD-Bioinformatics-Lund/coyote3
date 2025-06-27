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

from collections import defaultdict
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from coyote.util.report.report_util import ReportUtility
from flask import current_app as app
from coyote.extensions import store
from bisect import bisect_left


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
            if (
                var["INFO"].get("selected_CSQ", {}).get("BIOTYPE")
                == "protein_coding"
            ):
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
                        variant.setdefault("INFO", {}).setdefault(
                            "HOTSPOT", []
                        ).append(hotspot_key)
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
    def add_global_annotations(
        variants: list, assay: str, subpanel: str
    ) -> tuple[list, list]:
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
            list: The list of variants with updated global annotations and classifications.
        """
        selected_variants = []
        for var_idx, var in enumerate(variants):
            (
                variants[var_idx]["global_annotations"],
                variants[var_idx]["classification"],
                variants[var_idx]["other_classification"],
                variants[var_idx]["annotations_interesting"],
            ) = store.annotation_handler.get_global_annotations(
                var, assay, subpanel
            )
            classification = variants[var_idx]["classification"]
            if classification is not None:
                class_value = classification.get("class")
                if class_value is not None and class_value < 999:
                    selected_variants.append(variants[var_idx])

            variants[var_idx] = DNAUtility.add_alt_class(
                variants[var_idx], assay, subpanel
            )
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
        additional_classifications = (
            store.annotation_handler.get_additional_classifications(
                variant, assay, subpanel
            )
        )
        if additional_classifications:
            additional_classifications[0].pop("_id", None)
            additional_classifications[0].pop("author", None)
            additional_classifications[0].pop("time_created", None)
            additional_classifications[0]["class"] = int(
                additional_classifications[0]["class"]
            )
            variant["additional_classification"] = additional_classifications[
                0
            ]
        else:
            variant["additional_classification"] = None

        return variant

    @staticmethod
    def filter_variants_for_report(
        variants: list, filter_genes: list, assay: str
    ) -> list:
        """
        Filters variants for inclusion in the report based on gene, blacklist status, classification, and assay-specific rules.

        Args:
            variants (list): List of variant dictionaries to filter.
            filter_genes (list): List of gene symbols to include. If empty, all genes are included.
            assay (str): Assay type, used for additional filtering logic.

        Returns:
            list: Filtered and sorted list of variant dictionaries suitable for reporting.
        """
        filtered_sorted_variants = sorted(
            [
                var
                for var in variants
                if (
                    var.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL")
                    in filter_genes
                    or len(filter_genes) == 0
                )
                and not var.get("blacklist")
                and var.get("classification")
                and var.get("classification", {}).get("class", 0)
                not in [4, 999]
                and not (
                    (
                        assay == "gmsonco"
                        and var.get("classification", {}).get("class", 0) == 3
                    )
                    if assay != "tumwgs"
                    else False
                )
            ],
            key=lambda var: var.get("classification", {}).get("class", 0),
        )

        return filtered_sorted_variants

    @staticmethod
    def get_simple_variants_for_report(
        variants: list, assay_config: dict
    ) -> list:
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
        cdna = ""
        protein_changes = []
        simple_variants = []
        for var in variants:
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
                    variant = standard_HGVS(
                        one_letter_p(selected_CSQ.get("HGVSp"))
                    )
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
            if var.get("INFO", {}).get(
                "MYELOID_GERMLINE"
            ) == 1 or "GERMLINE" in var.get("FILTER", []):
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
            if (
                var.get("INFO", {}).get("SVTYPE")
                and selected_CSQ.get("SYMBOL") == "FLT3"
            ):
                AF = "N/A"
            else:
                for gt in var.get("GT"):
                    if gt.get("type") == "case":
                        AF = gt.get("AF")
                        break

            simple_variants.append(
                {
                    "chr": var.get("CHROM"),
                    "pos": var.get("POS"),
                    "ref": var.get("REF"),
                    "alt": var.get("ALT"),
                    "variant": variant,
                    "af": AF,
                    "symbol": selected_CSQ.get("SYMBOL"),
                    "exon": selected_CSQ.get("EXON").split("/"),
                    "intron": selected_CSQ.get("INTRON").split("/"),
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
                    "annotations_interesting": var.get(
                        "annotations_interesting", []
                    ),
                    "comments": var.get("comments", []),
                }
            )
        return simple_variants

    @staticmethod
    def get_tier_classification(data: dict) -> int:
        """
        Returns the tier classification for the given variant data dictionary.

        The function checks for the presence of tier keys (`tier1`, `tier2`, `tier3`, `tier4`)
        in the input dictionary and returns the corresponding classification number (1-4).
        If no tier is found, it returns 0.

        Returns:
            int: The tier classification number (1-4), or 0 if not classified.
        """
        tiers = {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}
        class_num = 0
        for key, value in tiers.items():
            if data.get(key, None) is not None:
                class_num = value

        return class_num

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
