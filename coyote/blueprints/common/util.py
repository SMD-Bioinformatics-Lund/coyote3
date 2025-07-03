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
This module provides utility methods for generating summary texts and reports
related to variant analysis in the Coyote3 genomic data analysis framework.

- Contains the `BPCommonUtility` class with static methods for summarizing SNVs, CNVs, translocations, biomarkers, and introductory report sections.
- Designed for use within the Coyote3 Flask application to support clinical and research reporting workflows.

Intended for internal use as part of the Coyote3 genomic data analysis framework.
"""

from collections import defaultdict
from coyote.util.common_utility import CommonUtility
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from flask import current_app as app


class BPCommonUtility:
    """
    BPCommonUtility provides utility methods for generating summary texts and reports
    related to variant analysis in a blueprint context. It includes methods for
    summarizing SNVs, CNVs, translocations, biomarkers, and introductory report sections.
    """

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
    def generate_summary_text(
        sample_ids: list,
        assay_config: dict,
        assay_panel_doc: dict,
        summary_sections_data: dict,
        genes_chosen: list,
        checked_genelists: list,
    ) -> str:
        """
        Generates a summary text for a variant analysis report.

        This method constructs a comprehensive summary for a variant analysis report in a blueprint context. It incorporates information about the panel design,
        selected gene lists, and the genes included in the analysis. The summary includes sections for clinically relevant SNVs, CNVs, translocations, fusions,
        and other biomarkers, as well as an introductory section and a conclusion regarding the accreditation status of the assay.

        Args:
            sample_ids (list): List of sample identifiers used in the analysis.
            assay_config (dict): Dictionary containing assay configuration and reporting details.
            assay_panel_doc (dict): Dictionary containing panel documentation, including germline gene information and accreditation status.
            summary_sections_data (dict): Dictionary containing data for each report section (e.g., SNVs, CNVs, translocations, biomarkers).
            genes_chosen (list): List of gene symbols included in the analysis.
            checked_genelists (list): List of gene list names that were selected for the analysis.

        Returns:
            str: A summary text describing the scope of the analysis, the findings for each variant type, and the accreditation status.
        """
        text = ""

        # generic information about panel design and active genelists
        text += BPCommonUtility.summarize_intro(
            sample_ids,
            genes_chosen,
            checked_genelists,
            assay_config,
            assay_panel_doc,
        )
        # get summary for SNVs
        if "snvs" in summary_sections_data:
            # Clinically relevant SNVs and small indels
            text = text + "## Kliniskt relevanta SNVs och små INDELs:"
            text += "\n\n"
            class_vars, class_cnt = BPCommonUtility.sort_tiered_variants(
                summary_sections_data["snvs"], genes_chosen
            )
            text = BPCommonUtility.summarize_tiered_snvs(
                class_vars, class_cnt, text
            )
            if 1 in class_vars or 2 in class_vars or 3 in class_vars:
                text += "\n\n"
            else:
                text += "Vid analysen har inga somatiskt förvärvade varianter i undersökta gener påvisats.\n\n"

        if "cnvs" in summary_sections_data:
            if len(summary_sections_data["cnvs"]) > 0:
                # Clinically relevant genespecific copy number changes
                text = (
                    text
                    + "## Kliniskt relevanta genspecifika kopietalsförändringar:"
                )
                text += "\n\n"
                text += BPCommonUtility.summarize_cnv(
                    summary_sections_data["cnvs"]
                )
                text += "\n"
        if "translocs" in summary_sections_data:
            if len(summary_sections_data["translocs"]) > 0:
                # Clinically relevant genespecific DNA-fusions
                text = (
                    text
                    + "## Kliniskt relevanta genspecifika DNA-fusioner: \n"
                )
                text += BPCommonUtility.summarize_transloc(
                    summary_sections_data["translocs"]
                )
                text += "\n"
        if "fusions" in summary_sections_data:
            ...
        if "biomarkers" in summary_sections_data:
            text = text + "## Andra kliniskt relevanta biomarkörer: \n"
            text += BPCommonUtility.summarize_bio(
                summary_sections_data["biomarkers"]
            )
            text += "\n"

        accredited_assay = assay_panel_doc.get("accredited", False)
        if accredited_assay:
            accredited = ""
        else:
            # the analysis is not covered by the acreditaion
            accredited = "Analysen omfattas inte av ackrediteringen."
        conclusion = (
            # for more information about the performed analysis and description of somatically gained variants, please see the attached report"
            "För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade varianter, var god se bifogad rapport. "
            + accredited
        )
        text += conclusion
        return text

    @staticmethod
    def summarize_intro(
        sample_ids: list,
        genes_chosen: list,
        checked_genelists: list,
        assay_config: dict,
        assay_panel_doc: dict,
    ) -> str:
        """
        Generates an introductory summary text for the report.

        This method creates a summary introduction for a variant analysis report. It incorporates general information about the assay, the gene lists used, the genes
        included in the analysis, and whether a control sample was used. The summary is tailored based on the provided sample IDs, selected genes, checked gene lists,
        assay configuration, and panel documentation.

        Args:
            sample_ids (list): List of sample identifiers used in the analysis.
            genes_chosen (list): List of gene symbols included in the analysis.
            checked_genelists (list): List of gene list names that were selected for the analysis.
            assay_config (dict): Dictionary containing assay configuration and reporting details.
            assay_panel_doc (dict): Dictionary containing panel documentation, including germline gene information.

        Returns:
            str: An introductory summary text for the report, describing the scope of the analysis, the gene lists and genes included, and any relevant control sample information.
        """

        text = (
            assay_config.get("reporting", {}).get("general_report_summary", "")
            or ""
        )
        germline_intersection = list(
            set(assay_panel_doc["germline_genes"]) & set(genes_chosen)
        )

        # add text about control sample used
        controll_tissue = "hudbiopsi"  # this needs to be configurable
        # The analysis was done for somatic variants (tissue_type was used as controlmaterial)
        paired_add = f"Analysen avser somatiska varianter ({controll_tissue} har använts som kontrollmaterial). "
        if len(sample_ids) == 2:
            text += paired_add

        if len(checked_genelists) > 0:
            the_lists = []
            for genelist in checked_genelists:
                list_name = genelist.upper()
                the_lists.append(list_name)
            the_lists_spoken = CommonUtility.nl_join(the_lists, "samt")
            if len(checked_genelists) == 1:
                genepanel_plural = "an"
            else:
                genepanel_plural = "orna"
            if len(genes_chosen) == 1:
                gene_plural = "en"
            else:
                gene_plural = "erna"
            incl_genes_copy = genes_chosen[:]
            if len(genes_chosen) <= 20:
                the_genes = (
                    " som innefattar gen"
                    + gene_plural
                    + ": "
                    + str(CommonUtility.nl_join(incl_genes_copy, "samt"))
                )
            else:
                the_genes = (
                    " som innefattar " + str(len(genes_chosen)) + " gener"
                )
            text += (
                # DNA has been extracted from the sent sample and has been analyzed with massive parallel sequencing. The analysis encompasses
                "Analysen omfattar "
                + "genlist"
                + str(genepanel_plural)
                + ": "
                + str(the_lists_spoken)
                + the_genes
                + ". "
            )
            if len(sample_ids) == 2:
                if len(germline_intersection) > 1:
                    germ_spoken = str(
                        CommonUtility.nl_join(incl_genes_copy, "samt")
                    )
                else:
                    germ_spoken = germline_intersection[0]
                text += f"För {germ_spoken} undersöks även konstitutionella varianter."
        text += "\n\n"
        return text

    @staticmethod
    def summarize_transloc(variants: list) -> str:
        """
        Generates a summary text for DNA fusions (translocations).

        This method analyzes a list of variant dictionaries representing DNA fusions (translocations) and summarizes the findings based on the type of supporting evidence:
        - PR (paired reads)
        - SR (split reads)
        - UR (unique reads)

        For each interesting variant, it identifies the genes involved in the fusion and calculates the highest observed percentages for each evidence type. The summary text describes the detected gene fusions, the proportion of supporting reads, and the number of unique reads, if available.

        Args:
            variants (list): List of variant dictionaries, each containing information about the DNA fusion event, supporting evidence, and gene annotations.

        Returns:
            str: A summary describing the detected gene fusions, the genes involved, and the supporting evidence (PR, SR, UR).
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
            elif len(interesting) == 2 and (cl > 1 and cl < len(interesting)):
                text += "\n" + intro[1] + " ("
            elif len(interesting) > 2 and cl == len(interesting):
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
    def summarize_cnv(variants: list) -> str:
        """
        Generates a summary text for interesting CNV (Copy Number Variation) findings.

        This method analyzes a list of CNV variant dictionaries and summarizes the results based on the type of evidence present:
        - For manta-like calls, it presents PR (paired reads) or SR (split reads) information.
        - For read-depth based calls, it presents copy number (cn) values.
        - The summary includes assay-relevant genes and the number of other genes affected by the CNV.

        Args:
            variants (list): List of CNV variant dictionaries, each containing information about the CNV event, evidence, and affected genes.

        Returns:
            str: A summary describing the detected CNVs, their type (amplification or loss), affected genes, and supporting evidence.
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
        text = ""
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
            elif len(interesting) == 2 or (cl > 1 and cl < len(interesting)):
                text += intro[1] + " (" + info
            elif len(interesting) > 2 and cl == len(interesting):
                text += intro[2] + " (" + info
            text += "). "
        text += "\n"
        return text

    @staticmethod
    def summarize_bio(variants: list) -> str:
        """
        Generates a summary text for detected biomarkers that exceed clinical thresholds.

        This method checks for specific biomarkers such as HRD and MSI in the provided list of variant dictionaries.
        If a biomarker value surpasses its defined threshold (e.g., HRD sum > 42, MSI percentage > 15),
        the result is included in the summary text with an explanatory message.

        Args:
        variants (list): List of variant dictionaries, each possibly containing HRD or MSI biomarker results.

        Returns:
            str: A summary describing detected biomarkers that surpass clinical thresholds, such as HRD and MSI values.
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
    def sort_tiered_variants(variants: list, genes_chosen: list) -> tuple:
        """
        Sorts the given list of variant dictionaries into clinical significance tiers (e.g., Tier I, II, III) based on their classification, and counts the number of affected genes per tier.

        Args:
            variants (list): List of variant dictionaries to be sorted.
            genes_chosen (list): List of gene symbols considered relevant for the analysis.

        Returns:
            tuple:
                - class_vars (dict): Maps tier (int) to a dict of gene symbols (str) and their supporting read percentages (list of str).
                - class_cnt (dict): Maps tier (int) to the count of variants (int).
        """
        class_vars = defaultdict(lambda: defaultdict(list))
        class_cnt = defaultdict(int)
        for v in sorted(
            variants, key=lambda d: d["GT"][0]["AF"], reverse=True
        ):
            if "irrelevant" in v and v["irrelevant"] == True:
                continue
            if (
                len(genes_chosen) > 0
                and v["INFO"]["selected_CSQ"]["SYMBOL"] not in genes_chosen
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
        return class_vars, class_cnt

    @staticmethod
    def summarize_tiered_snvs(
        class_vars: dict, class_cnt: dict, text: str
    ) -> str:
        """
        Generates a summary text for tiered SNVs (Single Nucleotide Variants).

        Args:
            class_vars (dict): A dictionary mapping tier (int) to gene symbols (str) and their supporting read percentages (list of str).
            class_cnt (dict): A dictionary mapping tier (int) to the count of variants (int).
            text (str): The initial summary text to append to.

        Returns:
            str: The updated summary text describing the number of variants per clinical significance tier,
                 the number of affected genes, and the proportion of reads supporting each variant.
        """
        first = 1
        tiers_text = {
            1: " av stark klinisk signifikans (Tier I)",  # of clinical significance..
            2: " av potentiell klinisk signifikans (Tier II)",  # of potential clinical significance..
            3: " av oklar klinisk signifikans (Tier III)",  # of unknown clinical significance
        }

        tiers_to_summarize = [1, 2, 3]  # this should be configurable
        present_tiers = [
            tier for tier in tiers_to_summarize if tier in class_vars
        ]
        for i, tier in enumerate(present_tiers):
            if i == 0:
                text += "Vid analysen finner man "
            elif i == len(present_tiers) - 1 and len(present_tiers) == 3:
                text += "Slutligen ses "
            else:
                text += "Vidare ses "

            num_vars = class_cnt[tier]
            num_genes = len(class_vars[tier])
            plural = "er" if num_vars > 1 else ""
            text += (
                CommonUtility.nl_num(num_vars, "n")
                + " variant"
                + plural
                + tiers_text[tier]
            )
            if num_genes == 1:
                first = 0
                for gene, perc_arr in class_vars[tier].items():
                    text += (
                        " i "
                        + gene
                        + " (i "
                        + CommonUtility.nl_join(perc_arr, "respektive")
                        + " av läsningarna)"  # of the reads
                    )
            elif num_genes > 1:
                text += ": "
                gene_texts = []
                for gene, perc_arr in class_vars[tier].items():
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
                        t += " av läsningarna"  # of the reads
                    t += ")"
                    gene_texts.append(t)
                    first = 0
                text += CommonUtility.nl_join(gene_texts, "och")
            text += ". "
        return text
    

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