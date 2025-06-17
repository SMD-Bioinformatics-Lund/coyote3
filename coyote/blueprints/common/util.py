from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from coyote.util.report.report_util import ReportUtility
from flask import current_app as app
from coyote.extensions import store
from bisect import bisect_left


class BPCommonUtility:
    """
    Utility class for variants blueprint
    """
    @staticmethod
    def generate_summary_text(sample_ids, assay_config, assay_panel_doc, summary_sections_data, genes_chosen, checked_genelists):
        text = ''
        
        # generic information about panel design and active genelists
        text += BPCommonUtility.summarize_intro( sample_ids, genes_chosen, checked_genelists, assay_config, assay_panel_doc )
        # get summary for SNVs
        if 'snvs' in summary_sections_data:
            # Clinically relevant SNVs and small indels
            text = text + "## Kliniskt relevanta SNVs och små INDELs:"
            text += "\n\n"
            class_vars, class_cnt = BPCommonUtility.sort_tiered_variants(summary_sections_data['snvs'], genes_chosen)
            text = BPCommonUtility.summarize_tiered_snvs( class_vars, class_cnt, text)
            if 1 in class_vars or 2 in class_vars or 3 in class_vars:
                text += "\n\n"
            else:
                text += "Vid analysen har inga somatiskt förvärvade varianter i undersökta gener påvisats.\n\n"

        if 'cnvs' in summary_sections_data:
            if len(summary_sections_data['cnvs']) > 0:
                # Clinically relevant genespecific copy number changes
                text = text + "## Kliniskt relevanta genspecifika kopietalsförändringar:"
                text += "\n\n"
                text += BPCommonUtility.summarize_cnv(summary_sections_data['cnvs'])
                text += "\n"
        if 'translocs' in summary_sections_data:
            if len(summary_sections_data['translocs']) > 0:
                # Clinically relevant genespecific DNA-fusions
                text = text + "## Kliniskt relevanta genspecifika DNA-fusioner: \n"
                text += BPCommonUtility.summarize_transloc(summary_sections_data['translocs'])
                text += "\n"
        if 'fusions' in summary_sections_data:
            ...
        if 'biomarkers' in summary_sections_data:
            text = text + "## Andra kliniskt relevanta biomarkörer: \n"
            text += BPCommonUtility.summarize_bio(summary_sections_data['biomarkers'])
            text += "\n"
        
        accredited_assay = False # this should be configurable    
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
    def summarize_intro( sample_ids, genes_chosen, checked_genelists, assay_config, assay_panel_doc ):
        text = assay_config['reporting']['general_report_summary']
        germline_intersection = list(set(assay_panel_doc['germline_genes']) & set(genes_chosen))

        # add text about control sample used
        controll_tissue = "hudbiopsi" # this needs to be configurable
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
                the_genes = " som innefattar gen" + gene_plural + ": " + str(CommonUtility.nl_join(incl_genes_copy, "samt"))
            else:
                the_genes = " som innefattar " + str(len(genes_chosen)) + " gener"
            text += (
                # DNA has been extracted from the sent sample and has been analyzed with massive parallel sequencing. The analysis encompasses
                "Analysen omfattar "
                + "genlist" + str(genepanel_plural)
                + ": "
                + str(the_lists_spoken)
                + the_genes
                + ". "
            )
            if len(sample_ids) == 2:
                if len(germline_intersection) > 1:
                    germ_spoken = str(CommonUtility.nl_join(incl_genes_copy, "samt"))
                else:
                    germ_spoken = germline_intersection[0]
                text += f"För {germ_spoken} undersöks även konstitutionella varianter."
        text += "\n\n"
        return text

    @staticmethod
    def summarize_transloc(variants):
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
                            interesting[genes[0] + " och " + genes[1]] = af_dict
                        if "PR" in gt:
                            pr = gt["PR"].split(",")
                            af_pr = (
                                round(float(pr[1]) / (float(pr[1]) + float(pr[0])), ndigits=3) * 100
                            )
                            if af_pr > interesting[genes[0] + " och " + genes[1]]["af_pr"]:
                                interesting[genes[0] + " och " + genes[1]]["af_pr"] = af_pr
                        if "SR" in gt:
                            sr = gt["SR"].split(",")
                            af_sr = (
                                round(float(sr[1]) / (float(sr[1]) + float(sr[0])), ndigits=3) * 100
                            )
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
    def summarize_cnv(variants):
        """
        Smart-text for summerizing interesting CNV finds. Depending on what type of evidence is present
        it will present PR or SR for manta-like calls, and copy number calls for read-depth based calls.
        It will mention assay-interesting genes and how many other genes the call spans over
        """
        interesting = {}
        for var in variants:
            if "interesting" in var:
                if var["interesting"]:
                    coord = str(var["chr"]) + ":" + str(var["start"]) + "-" + str(var["end"])
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
                    if other_genes > interesting[goi + ":" + suffix]["other_genes"]:
                        interesting[goi + ":" + suffix]["other_genes"] = other_genes
                    if "gatk" in var["callers"] or "cnvkit" in var["callers"]:
                        if cn > interesting[goi + ":" + suffix]["cn"]:
                            interesting[goi + ":" + suffix]["cn"] = cn
                    if "manta" in var["callers"]:
                        if var["SR"] != 0:
                            sr = var["SR"].split("/")
                            af_sr = (
                                round(float(sr[1]) / (float(sr[1]) + float(sr[0])), ndigits=3) * 100
                            )
                            interesting[goi + ":" + suffix]["af_sr"] = af_sr
                        if var["PR"] != 0:
                            pr = var["PR"].split("/")
                            af_pr = (
                                round(float(pr[1]) / (float(pr[1]) + float(pr[0])), ndigits=3) * 100
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

    @staticmethod
    def summarize_bio(variants):
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
    def sort_tiered_variants( variants, genes_chosen ):
        class_vars = defaultdict(lambda: defaultdict(list))
        class_cnt = defaultdict(int)
        for v in sorted(variants, key=lambda d: d["GT"][0]["AF"], reverse=True):
            if "irrelevant" in v and v["irrelevant"] == True:
                continue
            if len(genes_chosen) > 0 and v["INFO"]["selected_CSQ"]["SYMBOL"] not in genes_chosen:
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
    def summarize_tiered_snvs( class_vars, class_cnt, text ):
        first = 1
        tiers_text = {
            1 : " av stark klinisk signifikans (Tier I)", # of clinical significance..
            2 : " av potentiell klinisk signifikans (Tier II)", # of potential clinical significance..
            3 : " av oklar klinisk signifikans (Tier III)" # of unknown clinical significance
        }
        
        tiers_to_summarize = [1,2,3] # this should be configurable
        for tier in tiers_to_summarize:
            if tier in class_vars:
                if 1 in class_vars and 2 in class_vars and tier == 3:
                    text += "Slutligen ses " # Finally it is found
                elif tier != 1 and (1 in class_vars or 2 in class_vars):
                    text += "Vidare ses " # Further findings
                else:
                    text += "Vid analysen finner man " # Analysis finds

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
                            + " av läsningarna)" # of the reads
                        )
                elif num_genes > 1:
                    text += ": "
                    gene_texts = []
                    for gene, perc_arr in class_vars[tier].items():
                        t = CommonUtility.nl_num(len(perc_arr), "n") + " i " + gene + " ("
                        if first == 1:
                            t += "i "
                        t += CommonUtility.nl_join(perc_arr, "respektive")
                        if first == 1:
                            t += " av läsningarna" # of the reads
                        t += ")"
                        gene_texts.append(t)
                        first = 0
                    text += CommonUtility.nl_join(gene_texts, "och")
                text += ". "
        return text
  