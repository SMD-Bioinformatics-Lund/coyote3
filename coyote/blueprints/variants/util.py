from flask import current_app as app
from collections import defaultdict
import re
from math import floor, log10


def get_group_defaults(group):
    """
    Return Default dict (either group defaults or coyote defaults) and setting per sample
    """
    settings = app.config["GROUP_FILTERS"]
    # Get group specific settings
    if group is not None:
        settings["error_cov"] = int(group.get("error_cov", settings["error_cov"]))
        settings["warn_cov"] = int(group.get("warn_cov", settings["warn_cov"]))
        settings["default_popfreq"] = float(
            group.get("default_popfreq", settings["default_popfreq"])
        )
        settings["default_mindepth"] = int(
            group.get("default_mindepth", settings["default_mindepth"])
        )
        settings["default_spanreads"] = int(
            group.get("default_spanreads", settings["default_spanreads"])
        )
        settings["default_spanpairs"] = int(
            group.get("default_spanpairs", settings["default_spanpairs"])
        )
        settings["default_min_freq"] = float(
            group.get("default_min_freq", settings["default_min_freq"])
        )
        settings["default_min_reads"] = int(
            group.get("default_min_reads", settings["default_min_reads"])
        )
        settings["default_max_freq"] = float(
            group.get("default_max_freq", settings["default_max_freq"])
        )
        settings["default_min_cnv_size"] = int(
            group.get("default_min_cnv_size", settings["default_min_cnv_size"])
        )
        settings["default_max_cnv_size"] = int(
            group.get("default_max_cnv_size", settings["default_max_cnv_size"])
        )
        settings["default_checked_conseq"] = group.get(
            "default_checked_conseq", settings["default_checked_conseq"]
        )
    return settings


def get_sample_settings(sample, settings):
    """
    get sample settings or use default
    """
    sample_settings = {}
    sample_settings["min_freq"] = float(sample.get("filter_min_freq", settings["default_min_freq"]))
    sample_settings["min_reads"] = int(
        float(sample.get("filter_min_reads", settings["default_min_reads"]))
    )
    sample_settings["max_freq"] = float(sample.get("filter_max_freq", settings["default_max_freq"]))
    sample_settings["min_depth"] = int(
        float(sample.get("filter_min_depth", settings["default_mindepth"]))
    )
    sample_settings["max_popfreq"] = float(
        sample.get("filter_max_popfreq", settings["default_popfreq"])
    )
    sample_settings["csq_filter"] = sample.get("checked_csq", settings["default_checked_conseq"])
    sample_settings["min_spanreads"] = int(
        float(sample.get(("filter_min_spanreads", 0), settings["default_spanreads"]))
    )
    sample_settings["min_spanpairs"] = int(
        float(sample.get(("filter_min_spanpairs", 0), settings["default_spanpairs"]))
    )
    sample_settings["min_cnv_size"] = int(
        float(sample.get("min_cnv_size", settings["default_min_cnv_size"]))
    )
    sample_settings["max_cnv_size"] = int(
        float(sample.get("max_cnv_size", settings["default_max_cnv_size"]))
    )
    return sample_settings


def get_assay_from_sample(smp):
    for assay, groups in app.config["ASSAY_MAPPER"].items():
        if any(g in smp["groups"] for g in groups):
            return assay
    return "unknown"


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
    for fieldname in checked:
        if fieldname in app.config["CONSEQ_TERMS_MAPPER"]:
            filter_conseq.extend(app.config["CONSEQ_TERMS_MAPPER"][fieldname])

    return filter_conseq


def create_genelist(list_names, gene_lists):
    genes = []
    for name, val in list_names.items():
        if val == 1:
            list_name = name.split("_", 1)[1]
            try:
                genes.extend(gene_lists[list_name])
            except:
                genes.extend(["gene list not defined"])

    return genes


def create_fusiongenelist(list_names, fusion_lists):

    fusion_genes = []
    for name in list_names:
        list_name = name.split("_", 1)[1]
        if list_name != "FCknown" and list_name != "mitelman":
            fusion_genes.extend(fusion_lists[list_name])

    return fusion_genes


def create_fusioneffectlist(eff_names):
    """
    This function translates filter-names in template to what is annotated. More verbose?
    """
    effects = []
    for name in eff_names:
        effect = name.split("_", 1)[1]
        if effect == "inframe":
            effects.append("in-frame")
        if effect == "outframe":
            effects.append("out-of-frame")

    return effects


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


