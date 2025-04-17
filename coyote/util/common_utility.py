import os
from copy import deepcopy
from pathlib import Path
import subprocess
from flask import current_app as app
from typing import Any, Literal, Dict, Tuple
from bson import ObjectId
from datetime import datetime
from io import BytesIO
import base64
from datetime import timedelta


class CommonUtility:
    """
    List of util functions, mostly shared across Coyote main, rna and other blueprints.
    """

    @staticmethod
    def get_simple_id(variant):
        """
        Get a simple id for a variant
        """
        return variant.get(
            "simple_id",
            f"{str(variant['CHROM'])}_{str(variant['POS'])}_{variant['REF']}_{variant['ALT']}",
        )

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
    def get_unknown_default_parameters(grp: str = "unknown-default") -> dict:
        """
        Get group paramters data
        """
        conf = app.config.get("GROUP_CONFIGS")
        if conf is not None:
            return deepcopy(conf.get("unknown-default"))
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

    # TODO: Remove
    @staticmethod
    def get_assay_from_sample(smp) -> Any | Literal["unknown"] | None:
        conf = app.config.get("ASSAY_MAPPER")
        if conf is None:
            return None
        for assay, groups in conf.items():
            if any(g in smp["groups"] for g in groups):
                return assay
        return "unknown"

    @staticmethod
    def merge_sample_settings_with_assay_config(sample_doc, assay_config) -> dict:
        """
        Merge assay_config FILTERS into sample_doc['filters'].
        Existing sample values take priority. Missing values are filled from the assay_config.

        Args:
            sample_doc (dict): The sample document.
            assay_config (dict): The full assay config with a 'FILTERS' section.

        Returns:
            dict: Updated sample_doc with 'filters' field merged.
        """
        filters_config = assay_config.get("FILTERS", {})
        sample_filters = sample_doc.get("filters", {})

        merged_filters = {}

        for key, value in filters_config.items():
            # If the key already exists and is non-empty in the sample's filters, keep it
            if key in sample_filters and sample_filters[key]:
                merged_filters[key] = sample_filters[key]
            else:
                merged_filters[key] = value

        # If sample filters are empty, then update the sample doc with the default filters

        # Update the sample_doc with the merged filters
        sample_doc["filters"] = merged_filters
        sample_doc.pop("use_diagnosis_genelist", None)  # Remove this key if it exists
        return sample_doc

    # TODO: Remove
    @staticmethod
    def get_group_defaults(group) -> Any | None:
        """
        Return Default dict (either group defaults or coyote defaults) and setting per sample
        """
        settings = deepcopy(app.config.get("GROUP_FILTERS"))
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
    def get_sample_settings(sample, settings) -> dict:
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
    def get_fusions_settings(sample, settings) -> dict:
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
    def create_filter_genelist(genelist_dict: dict) -> list:
        """
        Create a list of genes from a dictionary of gene lists.
        Args:
            genelist_dict (dict): A dictionary where keys are gene list names and values are lists of genes.
        Returns:
            list: A list of genes.
        """

        filter_genes = []
        for name, genes in genelist_dict.items():
            filter_genes.extend(genes)

        return list(set(filter_genes))

    @staticmethod
    def create_genelists_dict(list_names: list, gene_lists: dict) -> dict:
        """
        Creates a dictionary of gene lists from a list of selected gene lists.
        Args:
            gene_lists (list): A list of gene lists.
            list_names (list): A list of gene list names.
        Returns:
            dict: A dictionary where keys are gene list names and values are lists of genes.
        """

        return {name: gene_lists[name] for name in list_names}

    @staticmethod
    def get_active_branch_name() -> str | None:
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
    def nl_num(i, gender) -> Any | str:
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

    @staticmethod
    def convert_object_id(data) -> list | dict | str | Any:
        if isinstance(data, list):
            return [CommonUtility.convert_object_id(item) for item in data]
        elif isinstance(data, dict):
            return {key: CommonUtility.convert_object_id(value) for key, value in data.items()}
        elif isinstance(data, ObjectId):
            return str(data)
        else:
            return data

    @staticmethod
    def convert_to_serializable(data) -> list | dict | str | Any:
        if isinstance(data, list):
            return [CommonUtility.convert_to_serializable(item) for item in data]
        elif isinstance(data, dict):
            return {
                key: CommonUtility.convert_to_serializable(value) for key, value in data.items()
            }
        elif isinstance(data, ObjectId):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    @staticmethod
    def dict_to_tuple(d: Dict) -> Tuple:
        """Convert a dictionary to a tuple of sorted key-value pairs."""
        return tuple(sorted(d.items()))

    @staticmethod
    def tuple_to_dict(t: Tuple) -> Dict:
        """Convert a tuple of sorted key-value pairs back to a dictionary."""
        return dict(t)

    @staticmethod
    def select_one_sample_group(sample_groups: list) -> str:
        """
        Selects the first sample group from the list of sample groups or select the first one if there is tumwgs.
        """
        ## Check the length of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
        if len(sample_groups) > 1:
            for group in sample_groups:
                if group in ["tumwgs-solid", "tumwgs-hema"]:
                    smp_grp = group
                    break
        else:
            smp_grp = sample_groups[0]
        return smp_grp

    @staticmethod
    def get_genelist_dispnames(genelists: dict, filter_list: None | list) -> str:
        """
        Get display names of genelists.

        This function extracts the display names from a list of gene lists. If a filter list is provided,
        only the gene lists whose names are in the filter list will have their display names extracted.

        Args:
            genelists (dict): A dictionary where each key is a gene list and each value is a dictionary containing gene list details, including the "displayname".
            filter_list (None | list): A list of gene list names to filter by. If None, all gene lists will be considered.

        Returns:
            list[str]: A list of display names of the gene lists.
        """
        if filter_list is None:
            display_names = [genelist.get("displayname") for genelist in genelists]
        else:
            display_names = [
                genelist.get("displayname")
                for genelist in genelists
                if genelist.get("name") in filter_list
            ]
        return display_names

    @staticmethod
    def get_report_header(assay: str, sample: dict):
        """
        Get report header based on assay and sample data
        """
        header = (
            app.config.get("REPORT_CONFIG", {})
            .get("REPORT_HEADERS", {})
            .get(assay, "Unknown assay")
        )
        if assay == "myeloid" and sample.get("subpanel") == "Hem-Snabb":
            if sample.get("num_samples") == 2:
                header += ": fullständig parad analys"
            else:
                header += ": preliminär oparad analys"
        return header

    @staticmethod
    def get_analysis_method(assay: str):
        """
        Get analysis method based on assay
        """
        method = app.config.get("REPORT_CONFIG", {}).get("ANALYSIS_METHODS", {}).get(assay, "")
        return method

    @staticmethod
    def check_report_exists(report_path: str) -> bool:
        """
        Check if report path exists
        """
        return os.path.exists(report_path)

    @staticmethod
    def write_report(report_data: str, report_path: str) -> bool:
        """
        Write report data to a file
        """
        try:
            with open(report_path, "w") as report_file:
                report_file.write(report_data)
            return True
        except Exception as e:
            app.logger.error(f"Error writing report to file: {e}")
            return False

    @staticmethod
    def get_base64_image(image_path: str) -> str:
        """
        Get base64 encoded image
        """
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        return base64_image

    @staticmethod
    def get_plot(fn: str, assay: str, build: str = "38") -> bool:
        """
        Check if plots should be shown in the report
        """
        plot_dir = app.config.get("REPORT_CONFIG", {}).get("REPORT_PLOTS_PATH", {}).get(assay, "")
        if plot_dir and fn:
            image_path = os.path.join(plot_dir, f"{fn}")
            return CommonUtility.get_base64_image(image_path)
        return False

    @staticmethod
    def get_date_today() -> str:
        """
        Get today's date
        """
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_date_days_ago(days: int) -> str:
        """
        Get date a specified number of days ago
        """
        return datetime.now() - timedelta(days=days)
