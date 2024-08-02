import os
from copy import deepcopy
from pathlib import Path
import subprocess
from flask import current_app as app


class CommonUtility:
    """
    List of util functions, mostly shared across Coyote main, rna and other blueprints.
    """

    @staticmethod
    def assay_config(assay_name: str = None) -> dict:
        conf = app.config.get("ASSAYS")
        if conf is None:
            return {}

        if assay_name is not None:
            conf = conf.get(assay_name)

        return deepcopy(conf)

    @staticmethod
    def get_group_parameters(group: str) -> dict:
        """
        Get group paramters data
        """
        conf = app.config.get("GROUP_CONFIGS")
        if conf is not None:
            return deepcopy(conf.get(group))
        return {}

    @staticmethod
    def table_config() -> dict:
        conf = app.config.get("TABLE")
        return deepcopy(conf)

    @staticmethod
    def cutoff_config(assay_name: str, sample_type: str = None) -> dict:
        conf = app.config.get("CUTOFFS")
        if conf is None:
            return {}
        try:
            conf = conf[assay_name]
            if sample_type is not None:
                conf = conf.get(sample_type)
        except KeyError:
            err = f"No cutoffs defined for assay: {assay_name}"
            if sample_type is not None:
                err += f", sample_type: {sample_type}"
            return {}
        return deepcopy(conf)

    @staticmethod
    def assay_info_vars(assay_name) -> list:
        assay = CommonUtility.assay_config(assay_name)
        return assay.get("sample_info")

    @staticmethod
    def assay_qc_vars(assay_name) -> list:
        assay = CommonUtility.assay_config(assay_name)
        return assay.get("sample_qc")

    @staticmethod
    def assays_in_assay_group(assay_name: str) -> list:
        return CommonUtility.assay_config(assay_name).get("include_assays")

    @staticmethod
    def has_subtypes(assay_name) -> bool:
        assay_conf = CommonUtility.assay_config(assay_name)
        return "subtypes" in assay_conf

    @staticmethod
    def get_sample_subtypes(assay_name: str) -> list:
        """
        Get list of available subtypes for assay defined in assays.config
        """
        assay = CommonUtility.assay_config(assay_name)
        subtypes = assay.get("subtypes", {})
        subtypes = subtypes.get("subtype_names", None)
        return subtypes

    @staticmethod
    def subtype_id_var(assay_name) -> list:
        if not CommonUtility.has_subtypes(assay_name):
            return None

        assay_conf = CommonUtility.assay_config(assay_name)

        if "subtype_id_col" not in assay_conf:
            config_path = app.config.get("PATH_ASSAY_CONFIG")
            raise AttributeError(
                f"Error in assay config: {config_path}. "
                "subtypes enabled but no subtype_id_col "
                f"defined for {assay_name}."
            )

        return assay_conf["subtype_id_col"]

    @staticmethod
    def assay_exists(assay_name: str) -> bool:
        """Check if assay defined in config"""
        conf = CommonUtility.assay_config()
        return assay_name in conf

    @staticmethod
    def assay_names_for_db_query(assay_category_name):
        # Ignore _restored
        assay_names = CommonUtility.assay_config(assay_category_name.removesuffix("_restored")).get(
            "include_assays"
        )
        if assay_category_name.endswith("_restored"):
            assay_names = [f"{assay_name}_restored" for assay_name in assay_names]

        return assay_names

    @staticmethod
    def get_assay_from_sample(smp):
        conf = app.config.get("ASSAY_MAPPER")
        if conf is None:
            return None
        for assay, groups in conf.items():
            if any(g in smp["groups"] for g in groups):
                return assay
        return "unknown"

    @staticmethod
    def get_group_defaults(group):
        """
        Return Default dict (either group defaults or coyote defaults) and setting per sample
        """
        settings = app.config.get("GROUP_FILTERS")
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

    @staticmethod
    def get_sample_settings(sample, settings):
        """
        get sample settings or use default
        """
        sample_settings = {}
        sample_settings["min_freq"] = float(
            sample.get("filter_min_freq", settings["default_min_freq"])
        )
        sample_settings["min_reads"] = int(
            float(sample.get("filter_min_reads", settings["default_min_reads"]))
        )
        sample_settings["max_freq"] = float(
            sample.get("filter_max_freq", settings["default_max_freq"])
        )
        sample_settings["min_depth"] = int(
            float(sample.get("filter_min_depth", settings["default_mindepth"]))
        )
        sample_settings["max_popfreq"] = float(
            sample.get("filter_max_popfreq", settings["default_popfreq"])
        )
        sample_settings["csq_filter"] = sample.get(
            "checked_csq", settings["default_checked_conseq"]
        )
        sample_settings["min_cnv_size"] = int(
            float(sample.get("min_cnv_size", settings["default_min_cnv_size"]))
        )
        sample_settings["max_cnv_size"] = int(
            float(sample.get("max_cnv_size", settings["default_max_cnv_size"]))
        )
        return sample_settings

    @staticmethod
    def get_fusions_settings(sample, settings):
        """
        get sample fusion setting or use default

        Args:
            sample (_type_): sample string
            settings (_type_): dictionary of the default sample settings
        """
        fusion_settings = {}
        fusion_settings["min_spanreads"] = int(
            sample.get("filter_min_spanreads", settings.get("default_spanreads", 0))
        )
        fusion_settings["min_spanpairs"] = int(
            sample.get("filter_min_spanpairs", settings.get("default_spanpairs", 0))
        )
        return fusion_settings

    @staticmethod
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

    @staticmethod
    def get_active_branch_name():
        """
        Get curr checked out git branch name. Used to display version name
        in debug mode.

        Credit: https://stackoverflow.com/a/62724213
        """
        head_dir = Path(".git/HEAD")

        if not os.path.exists(head_dir):
            return "unknown branch"

        with head_dir.open("r") as f:
            content = f.read().splitlines()

            for line in content:
                if line[0:4] == "ref:":
                    return line.partition("refs/heads/")[2]

    @staticmethod
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

    @staticmethod
    def get_hg38_pos(chr: str, pos: str) -> tuple:
        """
        Function to get hg38 position
        """

        hg38 = subprocess.check_output([app.config["HG38_POS_SCRIPT"], chr, pos]).decode("utf-8")
        hg38_chr, hg38_pos = hg38.split(":")

        return hg38_chr, hg38_pos

    @staticmethod
    def get_ncbi_link(chr: str, pos: str) -> str:
        """
        Function to generate a link to NCBI genomic region
        """
        _chr = app.config["NCBI_CHR"].get("chr")
        return f'<a href="https://www.ncbi.nlm.nih.gov/nuccore/{_chr}?report=fasta&from={int(pos) - 500}&to={int(pos) + 500}">NCBI genomic region</a>'

    @staticmethod
    def get_thermo_link(chr: str, pos: str) -> str:
        """
        Function to generate a link to ThermoFisher genomic region
        """
        return f'<a href="https://www.thermofisher.com/order/genome-database/searchResults?searchMode=keyword&CID=&ICID=&productTypeSelect=ceprimer&targetTypeSelect=ceprimer_all&alternateTargetTypeSelect=&alternateProductTypeSelect=&originalCount=0&species=Homo+sapiens&otherSpecies=&additionalFilter=ceprimer-human-exome&keyword=&sequenceInput=&selectedInputType=&chromosome={chr}&chromStart={pos}&chromStop={pos}&vcfUpload=&multiChromoSome=&batchText=&batchUpload=&sequenceUpload=&multiSequence=&multiSequenceNames=&priorSearchTerms=%28NR%29">Order primers from ThermoFisher</a>'

    @staticmethod
    def nl_join(arr, joiner):
        if len(arr) == 1:
            return arr[0]
        if len(arr) == 2:
            return f"{arr[0]} {joiner} {arr[1]}"
        if len(arr) > 2:
            last = arr.pop()
            return f"{', '.join(arr)} {joiner} {last}"

    @staticmethod
    def get_sample_type(assay: str) -> str:
        if assay not in ["fusion", "fusionrna"]:
            return "dna"
        else:
            return "rna"

    @staticmethod
    def filter_non_zero_data(data) -> dict:
        """
        Remove Non Zero items
        """
        return {k: v for k, v in data.items() if v > 0}