def create_fusioncallers(fuscallers):
    callers = []

    for callername in fuscallers:
        caller = callername.split("_", 1)[1]
        if caller == "arriba":
            callers.append("arriba")
        if caller == "fusioncatcher":
            callers.append("fusioncatcher")
        if caller == "starfusion":
            callers.append("starfusion")
    return callers


def get_protein_coding_genes(var_iter):
    genes = {}
    variants = []
    for var in var_iter:
        for csq in var["INFO"]["CSQ"]:
            if csq["BIOTYPE"] == "protein_coding":
                genes[csq["SYMBOL"]] = 1
        variants.append(var)

    return variants, genes


def add_blacklist_data(variants, assay):
    short_pos = []

    for var in variants:
        short_pos.append(
            str(var["CHROM"]) + "_" + str(var["POS"]) + "_" + var["REF"] + "_" + var["ALT"]
        )

    black_listed = app.config["BLACKLIST_COLL"].find({"assay": assay, "pos": {"$in": short_pos}})
    black_dict = {}

    for black_var in black_listed:
        black_dict[black_var["pos"]] = black_var["in_normal_perc"]

    for var in variants:
        pos = str(var["CHROM"]) + "_" + str(var["POS"]) + "_" + var["REF"] + "_" + var["ALT"]
        if pos in black_dict:
            var["blacklist"] = black_dict[pos]


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


def popfreq_filter(variants, max_freq):

    filtered_variants = []

    for v in variants:
        allele = v["ALT"]
        exac = parse_allele_freq(v["INFO"]["selected_CSQ"].get("ExAC_MAF"), v["ALT"])
        thousand_g = parse_allele_freq(v["INFO"]["selected_CSQ"].get("GMAF"), v["ALT"])
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


def hotspot_variant(variants):
    hotspots = []
    for variant in variants:
        for csq in variant["INFO"]["selected_CSQ"]:
            if "hotspot_OID" in csq:
                if "COS" in variant["INFO"]["selected_CSQ"][csq]:
                    csq1 = csq.split("_")
                    csq2 = re.sub(r"hotspot", r"", csq1[0])
                    hotspot = variant["INFO"].get("HOTSPOT", [])
                    hotspot.append(csq2)
                    variant["INFO"]["HOTSPOT"] = hotspot
        hotspots.append(variant)

    return hotspots


def format_pon(variant):
    pon = defaultdict(dict)
    for i in variant["INFO"]:
        if "PON_" in i:
            part = i.split("_")
            if len(part) == 3:
                numtype = part[1]
                vc = part[2]
                pon[vc][numtype] = variant["INFO"][i]


def select_csq(csq_arr, canonical):

    db_canonical = -1
    vep_canonical = -1
    first_protcoding = -1

    impact_order = ["HIGH", "MODERATE", "LOW", "MODIFIER"]

    for impact in impact_order:
        for csq_idx, csq in enumerate(csq_arr):
            if csq["IMPACT"] == impact:

                if csq["SYMBOL"] in canonical and canonical[csq["SYMBOL"]] == refseq_noversion(
                    csq["Feature"]
                ):
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


def refseq_noversion(acc):
    a = acc.split(".")
    return a[0]


def generate_ai_text_nonsnv(assay, variants, group, var_type):
    """
    Function to add a summerizing text to a specific non-snv type of variation
    The default behavior of coyote is to have SNVs. If one wants to add more things
    to the 'AI' summary this function just sends it to a specilized function
    and concatenates the output into one string of text
    """
    text = ""

    if var_type == "transloc":
        text = summerize_fusion(variants)
    elif var_type == "cnv":
        text = summerize_cnv(variants)
    elif var_type == "bio":
        text = summerize_bio(variants)

    return text


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
            text += (
                " samt uppskattas det finnas " + str(interesting[voi]["af_ur"]) + " unika läsningar"
            )
        elif interesting[voi]["af_ur"] > 0:
            text += (
                " i vilken det uppskattas finnas "
                + str(interesting[voi]["af_ur"])
                + " unika läsningar"
            )
        text += ")\n"
    return text


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
                        af_sr = round(float(sr[1]) / (float(sr[1]) + float(sr[0])), ndigits=3) * 100
                        interesting[goi + ":" + suffix]["af_sr"] = af_sr
                    if var["PR"] != 0:
                        pr = var["PR"].split("/")
                        af_pr = round(float(pr[1]) / (float(pr[1]) + float(pr[0])), ndigits=3) * 100
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
            gene_spoken = nl_join(vois, "samt")
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


