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

"""Report summary and shared interpretation helpers."""

from collections import defaultdict

from bson.objectid import ObjectId
from flask import current_app as app
from flask_login import current_user

from coyote.extensions import store
from coyote.util.common_utility import CommonUtility


def process_gene_annotations(annotations: dict) -> dict:
    annotations_dict = defaultdict(lambda: defaultdict(dict))
    for anno in annotations:
        if "class" in anno:
            if "assay" in anno:
                assub = anno["assay"] + ":" + anno["subpanel"]
                annotations_dict[assub][anno["variant"]]["latest_class"] = anno
            else:
                annotations_dict["historic:None"][anno["variant"]]["latest_class"] = anno
        if "text" in anno:
            if "assay" in anno:
                assub = anno["assay"] + ":" + anno["subpanel"]
                annotations_dict[assub][anno["variant"]]["latest_text"] = anno
            else:
                annotations_dict["historic:None"][anno["variant"]]["latest_text"] = anno
    return annotations_dict


def create_annotation_text_from_gene(gene: str, csq: list, assay_group: str, **kwargs) -> str:
    first_csq = str(csq[0])
    consequence = first_csq.replace("_", " ")
    tumor_type = ""
    if assay_group == "myeloid":
        tumor_type = "hematologiska"
    elif assay_group == "solid":
        tumor_type = "solida"

    text = f"Analysen påvisar en {consequence}. Mutationen är klassad som Tier III då mutationer i {gene} är sällsynta men förekommer i {tumor_type} maligniteter."
    gene_oncokb = kwargs.get("gene_oncokb", None)
    if gene_oncokb:
        text += f" För ytterligare information om {gene} se https://www.oncokb.org/gene/{gene}."
    else:
        text += f" {gene} finns ej beskriven i https://www.oncokb.org."
    app.logger.debug(text)
    return text


def create_comment_doc(data: dict, nomenclature: str = "", variant: str = "", key: str = "text") -> dict:
    if data.get("global", None) == "global":
        doc = {
            "text": data.get(key),
            "author": current_user.username,
            "time_created": CommonUtility.utc_now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "assay": data.get("assay_group", None),
            "subpanel": data.get("subpanel", None),
        }
        if nomenclature not in ["f", "t", "cn"]:
            doc["gene"] = data.get("gene", None)
            doc["transcript"] = data.get("transcript", None)
        elif nomenclature in ["f", "t"]:
            doc["gene1"] = data.get("gene1", None)
            doc["gene2"] = data.get("gene2", None)
    else:
        doc = {
            "$push": {
                "comments": {
                    "_id": ObjectId(),
                    "hidden": 0,
                    "text": data.get(key),
                    "author": current_user.username,
                    "time_created": CommonUtility.utc_now(),
                }
            }
        }
    return doc


def generate_summary_text(
    sample_ids: list,
    assay_config: dict,
    assay_panel_doc: dict,
    summary_sections_data: dict,
    genes_chosen: list,
    checked_genelists: list,
) -> str:
    text = summarize_intro(sample_ids, genes_chosen, checked_genelists, assay_config, assay_panel_doc)

    if "snvs" in summary_sections_data:
        text = text + "## Kliniskt relevanta SNVs och små INDELs:"
        text += "\n\n"
        class_vars, class_cnt = sort_tiered_variants(summary_sections_data["snvs"], genes_chosen)
        text = summarize_tiered_snvs(class_vars, class_cnt, text)
        if 1 in class_vars or 2 in class_vars or 3 in class_vars:
            text += "\n\n"
        else:
            text += "Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats.\n\n"

    if "cnvs" in summary_sections_data and len(summary_sections_data["cnvs"]) > 0:
        text = text + "## Kliniskt relevanta genspecifika kopietalsförändringar:"
        text += "\n\n"
        text += summarize_cnv(summary_sections_data["cnvs"])
        text += "\n"

    if "translocs" in summary_sections_data and len(summary_sections_data["translocs"]) > 0:
        text = text + "## Kliniskt relevanta genspecifika DNA-fusioner: \n"
        text += summarize_transloc(summary_sections_data["translocs"])
        text += "\n"

    if "fusions" in summary_sections_data and len(summary_sections_data["fusions"]) > 0:
        text = text + "## Kliniskt relevanta RNA-fusioner: \n"
        text += summarize_transloc(summary_sections_data["fusions"])
        text += "\n"

    if "biomarkers" in summary_sections_data:
        text = text + "## Andra kliniskt relevanta biomarkörer: \n"
        text += summarize_bio(summary_sections_data["biomarkers"])
        text += "\n"

    accredited_assay = assay_panel_doc.get("accredited", False)
    accredited = "" if accredited_assay else "Analysen omfattas inte av ackrediteringen."
    conclusion = (
        "För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport. "
        + accredited
    )
    text += conclusion
    return text


