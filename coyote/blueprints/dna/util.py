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
    def parse_allele_freq(freq, allele):
        """
        Deprecated function. This function is no longer maintained and will be removed in future versions.
        """
        # TODO: Remove this function

        if not freq:
            return ""
        if len(allele) > 1:
            allele = allele[1:]
        all_alleles = freq.split("&")
        for allele_frq in all_alleles:
            a = allele_frq.split(":")
            if a[0] == allele:
                return float(a[1])
        return "N/A"

    @staticmethod
    def popfreq_filter(variants: list, max_freq: float) -> list:
        """
        Filter variants based on population frequency.

        Args:
            variants (list): List of variant dictionaries.
            max_freq (float): Maximum allowed population frequency.

        Returns:
            list: Filtered list of variant dictionaries.
        """

        filtered_variants = []

        for var in variants:
            pop_freq = {
                "exac": var.get("exac_frequency"),
                "thousand_g": var.get("thousandG_frequency"),
                "gnomad": var.get("gnomad_frequency"),
                # "gnomad_max": var.get("gnomad_max"),
            }
            for k, v in pop_freq.items():
                if v in ["", ".", None]:
                    pop_freq[k] = float(-1)
                else:
                    pop_freq[k] = float(v)

            try:
                if max_freq < 1 and any(
                    [freq > max_freq for freq in pop_freq.values()]
                ):
                    pass
                else:
                    filtered_variants.append(var)
            except TypeError:
                filtered_variants.append(var)

        return filtered_variants

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
    def select_csq(csq_arr: list, canonical: dict):
        """
        Selects the most appropriate consequence (csq) from a list of consequences based on predefined criteria.

        The function prioritizes consequences in the following order:
        1. A consequence that matches the canonical dictionary (db_canonical).
        2. A consequence marked as canonical by VEP (vep_canonical).
        3. The first protein-coding consequence (first_protcoding).
        4. If none of the above are found, the first consequence in the list.

        Args:
            csq_arr (list): A list of consequence dictionaries.
            canonical (dict): A dictionary containing canonical symbols and their corresponding features.

        Returns:
            tuple: A tuple containing the selected consequence dictionary and a string indicating the selection method
                ("db", "vep", or "random").
        """
        # TODO: SHOULD BE PROBABLY BRING IN MANE TRANSCRIPTS INTO THE SELECTION PROCESS
        db_canonical = -1
        vep_canonical = -1
        first_protcoding = -1

        impact_order = ["HIGH", "MODERATE", "LOW", "MODIFIER"]

        for impact in impact_order:
            for csq_idx, csq in enumerate(csq_arr):
                csq_symbol = csq.get("SYMBOL")
                csq_feature = csq.get("Feature")
                csq_biotype = csq.get("BIOTYPE")
                csq_impact = csq.get("IMPACT")

                if csq_impact == impact:
                    if csq_symbol in canonical and canonical.get(
                        csq_symbol
                    ) == DNAUtility.refseq_noversion(csq_feature):
                        db_canonical = csq_idx
                        return csq_arr[db_canonical], "db"

                    if csq.get("CANONICAL") == "YES" and vep_canonical == -1:
                        vep_canonical = csq_idx

                    if (
                        first_protcoding == -1
                        and csq_biotype == "protein_coding"
                    ):
                        first_protcoding = csq_idx

        if vep_canonical >= 0:
            return csq_arr[vep_canonical], "vep"
        elif first_protcoding >= 0:
            return csq_arr[first_protcoding], "random"

        return csq_arr[0], "random"

    @staticmethod
    def refseq_noversion(acc: str) -> str:
        """
        Returns the RefSeq accession number without the version number.
        """
        a = acc.split(".")
        return a[0]

    @staticmethod
    def select_csq_for_variants(
        variants: list, subpanel: str, assay: str, canonical_dict: dict
    ) -> list:
        """
        Selects the VEP CSQ (Consequence) for each variant and adds additional annotations.

        This method iterates over a list of variant dictionaries, selects the most appropriate
        consequence annotation for each variant using the canonical transcript dictionary, and
        updates the variant's INFO field with the selected consequence and selection criteria.
        It also adds global annotations, classification, other classification, and interesting
        annotations to each variant using the annotation handler from the store.

        Args:
            variants (list): List of variant dictionaries to annotate.
            subpanel (str): Subpanel identifier used for annotation.
            assay (str): Assay type used for annotation.
            canonical_dict (dict): Dictionary mapping gene symbols to canonical transcript features.

        Returns:
            list: The list of variants with updated INFO and annotation fields.
        """
        # TODO:
        for var_idx, var in enumerate(variants):
            (
                variants[var_idx]["INFO"]["selected_CSQ"],
                variants[var_idx]["INFO"]["selected_CSQ_criteria"],
            ) = DNAUtility.select_csq(var["INFO"]["CSQ"], canonical_dict)

            (
                variants[var_idx]["global_annotations"],
                variants[var_idx]["classification"],
                variants[var_idx]["other_classification"],
                variants[var_idx]["annotations_interesting"],
            ) = store.annotation_handler.get_global_annotations(
                variants[var_idx], assay, subpanel
            )
        return variants

    @staticmethod
    def add_global_annotations(
        variants: list, assay: str, subpanel: str
    ) -> list:
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
            ) = store.annotation_handler.get_global_annotations(var, assay, subpanel)
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
    def generate_ai_text_nonsnv(assay, variants, group, var_type):
        """
        Function to add a summerizing text to a specific non-snv type of variation
        The default behavior of coyote is to have SNVs. If one wants to add more things
        to the 'AI' summary this function just sends it to a specilized function
        and concatenates the output into one string of text
        """
        text = ""

        if var_type == "transloc":
            text = DNAUtility.summerize_fusion(variants)
        elif var_type == "cnv":
            text = DNAUtility.summerize_cnv(variants)
        elif var_type == "bio":
            text = DNAUtility.summerize_bio(variants)

        return text

    @staticmethod
    def summerize_fusion(variants: list) -> str:
        """
        Smart-text for summerizing dna-fusions(translocations). Depending on what type
        of evidence is present it will add PR SR or UR and between what genes the trans-
        location as occured.
        """
        interesting = {}
        for var in variants:
            if "interesting" in var:
                if var["interesting"]:
                    if "MANE_ANN" in var["INFO"]:
                        annotation = var["INFO"]["MANE_ANN"]
                    else:
                        annotation = var["INFO"]["ANN"][0]
                    genes = annotation["Gene_Name"].split("&")
                    for gt in var["GT"]:
                        af_dict = {"af_pr": 0, "af_sr": 0, "af_ur": 0}
                        if genes[0] + " och " + genes[1] in interesting:
                            pass
                        else:
                            interesting[genes[0] + " och " + genes[1]] = (
                                af_dict
                            )
                        if "PR" in gt:
                            pr = gt["PR"].split(",")
                            af_pr = (
                                round(
                                    float(pr[1])
                                    / (float(pr[1]) + float(pr[0])),
                                    ndigits=3,
                                )
                                * 100
                            )
                            if (
                                af_pr
                                > interesting[genes[0] + " och " + genes[1]][
                                    "af_pr"
                                ]
                            ):
                                interesting[genes[0] + " och " + genes[1]][
                                    "af_pr"
                                ] = af_pr
                        if "SR" in gt:
                            sr = gt["SR"].split(",")
                            af_sr = (
                                round(
                                    float(sr[1])
                                    / (float(sr[1]) + float(sr[0])),
                                    ndigits=3,
                                )
                                * 100
                            )
                            if (
                                af_sr
                                > interesting[genes[0] + " och " + genes[1]][
                                    "af_sr"
                                ]
                            ):
                                interesting[genes[0] + " och " + genes[1]][
                                    "af_sr"
                                ] = af_sr
                    if "UR" in var["INFO"]:
                        af_ur = var["INFO"]["UR"]
                        if (
                            af_ur
                            > interesting[genes[0] + " och " + genes[1]][
                                "af_ur"
                            ]
                        ):
                            interesting[genes[0] + " och " + genes[1]][
                                "af_ur"
                            ] = af_ur
        text = ""
        cl = 0
        for voi in interesting:
            cl += 1
            intro = [
                "Vid analysen finner man en genfusion mellan generna " + voi,
                "Vidare finner man en genfusion mellan generna " + voi,
                "Slutligen finner man en genfusion mellan generna " + voi,
            ]
            if len(interesting) == 1 or cl == 1:
                text += "\n" + intro[0] + " ("
            elif len(interesting) == 2 and (1 < cl < len(interesting)):
                text += "\n" + intro[1] + " ("
            elif 2 < len(interesting) == cl:
                text += "\n" + intro[2] + " ("
            af = 0
            if interesting[voi]["af_pr"] > 0 and interesting[voi]["af_sr"] > 0:
                text += (
                    "i "
                    + str(interesting[voi]["af_pr"])
                    + "%"
                    + " av överspännande läsningar och "
                    + str(interesting[voi]["af_sr"])
                    + "%"
                    + " av splittade läsningar"
                )
                af = 1
            elif interesting[voi]["af_sr"] > 0:
                text += (
                    "i "
                    + str(interesting[voi]["af_sr"])
                    + "%"
                    + " av splittade läsningar"
                )
                af = 1
            elif interesting[voi]["af_pr"]:
                text += (
                    "i "
                    + str(interesting[voi]["af_pr"])
                    + "%"
                    + " av överspännande läsningar"
                )
                af = 1
            if interesting[voi]["af_ur"] > 0 and af > 0:
                text += (
                    " samt uppskattas det finnas "
                    + str(interesting[voi]["af_ur"])
                    + " unika läsningar"
                )
            elif interesting[voi]["af_ur"] > 0:
                text += (
                    " i vilken det uppskattas finnas "
                    + str(interesting[voi]["af_ur"])
                    + " unika läsningar"
                )
            text += ")\n"
        return text

    @staticmethod
    def summerize_cnv(variants: list) -> str:
        """
        Smart-text for summerizing interesting CNV finds. Depending on what type of evidence is present
        it will present PR or SR for manta-like calls, and copy number calls for read-depth based calls.
        It will mention assay-interesting genes and how many other genes the call spans over
        """
        interesting = {}
        for var in variants:
            if "interesting" in var:
                if var["interesting"]:
                    coord = (
                        str(var["chr"])
                        + ":"
                        + str(var["start"])
                        + "-"
                        + str(var["end"])
                    )
                    af_dict = {
                        "af_pr": 0,
                        "af_sr": 0,
                        "cn": 0,
                        "cnp": 0,
                        "coord": coord,
                        "other_genes": 0,
                    }
                    if isinstance(var["ratio"], float):
                        cn = round(2 * (2 ** var["ratio"]), ndigits=2)
                    else:
                        cn = var["ratio"]
                    other_genes = 0
                    goi = []
                    for gene in var["genes"]:
                        if "class" in gene:
                            goi.append(gene["gene"])
                        else:
                            other_genes += 1
                    goi = ":".join(goi)
                    if var["ratio"] > 0:
                        suffix = "amp"
                    else:
                        suffix = "loss"
                    if goi + ":" + suffix in interesting:
                        pass
                    else:
                        interesting[goi + ":" + suffix] = af_dict
                    if (
                        other_genes
                        > interesting[goi + ":" + suffix]["other_genes"]
                    ):
                        interesting[goi + ":" + suffix][
                            "other_genes"
                        ] = other_genes
                    if "gatk" in var["callers"] or "cnvkit" in var["callers"]:
                        if cn > interesting[goi + ":" + suffix]["cn"]:
                            interesting[goi + ":" + suffix]["cn"] = cn
                    if "manta" in var["callers"]:
                        if var["SR"] != 0:
                            sr = var["SR"].split("/")
                            af_sr = (
                                round(
                                    float(sr[1])
                                    / (float(sr[1]) + float(sr[0])),
                                    ndigits=3,
                                )
                                * 100
                            )
                            interesting[goi + ":" + suffix]["af_sr"] = af_sr
                        if var["PR"] != 0:
                            pr = var["PR"].split("/")
                            af_pr = (
                                round(
                                    float(pr[1])
                                    / (float(pr[1]) + float(pr[0])),
                                    ndigits=3,
                                )
                                * 100
                            )
                            interesting[goi + ":" + suffix]["af_pr"] = af_pr
        text = "\n"
        cl = 0
        for voi in interesting:
            cl += 1
            vois = voi.split(":")
            effect = vois.pop()
            if effect == "amp":
                effect = "amplifiering"
            else:
                effect = "förlust"
            if len(vois) > 1:
                gene_spoken = CommonUtility.nl_join(vois, "samt")
                gene = "generna " + gene_spoken
            else:
                gene = "genen " + vois[0]
            info = ""
            if (interesting[voi]["cn"]) > 0:
                info += "cn=" + str(interesting[voi]["cn"])
            if interesting[voi]["af_sr"] > 0 and interesting[voi]["af_pr"] > 0:
                info += (
                    " i "
                    + str(interesting[voi]["af_pr"])
                    + "%"
                    + " av överspännande läsningar och "
                    + str(interesting[voi]["af_sr"])
                    + "%"
                    + " av splittade läsningar"
                )
            elif interesting[voi]["af_sr"] > 0:
                info += (
                    " i "
                    + str(interesting[voi]["af_sr"])
                    + "%"
                    + " av splittade läsningar"
                )
            elif interesting[voi]["af_pr"]:
                info += (
                    " i "
                    + str(interesting[voi]["af_pr"])
                    + "%"
                    + " av överspännande läsningar"
                )

            intro = [
                "Vid analysen finner man en " + effect + " av " + gene,
                "Vidare finner man en " + effect + " av " + gene,
                "Slutligen finner man en " + effect + " av " + gene,
            ]
            if len(interesting) == 1 or cl == 1:
                text += intro[0] + " (" + info
            elif len(interesting) == 2 or (1 < cl < len(interesting)):
                text += intro[1] + " (" + info
            elif 2 < len(interesting) == cl:
                text += intro[2] + " (" + info
            text += "). "
        text += "\n"
        return text

    @staticmethod
    def summerize_bio(variants: list) -> str:
        """
        Smart-text summerizing other biomarkers. Depending if the biomarker surpasses a set threshold it will present the result
        with an acompaning text.
        """
        text = ""
        for bio in variants:
            if "HRD" in bio:
                if bio["HRD"]["sum"] > 42:
                    text += (
                        "\nAnalysen påvisar ett positivt HRD-värde ("
                        + str(bio["HRD"]["sum"])
                        + " homologisk rekombinationsdeficiens)\n"
                    )
            if "MSIP" in bio:
                if bio["MSIP"]["perc"] > 15:
                    text += (
                        "\nAnalysen påvisar ett positivt MSI-värde ("
                        + str(bio["MSIP"]["perc"])
                        + "% mikrosatellitinstabilitet)\n"
                    )
            elif "MSIS" in bio:
                if bio["MSIS"]["perc"] > 15:
                    text += (
                        "\nAnalysen påvisar ett positivt -MSI-värde ("
                        + str(bio["MSIS"]["perc"])
                        + "% mikrosatellitinstabilitet)\n"
                    )
        return text

    @staticmethod
    def generate_ai_text(assay, variants, incl_genes, genelists, group):
        """
        Function to generate a text for the AI summary in the report.
        """
        text = ""
        conclusion = ""
        if assay == "fusion":
            text = "RNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela mRNA transkriptomet och avser detektion av fusionsgener.\n\nFör ytterligare information om utförd analys och beskrivning av eventuellt funna fusionsgener, var god se bifogad rapport. RNA-seq-analys har gjorts som led i ett utvecklingsarbete och har ej debiterats. Analysen omfattas inte av ackrediteringen."

        if assay == "fusionrna":
            text = "RNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar kända fusionsgener vid solid tumörsjukdom, se Analysbeskrivning nedan.\n\nFör ytterligare information om utförd analys och beskrivning av eventuellt funna fusionsgener, var god se bifogad rapport. Analysen omfattas inte av ackrediteringen."

        if assay == "tumwgs":
            text = "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela genomet (WGS; whole genome sequencing) med indikationsspecifik analys av somatiska varianter (SNVs, indels, amplifieringar, homozygota deletioner samt större alleliska obalanser (förlust och överskott av genetiskt material). Korresponderande normalprov har använts som kontrollmaterial.\n\nFör ytterligare information om utförd analys och beskrivning av somatiskt förvärvade varianter, var god se bifogad rapport. Analysen omfattas inte av ackrediteringen."

        if assay == "myeloid" or assay == "gmsonco" or assay == "solid":
            text = ""

            class_vars = defaultdict(lambda: defaultdict(list))
            class_cnt = defaultdict(int)
            for v in sorted(
                variants, key=lambda d: d["GT"][0]["AF"], reverse=True
            ):
                if "irrelevant" in v and v["irrelevant"] == True:
                    continue
                if (
                    len(incl_genes) > 0
                    and v["INFO"]["selected_CSQ"]["SYMBOL"] not in incl_genes
                ):
                    continue
                percent = ""
                for gt in v["GT"]:
                    if gt["type"] == "case":
                        percent = str(int(round(100 * gt["AF"], 0))) + "%"
                class_vars[v["classification"]["class"]][
                    v["INFO"]["selected_CSQ"]["SYMBOL"]
                ].append(percent)
                class_cnt[v["classification"]["class"]] += 1

            first = 1

            ## Use groups table from mongodb to determine things ##
            group_config = app.config["GROUPS_COLL"].find_one({"_id": group})

            if group_config:
                if "panel_name" in group_config:
                    panel_name = group_config["panel_name"]
                ## fallback to original assay in coyote
            else:
                panel_name = "Illuminas TruSight Myeloid"

            if len(genelists) > 0:
                the_lists = []
                for genelist in genelists:
                    list_name = genelist[9:].upper()
                    the_lists.append(list_name)
                the_lists_spoken = CommonUtility.nl_join(the_lists, "samt")
                if len(genelists) == 1:
                    genepanel_plural = "en "
                else:
                    genepanel_plural = "erna "
                if len(incl_genes) == 1:
                    gene_plural = "en "
                    definite_article = " vilken är inkluderad"
                else:
                    gene_plural = "erna "
                    definite_article = " vilka inkluderas"
                incl_genes_copy = incl_genes[:]
                the_genes = CommonUtility.nl_join(incl_genes_copy, "samt")
                text += (
                    "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar gen"
                    + gene_plural
                    + "(genpanel"
                    + genepanel_plural
                    + ": "
                    + the_lists_spoken
                    + ") "
                    + the_genes
                    + definite_article
                    + " i "
                    + panel_name
                    + " sekvenseringspanel.\n\n"
                )
            else:
                if group == "myeloid_GMSv1":
                    text += (
                        "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i 191 gener som inkluderas i %s sekvenseringspanel. Analysen avser somatiska varianter (hudbiopsi har använts som kontrollmaterial). För CEBPA undersöks även konstitutionella varianter.\n\n"
                        % panel_name
                    )
                elif group == "solid_GMSv3":
                    text += (
                        "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i 560 gener som inkluderas i %s sekvenseringspanel. Analysen avser somatiska varianter (blodprov har använts som kontrollmaterial). För BRCA1 och BRCA2 undersöks även konstitutionella varianter.\n\n"
                        % panel_name
                    )
                else:
                    text += "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner och hotspot-regioner i 54 gener som inkluderas i Illuminas TruSight Myeloid sekvenseringspanel. Analysen avser somatiska varianter (hudbiopsi har använts som kontrollmaterial). För CEBPA undersöks även konstitutionella varianter.\n\n"

            if 1 in class_vars:
                text += "Vid analysen finner man "

                num_vars = class_cnt[1]
                num_genes = len(class_vars[1])
                plural = "er" if num_vars > 1 else ""
                text += (
                    CommonUtility.nl_num(num_vars, "n")
                    + " variant"
                    + plural
                    + " av stark klinisk signifikans (Tier I)"
                )
                if num_genes == 1:
                    first = 0
                    for gene, perc_arr in class_vars[1].items():
                        text += (
                            " i "
                            + gene
                            + " (i "
                            + CommonUtility.nl_join(perc_arr, "respektive")
                            + " av läsningarna)"
                        )
                elif num_genes > 1:
                    text += ": "
                    gene_texts = []
                    for gene, perc_arr in class_vars[1].items():
                        t = (
                            CommonUtility.nl_num(len(perc_arr), "n")
                            + " i "
                            + gene
                            + " ("
                        )
                        if first == 1:
                            t += "i "
                        t += CommonUtility.nl_join(perc_arr, "respektive")
                        if first == 1:
                            t += " av läsningarna"
                        t += ")"
                        gene_texts.append(t)
                        first = 0
                    text += CommonUtility.nl_join(gene_texts, "och")

                text += ". "

            if 2 in class_vars:
                num_vars = class_cnt[2]
                num_genes = len(class_vars[2])
                plural = "er" if num_vars > 1 else ""

                if 1 in class_vars:
                    text += "Vidare ses "
                else:
                    text += "Vid analysen finner man "

                text += (
                    CommonUtility.nl_num(num_vars, "n")
                    + " variant"
                    + plural
                    + " av potentiell klinisk signifikans (Tier II)"
                )

                if num_genes == 1:
                    for gene, perc_arr in class_vars[2].items():
                        text += " i " + gene + " ("
                        if first == 1:
                            text += "i "
                        text += CommonUtility.nl_join(perc_arr, "respektive")
                        if first == 1:
                            text += " av läsningarna"
                        text += ")"

                if num_genes > 1:
                    text += ": "

                    gene_texts = []
                    for gene, perc_arr in class_vars[2].items():
                        t = (
                            CommonUtility.nl_num(len(perc_arr), "n")
                            + " i "
                            + gene
                            + " ("
                            + CommonUtility.nl_join(perc_arr, "respektive")
                        )
                        if first == 1:
                            t += " av läsningarna"
                        t += ")"
                        gene_texts.append(t)
                        first = 0
                    text += CommonUtility.nl_join(gene_texts, "och")

                text += ". "

            if 3 in class_vars and assay != "solid":
                num_vars = class_cnt[3]
                num_genes = len(class_vars[3])
                plural = "er" if num_vars > 1 else ""

                if 1 in class_vars and 2 in class_vars:
                    text += "Slutligen ses "
                elif 1 in class_vars or 2 in class_vars:
                    text += "Vidare ses "
                else:
                    text += "Vid analysen finner man "

                text += (
                    CommonUtility.nl_num(num_vars, "n")
                    + " variant"
                    + plural
                    + " av oklar klinisk signifikans (Tier III)"
                )

                if num_genes == 1:
                    for gene, perc_arr in class_vars[3].items():
                        text += " i " + gene + " ("
                        if first == 1:
                            text += "i "
                        text += CommonUtility.nl_join(perc_arr, "respektive")
                        if first == 1:
                            text += " av läsningarna"
                        text += ")"

                if num_genes > 1:
                    text += ": "

                    gene_texts = []
                    for gene, perc_arr in class_vars[3].items():
                        t = (
                            CommonUtility.nl_num(len(perc_arr), "n")
                            + " i "
                            + gene
                            + " ("
                            + CommonUtility.nl_join(perc_arr, "respektive")
                        )
                        if first == 1:
                            t += " av läsningarna"
                        t += ")"
                        gene_texts.append(t)
                        first = 0
                    text += CommonUtility.nl_join(gene_texts, "och")

                text += ". "

            if 1 in class_vars or 2 in class_vars or 3 in class_vars:
                text += "\n"
            else:
                text += "Vid analysen har inga somatiskt förvärvade varianter i undersökta gener påvisats.\n"

            if group_config:
                if "accredited" in group_config:
                    if group_config["accredited"]:
                        accredited = ""
                    else:
                        accredited = (
                            "Analysen omfattas inte av ackrediteringen."
                        )
            else:
                accredited = "Analysen omfattas inte av ackrediteringen."
            conclusion = (
                "\nFör ytterligare information om utförd analys och beskrivning av somatiskt förvärvade varianter, var god se bifogad rapport. "
                + accredited
            )

        return text, conclusion

    @staticmethod
    def get_gt_calls(variant: dict) -> list:
        """
        Retrieve genotype (GT) call information for the given variant.

        Args:
            variant (dict): A variant dictionary containing a `GT` key with genotype call data.

        Returns:
            list: A list of HTML list item strings, each representing a sample's genotype and allele frequency.
        """

        gtcalls = []
        for gt in variant["GT"]:
            gtcalls.append(
                f"<li>{gt['sample']} : {gt['GT']} ({str(gt['AF'])})</li>"
            )
        return gtcalls

    @staticmethod
    def compose_sanger_email(var: dict, sample_name: str) -> tuple[str, dict]:
        """
        Compose an email for the Sanger sequencing order.

        Args:
            var (dict): The variant dictionary containing variant and annotation information.
            sample_name (str): The name of the sample for which the Sanger order is being composed.

        Returns:
            tuple[str, dict]: A tuple containing the HTML content for the email and the selected CSQ information.
        """

        tx_info = var["INFO"]["selected_CSQ"]
        varid = (
            f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}"
        )
        hg38_chr, hg38_pos = CommonUtility.get_hg38_pos(
            str(var["CHROM"]), str(var["POS"])
        )
        ncbi_link = CommonUtility.get_ncbi_link(hg38_chr, hg38_pos)
        thermo_link = CommonUtility.get_thermo_link(hg38_chr, hg38_pos)
        gtcalls = DNAUtility.get_gt_calls(var)

        hgvsc = "-"
        hgvsp = "-"
        exon = "-"
        if len(tx_info.get("HGVSc")) > 0:
            hgvsc = tx_info.get("HGVSc", "-:-").split(":")[1]

        if len(tx_info.get("EXON")) > 0:
            exon = tx_info.get("EXON", "-:-").split("/")[0]

        if len(tx_info.get("HGVSp")) > 0:
            hgvsp = tx_info.get("HGVSp", "-:-").split(":")[1]

        tx_changes = f"<li>{tx_info['SYMBOL']} : {tx_info['Feature']} : exon{exon} : {hgvsc} : {hgvsp}</li>"

        html = f"""
        <ul>
            <li><strong>Case {sample_name}</strong>: <a href="{app.config["SANGER_URL"]}/{var["_id"]}</a>{varid}</li>
            <li><strong>HGNC symbols</strong>: {tx_info["SYMBOL"]}</li>
            <li><strong>GT call</strong></li>{"".join(gtcalls)}
            <li><strong>Amino acid changes</strong></li>
            {tx_changes}
            <li><strong>hg19</strong>: {var["CHROM"]}:{var["POS"]}</li>
            <li><strong>hg38</strong>: {hg38_chr}:{hg38_pos}</li>
            <li>{ncbi_link}</li>
            <li>{thermo_link}</li>
            <li><strong>Ordered by</strong>: Björn</li>
        </ul>
        """

        return html, tx_info

    @staticmethod
    def send_sanger_email(html: str, gene: str) -> bool | str:
        """
        Send a Sanger sequencing order email using the provided HTML content and gene name.

        Args:
            html (str): The HTML content for the Sanger order email.
            gene (str): The gene symbol associated with the Sanger order.

        Returns:
            bool | str: The result of the email sending operation.
        """
        return subprocess.check_output(
            [
                app.config["SANGER_EMAIL_SCRIPT"],
                app.config["SANGER_EMAIL_RECEPIENTS"],
                gene,
                html,
            ]
        ).decode()

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
    def create_comment_doc(
        data: dict,
        nomenclature: str = "",
        variant: str = "",
        key: str = "text",
    ) -> dict:
        """
        Create a variant comment document.

        This function constructs a dictionary representing a comment on a variant, including metadata such as author, creation time, nomenclature, and assay information.
        It supports both global and non-global comments, and can be customized with additional keys.

        Args:
            data (dict): Input data containing comment and variant information.
            nomenclature (str, optional): The nomenclature type for the variant (e.g., 'p', 'c', 'g'). Defaults to "".
            variant (str, optional): The variant string or identifier. Defaults to "".
            key (str, optional): The key in `data` to use for the comment text. Defaults to "text".

        Returns:
            dict: A dictionary representing the comment document, ready for storage or further processing.
        """
        if data.get("global", None) == "global":
            doc = {
                "text": data.get(key),  # common
                "author": current_user.username,  # common
                "time_created": datetime.now(),  # common
                "variant": variant,  # common
                "nomenclature": nomenclature,  # common
                "assay": data.get("assay_group", None),  # common
                "subpanel": data.get("subpanel", None),  # common
            }
            if nomenclature not in ["f", "t", "cn"]:
                doc["gene"] = data.get("gene", None)
                doc["transcript"] = data.get("transcript", None)
            elif nomenclature == "f":
                doc["gene1"] = data.get("gene1", None)
                doc["gene2"] = data.get("gene2", None)
            elif nomenclature == "t":
                doc["gene1"] = data.get("gene1", None)
                doc["gene2"] = data.get("gene2", None)
            elif nomenclature == "cn":
                pass
        else:
            doc = {
                "$push": {
                    "comments": {
                        "_id": ObjectId(),
                        "hidden": 0,
                        "text": data.get(key),
                        "author": current_user.username,
                        "time_created": datetime.now(),
                    }
                }
            }

        return doc

    @staticmethod
    def filter_low_coverage_with_cosmic(
        low_coverage: list, cosmic: list
    ) -> list:
        """
        Filter low coverage variants using COSMIC data.

        This function filters a list of low coverage variants by cross-referencing them with COSMIC (Catalogue Of Somatic Mutations In Cancer) data.
        It returns only those low coverage variants that have matching entries in the provided COSMIC list.

        Args:
            low_coverage (list): List of low coverage variant dictionaries.
            cosmic (list): List of COSMIC variant dictionaries.

        Returns:
            list: Filtered list of low coverage variants that have matches in COSMIC.
        """
        # Sort cosmic data by chromosome and start position for efficient searching
        if not cosmic:
            return []
        cosmic.sort(key=lambda x: (x["chr"], x["start"]))

        filtered_low_cov: list = []

        for low_cov in low_coverage:
            low_cov["cosmic"] = []
            # Find the starting index in the sorted cosmic list
            start_idx = bisect_left(
                cosmic,
                (str(low_cov["chr"]), str(low_cov["start"])),
                key=lambda x: (str(x["chr"]), str(x["start"])),
            )
            # Iterate through the cosmic list from the starting index
            for cos in cosmic[start_idx:]:
                if (
                    int(cos["chr"]) != int(low_cov["chr"])
                    or int(cos["start"]) > int(low_cov["end"])
                    or int(cos["start"]) < int(low_cov["start"])
                ):
                    break
                # if int(low_cov["start"]) >= int(cos["start"]) <= int(low_cov["end"]):
                else:
                    low_cov["cosmic"].append(
                        {k: v for k, v in cos.items() if k != "_id"}
                    )
            if len(low_cov["cosmic"]) > 0:
                filtered_low_cov.append(low_cov)

        return filtered_low_cov

    @staticmethod
    def create_annotation_text_from_gene(
        gene: str, csq: list, assay_group: str, **kwargs
    ) -> str:
        """
        Generate an automated text annotation for tier 3 variants.

        This function creates a default annotation text for variants classified as tier 3.
        It also checks if an annotation already exists for the variant and avoids adding a new one if so.

        Args:
            gene (str): The gene symbol for the variant.
            csq (list): List of consequence terms for the variant.
            assay_group (str): The assay group (e.g., 'myeloid', 'solid').
            **kwargs: Additional keyword arguments.

        Returns:
            str: The generated annotation text for the tier 3 variant.
        """
        first_csq = str(csq[0])
        ## Might need a prettier way of presenting variant type. In line with translation dict used in list_variants
        consequence = first_csq.replace("_", " ")
        tumor_type = ""
        if assay_group == "myeloid":
            tumor_type = "hematologiska"
        elif assay_group == "solid":
            tumor_type = "solida"
        else:
            tumor_type = ""

        ## Bit stinky to have in code, maybe in config for coyote3.0
        text = f"Analysen påvisar en {consequence}. Varianten är klassad som Tier III då varianter i {gene} är sällsy men förekommer i {tumor_type} maligniteter."
        gene_oncokb = kwargs.get("gene_oncokb", None)
        if gene_oncokb:
            text += f" För ytterligare information om {gene} se https://www.oncokb.org/gene/{gene}."
        else:
            text += f" {gene} finns ej beskriven i https://www.oncokb.org."
        app.logger.debug(text)
        return text

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
    def process_gene_annotations(annotations: dict) -> dict:
        """
        Process gene annotations.

        Args:
            annotations (dict): A dictionary containing gene annotation data.

        Returns:
            dict: The processed gene annotation data.
        """
        annotations_dict = defaultdict(lambda: defaultdict(dict))
        for anno in annotations:
            if "class" in anno:
                if "assay" in anno:
                    assub = anno["assay"] + ":" + anno["subpanel"]
                    annotations_dict[assub][anno["variant"]][
                        "latest_class"
                    ] = anno
                else:
                    annotations_dict["historic:None"][anno["variant"]][
                        "latest_class"
                    ] = anno
            if "text" in anno:
                if "assay" in anno:
                    assub = anno["assay"] + ":" + anno["subpanel"]
                    annotations_dict[assub][anno["variant"]][
                        "latest_text"
                    ] = anno
                else:
                    annotations_dict["historic:None"][anno["variant"]][
                        "latest_text"
                    ] = anno

        return annotations_dict