def nl_num(i, gender):
    names = [
        "noll",
        "en",
        "två",
        "tre",
        "fyra",
        "fem",
        "sex",
        "sju",
        "åtta",
        "nio",
        "tio",
        "elva",
        "tolv",
    ]
    if gender == "t":
        names[1] = "ett"
    if i <= 12:
        return names[i]
    else:
        return str(i)


def nl_join(arr, joiner):
    if len(arr) == 1:
        return arr[0]
    if len(arr) == 2:
        return arr[0] + " " + joiner + " " + arr[1]
    if len(arr) > 2:
        last = arr.pop()
        return ", ".join(arr) + " " + joiner + " " + last


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
            class_vars[v["classification"]["class"]][v["INFO"]["selected_CSQ"]["SYMBOL"]].append(
                percent
            )
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
            the_lists_spoken = nl_join(the_lists, "samt")
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
            the_genes = nl_join(incl_genes_copy, "samt")
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
                nl_num(num_vars, "n")
                + " variant"
                + plural
                + " av stark klinisk signifikans (Tier I)"
            )
            if num_genes == 1:
                first = 0
                for gene, perc_arr in class_vars[1].items():
                    text += (
                        " i " + gene + " (i " + nl_join(perc_arr, "respektive") + " av läsningarna)"
                    )
            elif num_genes > 1:
                text += ": "
                gene_texts = []
                for gene, perc_arr in class_vars[1].items():
                    t = nl_num(len(perc_arr), "n") + " i " + gene + " ("
                    if first == 1:
                        t += "i "
                    t += nl_join(perc_arr, "respektive")
                    if first == 1:
                        t += " av läsningarna"
                    t += ")"
                    gene_texts.append(t)
                    first = 0
                text += nl_join(gene_texts, "och")

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
                nl_num(num_vars, "n")
                + " variant"
                + plural
                + " av potentiell klinisk signifikans (Tier II)"
            )

            if num_genes == 1:
                for gene, perc_arr in class_vars[2].items():
                    text += " i " + gene + " ("
                    if first == 1:
                        text += "i "
                    text += nl_join(perc_arr, "respektive")
                    if first == 1:
                        text += " av läsningarna"
                    text += ")"

            if num_genes > 1:
                text += ": "

                gene_texts = []
                for gene, perc_arr in class_vars[2].items():
                    t = (
                        nl_num(len(perc_arr), "n")
                        + " i "
                        + gene
                        + " ("
                        + nl_join(perc_arr, "respektive")
                    )
                    if first == 1:
                        t += " av läsningarna"
                    t += ")"
                    gene_texts.append(t)
                    first = 0
                text += nl_join(gene_texts, "och")

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
                nl_num(num_vars, "n")
                + " variant"
                + plural
                + " av oklar klinisk signifikans (Tier III)"
            )

            if num_genes == 1:
                for gene, perc_arr in class_vars[3].items():
                    text += " i " + gene + " ("
                    if first == 1:
                        text += "i "
                    text += nl_join(perc_arr, "respektive")
                    if first == 1:
                        text += " av läsningarna"
                    text += ")"

            if num_genes > 1:
                text += ": "

                gene_texts = []
                for gene, perc_arr in class_vars[3].items():
                    t = (
                        nl_num(len(perc_arr), "n")
                        + " i "
                        + gene
                        + " ("
                        + nl_join(perc_arr, "respektive")
                    )
                    if first == 1:
                        t += " av läsningarna"
                    t += ")"
                    gene_texts.append(t)
                    first = 0
                text += nl_join(gene_texts, "och")

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


def cnvtype_variant(cnvs, checked_effects):
    filtered_cnvs = []
    for var in cnvs:
        if var["ratio"] > 0:
            effect = "AMP"
        if var["ratio"] < 0:
            effect = "DEL"
        if effect in checked_effects:
            filtered_cnvs.append(var)
    return filtered_cnvs


def cnv_organizegenes(cnvs):
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