def summarize_intro(
    sample_ids: list,
    genes_chosen: list,
    checked_genelists: list,
    assay_config: dict,
    assay_panel_doc: dict,
) -> str:
    text = assay_config.get("reporting", {}).get("general_report_summary", "") or ""
    germline_intersection = list(set(assay_panel_doc.get("germline_genes", [])) & set(genes_chosen))
    controll_tissue = "hudbiopsi"
    paired_add = f"Analysen avser somatiska mutationer ({controll_tissue} har använts som kontrollmaterial). "
    if len(sample_ids) == 2:
        text += paired_add

    if len(checked_genelists) > 0:
        the_lists = [genelist.upper() for genelist in checked_genelists]
        the_lists_spoken = CommonUtility.nl_join(the_lists, "samt")
        genepanel_plural = "an" if len(checked_genelists) == 1 else "orna"
        gene_plural = "en" if len(genes_chosen) == 1 else "erna"
        incl_genes_copy = genes_chosen[:]
        if len(genes_chosen) <= 20:
            the_genes = " som innefattar gen" + gene_plural + ": " + str(
                CommonUtility.nl_join(incl_genes_copy, "samt")
            )
        else:
            the_genes = " som innefattar " + str(len(genes_chosen)) + " gener"
        text += "Analysen omfattar " + "genlist" + str(genepanel_plural) + ": " + str(the_lists_spoken) + the_genes + ". "
        if len(sample_ids) == 2 and germline_intersection:
            germ_spoken = str(CommonUtility.nl_join(germline_intersection, "samt"))
            text += f"För {germ_spoken} undersöks även konstitutionella mutationer."

    text += "\n\n"
    return text


def summarize_transloc(variants: list) -> str:
    interesting = {}
    for var in variants:
        if "interesting" in var and var["interesting"]:
            if "MANE_ANN" in var["INFO"]:
                annotation = var["INFO"]["MANE_ANN"]
            else:
                annotation = var["INFO"]["ANN"][0]
            genes = annotation["Gene_Name"].split("&")
            for gt in var["GT"]:
                af_dict = {"af_pr": 0, "af_sr": 0, "af_ur": 0}
                if genes[0] + " och " + genes[1] not in interesting:
                    interesting[genes[0] + " och " + genes[1]] = af_dict
                if "PR" in gt:
                    pr = gt["PR"].split(",")
                    af_pr = round(float(pr[1]) / (float(pr[1]) + float(pr[0])), ndigits=3) * 100
                    if af_pr > interesting[genes[0] + " och " + genes[1]]["af_pr"]:
                        interesting[genes[0] + " och " + genes[1]]["af_pr"] = af_pr
                if "SR" in gt:
                    sr = gt["SR"].split(",")
                    af_sr = round(float(sr[1]) / (float(sr[1]) + float(sr[0])), ndigits=3) * 100
                    if af_sr > interesting[genes[0] + " och " + genes[1]]["af_sr"]:
                        interesting[genes[0] + " och " + genes[1]]["af_sr"] = af_sr
            if "UR" in var["INFO"]:
                af_ur = var["INFO"]["UR"]
                if af_ur > interesting[genes[0] + " och " + genes[1]]["af_ur"]:
                    interesting[genes[0] + " och " + genes[1]]["af_ur"] = af_ur

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
            text += "i " + str(interesting[voi]["af_sr"]) + "%" + " av splittade läsningar"
            af = 1
        elif interesting[voi]["af_pr"]:
            text += "i " + str(interesting[voi]["af_pr"]) + "%" + " av överspännande läsningar"
            af = 1
        if interesting[voi]["af_ur"] > 0 and af > 0:
            text += " samt uppskattas det finnas " + str(interesting[voi]["af_ur"]) + " unika läsningar"
        elif interesting[voi]["af_ur"] > 0:
            text += " i vilken det uppskattas finnas " + str(interesting[voi]["af_ur"]) + " unika läsningar"
        text += ")\n"
    return text


def summarize_cnv(variants: list) -> str:
    interesting = {}
    for var in variants:
        if "interesting" in var and var["interesting"]:
            coord = str(var["chr"]) + ":" + str(var["start"]) + "-" + str(var["end"])
            af_dict = {"af_pr": 0, "af_sr": 0, "cn": 0, "cnp": 0, "coord": coord, "other_genes": 0}
            cn = round(2 * (2 ** var["ratio"]), ndigits=2) if isinstance(var["ratio"], float) else var["ratio"]
            other_genes = 0
            goi = []
            for gene in var["genes"]:
                if "class" in gene:
                    goi.append(gene["gene"])
                else:
                    other_genes += 1
            goi = ":".join(goi)
            suffix = "amp" if var["ratio"] > 0 else "loss"
            if goi + ":" + suffix not in interesting:
                interesting[goi + ":" + suffix] = af_dict
            if other_genes > interesting[goi + ":" + suffix]["other_genes"]:
                interesting[goi + ":" + suffix]["other_genes"] = other_genes
            if "gatk" in var["callers"] or "cnvkit" in var["callers"]:
                if cn > interesting[goi + ":" + suffix]["cn"]:
                    interesting[goi + ":" + suffix]["cn"] = cn
            if "manta" in var["callers"]:
                if var["SR"] != 0:
                    sr = var["SR"].split("/")
                    af_sr = round(float(sr[1]) / (float(sr[1]) + float(sr[0])), ndigits=3) * 100
                    interesting[goi + ":" + suffix]["af_sr"] = af_sr
                if var["PR"] != 0:
                    pr = var["PR"].split("/")
                    af_pr = round(float(pr[1]) / (float(pr[1]) + float(pr[0])), ndigits=3) * 100
                    interesting[goi + ":" + suffix]["af_pr"] = af_pr

    text = ""
    cl = 0
    for voi in interesting:
        cl += 1
        vois = voi.split(":")
        effect = vois.pop()
        effect = "amplifiering" if effect == "amp" else "förlust"
        if len(vois) > 1:
            gene_spoken = CommonUtility.nl_join(vois, "samt")
            gene = "generna " + gene_spoken
        else:
            gene = "genen " + vois[0]
        info = ""
        if interesting[voi]["cn"] > 0:
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
            info += " i " + str(interesting[voi]["af_sr"]) + "%" + " av splittade läsningar"
        elif interesting[voi]["af_pr"]:
            info += " i " + str(interesting[voi]["af_pr"]) + "%" + " av överspännande läsningar"

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


