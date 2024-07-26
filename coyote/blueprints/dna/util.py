from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from flask import current_app as app


class DNAUtility:
    """
    Utility class for variants blueprint
    """

    @staticmethod
    def get_filter_conseq_terms(checked):

        # NOT IMPLEMENTED!
        # transcript_ablation
        # transcript_amplification
        # protein_altering_variant
        # incomplete_terminal_codon_variant
        # mature_miRNA_variant
        # NMD_transcript_variant
        # TFBS_ablation
        # TFBS_amplification
        # TF_binding_site_variant
        # regulatory_region_ablation
        # regulatory_region_amplification

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
    def create_cnveffectlist(cnvtype):
        """
        This is stupid. It allows to filter CNVs depending on types. The filter in template is called
        loss or gain, but the variants are annotated with DEL or AMP. This just translates between
        """
        types = []
        for name in cnvtype:
            effect = name.split("_", 1)[1]
            if effect == "loss":
                types.append("DEL")
            if effect == "gain":
                types.append("AMP")
        return types

    @staticmethod
    def parse_allele_freq(freq, allele):
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
    def popfreq_filter(variants, max_freq):

        filtered_variants = []

        for v in variants:
            allele = v["ALT"]
            exac = DNAUtility.parse_allele_freq(v["INFO"]["selected_CSQ"].get("ExAC_MAF"), v["ALT"])
            thousand_g = DNAUtility.parse_allele_freq(
                v["INFO"]["selected_CSQ"].get("GMAF"), v["ALT"]
            )
            gnomad = v["INFO"]["selected_CSQ"].get("gnomAD_AF", 0)
            gnomad_genome = v["INFO"]["selected_CSQ"].get("gnomADg_AF", 0)
            if gnomad == "." or gnomad == "":
                gnomad = -1
            if gnomad_genome == "." or gnomad_genome == "":
                gnomad_genome = -1

            try:
                if max_freq < 1 and (
                    exac > max_freq
                    or thousand_g > max_freq
                    or float(gnomad) > max_freq
                    or float(gnomad_genome) > max_freq
                ):
                    pass
                else:
                    filtered_variants.append(v)
            except TypeError:
                filtered_variants.append(v)

        return filtered_variants

    @staticmethod
    def format_pon(variant):
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
    def select_csq(csq_arr, canonical):

        db_canonical = -1
        vep_canonical = -1
        first_protcoding = -1

        impact_order = ["HIGH", "MODERATE", "LOW", "MODIFIER"]

        for impact in impact_order:
            for csq_idx, csq in enumerate(csq_arr):
                if csq["IMPACT"] == impact:

                    if csq["SYMBOL"] in canonical and canonical[
                        csq["SYMBOL"]
                    ] == DNAUtility.refseq_noversion(csq["Feature"]):
                        db_canonical = csq_idx
                        return (csq_arr[db_canonical], "db")
                    if csq["CANONICAL"] == "YES" and vep_canonical == -1:
                        vep_canonical = csq_idx
                    if (
                        first_protcoding == -1
                        and csq["BIOTYPE"] == "protein_coding"
                        and first_protcoding == -1
                    ):
                        first_protcoding = csq_idx

        if vep_canonical >= 0:
            return (csq_arr[vep_canonical], "vep")
        elif first_protcoding >= 0:
            return (csq_arr[first_protcoding], "random")

        return (csq_arr[0], "random")

    @staticmethod
    def refseq_noversion(acc):
        a = acc.split(".")
        return a[0]

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
    def summerize_fusion(variants):
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
    def summerize_cnv(variants):
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
    def summerize_bio(variants):
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
            for v in sorted(variants, key=lambda d: d["GT"][0]["AF"], reverse=True):
                if "irrelevant" in v and v["irrelevant"] == True:
                    continue
                if len(incl_genes) > 0 and v["INFO"]["selected_CSQ"]["SYMBOL"] not in incl_genes:
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
                        accredited = "Analysen omfattas inte av ackrediteringen."
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
        Get GT call data for the variant
        """

        gtcalls = []
        for gt in variant["GT"]:
            gtcalls.append(f"<li>{gt['sample']} : {gt['GT']} ({str(gt['AF'])})</li>")
        return gtcalls

    @staticmethod
    def compose_sanger_email(var: dict, sample_name: str) -> str:
        """
        Compose an email for the sanger order
        """

        tx_info = var["INFO"]["selected_CSQ"]
        varid = f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}"
        hg38_chr, hg38_pos = CommonUtility.get_hg38_pos(str(var["CHROM"]), str(var["POS"]))
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

        tx_changes = (
            f"<li>{tx_info['SYMBOL']} : {tx_info['Feature']} : exon{exon} : {hgvsc} : {hgvsp}</li>"
        )

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
    def send_sanger_email(html: str, gene: str) -> bool:
        """
        Send Sanger Email
        """
        return subprocess.check_output(
            [
                app.config["SANGER_EMAIL_SCRIPT"],
                app.config["SANGER_EMAIL_RECEPIENTS"],
                gene,
                html,
            ]
        ).decode("utf-8")

    @staticmethod
    def get_tier_classification(data: dict) -> int:
        """
        Get the tier classification for the variant
        """
        tiers = {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}
        class_num = 0
        for key, value in tiers.items():
            if data.get(key, None) is not None:
                class_num = value

        return class_num

    @staticmethod
    def get_variant_nomenclature(data: dict) -> str:
        """
        Get the nomenclature for the variant
        """
        nomenclature = "p"
        var_nomenclature = {
            "var_p": "p",
            "var_c": "c",
            "fusionpoints": "f",
            "var_g": "g",
            "translocpoints": "t",
            "cnvvar": "cn",
        }
        for key, value in var_nomenclature.items():
            if key in data:
                variant = data.get(key, None)
                nomenclature = value
                break

        return nomenclature, variant

    @staticmethod
    def create_comment_doc(
        data: dict, nomenclature: str = "", variant: str = "", key: str = "text"
    ) -> dict:
        """
        Create a variant comment document
        """
        if data.get("global", None) == "global":
            doc = {
                "text": data.get(key),  # common
                "author": current_user.get_id(),  # common
                "time_created": datetime.now(),  # common
                "variant": variant,  # common
                "nomenclature": nomenclature,  # common
                "assay": data.get("assay", None),  # common
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
                        "author": current_user.get_id(),
                        "time_created": datetime.now(),
                    }
                }
            }

        return doc