def summarize_bio(variants: list) -> str:
    text = ""
    for bio in variants:
        if "HRD" in bio and bio["HRD"]["sum"] > 42:
            text += (
                "\nAnalysen påvisar ett positivt HRD-värde ("
                + str(bio["HRD"]["sum"])
                + " homologisk rekombinationsdeficiens)\n"
            )
        if "MSIP" in bio and bio["MSIP"]["perc"] > 15:
            text += (
                "\nAnalysen påvisar ett positivt MSI-värde ("
                + str(bio["MSIP"]["perc"])
                + "% mikrosatellitinstabilitet)\n"
            )
        elif "MSIS" in bio and bio["MSIS"]["perc"] > 15:
            text += (
                "\nAnalysen påvisar ett positivt -MSI-värde ("
                + str(bio["MSIS"]["perc"])
                + "% mikrosatellitinstabilitet)\n"
            )
    return text


def sort_tiered_variants(variants: list, genes_chosen: list) -> tuple:
    class_vars = defaultdict(lambda: defaultdict(list))
    class_cnt = defaultdict(int)
    for v in sorted(variants, key=lambda d: d["GT"][0]["AF"], reverse=True):
        if "irrelevant" in v and v["irrelevant"] is True:
            continue
        if len(genes_chosen) > 0 and v["INFO"]["selected_CSQ"]["SYMBOL"] not in genes_chosen:
            continue
        percent = ""
        for gt in v["GT"]:
            if gt["type"] == "case":
                percent = str(int(round(100 * gt["AF"], 0))) + "%"
        class_vars[v["classification"]["class"]][v["INFO"]["selected_CSQ"]["SYMBOL"]].append(percent)
        class_cnt[v["classification"]["class"]] += 1
    return class_vars, class_cnt


def summarize_tiered_snvs(class_vars: dict, class_cnt: dict, text: str) -> str:
    first = 1
    tiers_text = {
        1: " av stark klinisk signifikans (Tier I)",
        2: " av potentiell klinisk signifikans (Tier II)",
        3: " av oklar klinisk signifikans (Tier III)",
    }
    tiers_to_summarize = [1, 2, 3]
    present_tiers = [tier for tier in tiers_to_summarize if tier in class_vars]
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
        text += CommonUtility.nl_num(num_vars, "n") + " mutation" + plural + tiers_text[tier]
        if num_genes == 1:
            first = 0
            for gene, perc_arr in class_vars[tier].items():
                text += " i " + gene + " (i " + CommonUtility.nl_join(perc_arr, "respektive") + " av läsningarna)"
        elif num_genes > 1:
            text += ": "
            gene_texts = []
            for gene, perc_arr in class_vars[tier].items():
                t = CommonUtility.nl_num(len(perc_arr), "n") + " i " + gene + " ("
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
    return text


def get_tier_classification(data: dict) -> int:
    tiers = {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}
    class_num = 0
    for key, value in tiers.items():
        if data.get(key, None) is not None:
            class_num = value
    return class_num


def enrich_reported_variant_docs(tier_docs: list) -> list:
    enriched_docs = []
    for doc in tier_docs:
        enriched_doc = doc.copy()
        sample = store.sample_handler.get_sample_by_oid(doc.get("sample_oid", None)) or {}
        enriched_doc["sample"] = {}
        enriched_doc["sample"]["sample_name"] = sample.get("name")
        enriched_doc["sample"]["case_id"] = sample.get("case_id")
        enriched_doc["sample"]["control_id"] = sample.get("control_id")
        enriched_doc["sample"]["profile"] = sample.get("profile")
        enriched_doc["sample"]["paired"] = sample.get("paired")
        enriched_doc["sample"]["assay"] = sample.get("assay")
        enriched_doc["sample"]["subpanel"] = sample.get("subpanel")

        annotation = store.annotation_handler.get_annotation_by_oid(doc.get("annotation_oid", None))
        enriched_doc["annotation"] = {**annotation}
        enriched_docs.append(enriched_doc)
    return enriched_docs
