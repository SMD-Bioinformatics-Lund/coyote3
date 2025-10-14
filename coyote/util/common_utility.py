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
Coyote3 Common Utility
===============================
This file contains utility functions and helper methods for common operations
used throughout the Coyote3 project, including configuration handling,
data formatting, serialization, and reporting.
"""

import os
from copy import deepcopy
from pathlib import Path
import subprocess

from cryptography.fernet import Fernet
from flask import current_app as app
from typing import Any, Literal, Dict, Tuple
from bson import ObjectId
from datetime import datetime
from datetime import timedelta
from hashlib import md5
import base64, json
from flask_login import current_user


class CommonUtility:
    """
    Collection of utility functions and helper methods for common operations
    used throughout the Coyote3 project. These utilities include configuration
    handling, data formatting, serialization, reporting, and other shared logic
    across Coyote main, RNA, and other blueprints.
    """

    @staticmethod
    def get_simple_id(variant: dict) -> str:
        """
        Generate a simple identifier for a variant.

        This method returns a simple string identifier for a variant dictionary. If the variant contains
        a "simple_id" key, its value is returned. Otherwise, the identifier is constructed using the
        "CHROM", "POS", "REF", and "ALT" fields in the format: "{CHROM}_{POS}_{REF}_{ALT}".

        Args:
            variant (dict): A dictionary representing a variant, expected to contain at least the keys
                "CHROM", "POS", "REF", and "ALT".

        Returns:
            str: The simple identifier for the variant.
        """
        return variant.get(
            "simple_id",
            f"{str(variant['CHROM'])}_{str(variant['POS'])}_{variant['REF']}_{variant['ALT']}",
        )

    @staticmethod
    def assay_config(assay_name: str = None) -> dict:
        """
        Retrieve assay configuration data from the application config.

        If `assay_name` is provided, returns the configuration for that specific assay.
        If not provided, returns the entire assays configuration dictionary.

        Args:
            assay_name (str, optional): The name of the assay to retrieve configuration for.

        Returns:
            dict: The configuration dictionary for the specified assay, or all assays if no name is given.
        """
        conf = app.config.get("ASSAYS")
        if conf is None:
            return {}

        if assay_name is not None:
            conf = conf.get(assay_name)

        return deepcopy(conf)

    @staticmethod
    def get_group_parameters(group: str) -> dict:
        """
        Retrieve configuration parameters for a specific group.

        Args:
            group (str): The name of the group to retrieve parameters for.

        Returns:
            dict: A deep copy of the group's configuration parameters if found, otherwise an empty dictionary.
        """
        conf = app.config.get("GROUP_CONFIGS")
        if conf is not None:
            return deepcopy(conf.get(group))
        return {}

    @staticmethod
    def table_config() -> dict:
        """
        Retrieve the table configuration from the application config.

        Returns:
            dict: A deep copy of the table configuration dictionary, or None if not set.
        """
        conf = app.config.get("TABLE")
        return deepcopy(conf)

    @staticmethod
    def cutoff_config(assay_name: str, sample_type: str = None) -> dict:
        """
        Retrieve cutoff configuration for a given assay and optional sample type.

        This method fetches the cutoff values from the application configuration for the specified
        assay. If a sample type is provided, it returns the cutoffs specific to that sample type.
        If no cutoffs are defined for the assay or sample type, an empty dictionary is returned.

        Args:
            assay_name (str): The name of the assay to retrieve cutoffs for.
            sample_type (str, optional): The sample type to retrieve cutoffs for.

        Returns:
            dict: The cutoff configuration for the specified assay and sample type, or an empty dict if not found.
        """
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
    def assay_info_vars(assay_name: str) -> list:
        """
        Retrieve the list of sample information variables for a given assay.

        Args:
            assay_name (str): The name of the assay to retrieve information variables for.

        Returns:
            list: A list of sample information variable names defined in the assay configuration, or None if not found.
        """
        assay = CommonUtility.assay_config(assay_name)
        return assay.get("sample_info")

    @staticmethod
    def assay_qc_vars(assay_name: str) -> list:
        """
        Retrieve the list of sample quality control (QC) variable names for a given assay.

        Args:
            assay_name (str): The name of the assay to retrieve QC variable names for.

        Returns:
            list: A list of QC variable names defined in the assay configuration, or None if not found.
        """
        assay = CommonUtility.assay_config(assay_name)
        return assay.get("sample_qc")

    @staticmethod
    def assays_in_assay_group(assay_name: str) -> list:
        """
        Retrieve the list of assays included in a given assay group.

        Args:
            assay_name (str): The name of the assay group to retrieve included assays for.

        Returns:
            list: A list of assay names included in the specified assay group, or None if not found.
        """
        return CommonUtility.assay_config(assay_name).get("include_assays")

    @staticmethod
    def has_subtypes(assay_name: str) -> bool:
        """
        Check if the given assay has subtypes defined in its configuration.

        Args:
            assay_name (str): The name of the assay to check.

        Returns:
            bool: True if the assay has subtypes, False otherwise.
        """
        assay_conf = CommonUtility.assay_config(assay_name)
        return "subtypes" in assay_conf

    @staticmethod
    def get_sample_subtypes(assay_name: str) -> list:
        """
        Get the list of available subtypes for a given assay as defined in the assay configuration.

        Args:
            assay_name (str): The name of the assay to retrieve subtypes for.

        Returns:
            list: A list of subtype names if defined, otherwise None.
        """
        assay = CommonUtility.assay_config(assay_name)
        subtypes = assay.get("subtypes", {})
        subtypes = subtypes.get("subtype_names", None)
        return subtypes

    @staticmethod
    def subtype_id_var(assay_name: str) -> list:
        """
        Retrieve the subtype ID column(s) for a given assay.

        This method checks if the specified assay has subtypes defined in its configuration.
        If subtypes are enabled, it returns the value of the "subtype_id_col" key from the assay configuration.
        If subtypes are not enabled, it returns None.
        If "subtype_id_col" is missing when subtypes are enabled, an AttributeError is raised.

        Args:
            assay_name (str): The name of the assay to retrieve the subtype ID column(s) for.

        Returns:
            list: The subtype ID column(s) if defined, otherwise None.

        Raises:
            AttributeError: If subtypes are enabled but "subtype_id_col" is not defined in the assay configuration.
        """
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
        """
        Check if the given assay is defined in the configuration.

        Args:
            assay_name (str): The name of the assay to check.

        Returns:
            bool: True if the assay is defined in the configuration, False otherwise.
        """
        conf = CommonUtility.assay_config()
        return assay_name in conf

    @staticmethod
    def assay_names_for_db_query(assay_category_name: str) -> list:
        """
        Retrieve the list of assay names for a given assay category, handling restored categories.

        If the category name ends with "_restored", appends "_restored" to each included assay name.
        Otherwise, returns the list of included assays as defined in the configuration.

        Args:
            assay_category_name (str): The name of the assay category to query.

        Returns:
            list: A list of assay names for database queries, possibly with "_restored" suffixes.
        """
        # Ignore _restored
        assay_names = CommonUtility.assay_config(assay_category_name.removesuffix("_restored")).get(
            "include_assays"
        )
        if assay_category_name.endswith("_restored"):
            assay_names = [f"{assay_name}_restored" for assay_name in assay_names]

        return assay_names

    @staticmethod
    def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config: dict) -> dict:
        """
        Merge assay_config FILTERS into sample_doc['filters'].
        Existing sample values take priority. Missing values are filled from the assay_config.

        Args:
            sample_doc (dict): The sample document.
            assay_config (dict): The full assay config with a 'FILTERS' section.

        Returns:
            dict: Updated sample_doc with 'filters' field merged.
        """
        filters_config = assay_config.get("filters", {})
        sample_filters = sample_doc.get("filters", {})
        adhoc_genes = sample_filters.pop("adhoc_genes", {})

        # If sample filters are empty, then update the sample doc with the default filters
        if not sample_filters:
            merged_filters = deepcopy(filters_config)
        else:
            # If sample filters are not empty, then merge the default filters with the sample filters
            merged_filters = {}

            for key, value in filters_config.items():
                # If the key already exists and is non-empty in the sample's filters, keep it
                if key in sample_filters and sample_filters[key]:
                    merged_filters[key] = sample_filters[key]
                else:
                    merged_filters[key] = value

        if adhoc_genes:
            merged_filters["adhoc_genes"] = adhoc_genes

        # Update the sample_doc with the merged filters
        sample_doc["filters"] = merged_filters
        sample_doc.pop("use_diagnosis_genelist", None)  # Remove this key if it exists
        return sample_doc

    @staticmethod
    def get_fusions_settings(sample: dict, settings: dict) -> dict:
        """
        Get sample fusion settings or use default values.

        This method retrieves fusion-related filter settings for a sample, using values from the sample if present,
        or falling back to the provided default settings.

        Args:
            sample (dict): The sample dictionary containing possible fusion filter settings.
            settings (dict): The default settings to use if sample-specific values are missing.

        Returns:
            dict: A dictionary with fusion filter settings applied.
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
        Create a list of unique genes from a dictionary of gene lists.

        Iterates through the provided `genelist_dict`, collecting all genes from the
        "covered" field of each active gene list (where "is_active" is True), and returns
        a deduplicated list of these genes.

        Args:
            genelist_dict (dict): A dictionary where keys are gene list names and values are
                dictionaries containing gene list details, including "is_active" (bool) and
                "covered" (list of genes).

        Returns:
            list: A list of unique genes from all active gene lists.
        """

        filter_genes = []
        for genelist_id, genelist_values in genelist_dict.items():
            if genelist_values.get("is_active", False):
                filter_genes.extend(genelist_values["covered"])

        return list(set(filter_genes))

    @staticmethod
    def get_genes_covered_in_panel(genelists: dict, assay_panel_doc: dict) -> dict:
        """
        Filters the input gene lists to include only genes covered by the specified assay panel.

        Args:
            genelists (list[dict]):
                A list of dictionaries, each containing a "genes" key with a list of gene names.
            assay_panel_doc (dict):
                A dictionary representing the assay panel document, which contains a "covered_genes" key with a list of gene names.

        Returns:
            list[dict]:
                A list of dictionaries in the same format as `genelists`, but with the "genes" lists filtered to include only those genes present in the assay panel.

            covered_genelists = get_genes_covered_in_panel(genelists, assay_panel_doc)
            # covered_genelists: [{"genes": ["BRCA1", "EGFR"]}, {"genes": ["KRAS"]}]
        """
        # Flatten all genes from the genelists into a set
        covered_genes_set = set(assay_panel_doc.get("covered_genes", []))
        updated_genelists = {}
        asp_family = assay_panel_doc.get("asp_family", "").lower()

        for genelist_id, genelist_values in genelists.items():
            genelist_genes = set(genelist_values.get("genes", []))
            # For WSG and WTS, keep all genes in the genelist, marking which are covered and which are not
            if asp_family in ["wgs", "wts"]:
                genelist_values["covered"] = sorted(genelist_genes)
                genelist_values["uncovered"] = []
            else:
                # Keep only genes present in the assay panel and move the rest to a separate list
                genelist_values["covered"] = sorted(
                    list(genelist_genes.intersection(covered_genes_set))
                )
                genelist_values["uncovered"] = sorted(
                    list(genelist_genes.difference(covered_genes_set))
                )
            updated_genelists[genelist_id] = genelist_values

        return updated_genelists

    @staticmethod
    def get_assay_genelist_names(genelists: dict) -> list:
        """
        Get the names of the gene lists for a specific assay.

        Args:
            genelists (dict): A dictionary where keys are gene list names and values are lists of genes.

        Returns:
            list: A list of gene list names.
        """
        return [genelist["_id"] for genelist in genelists]

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
    def nl_num(i: int, gender: str) -> Any | str:
        """
        Return the Swedish word for a number, optionally using the neuter form for 'one'.

        Args:
            i (int): The number to convert (0-12 returns Swedish word, otherwise returns the number as string).
            gender (str): If 't', use the neuter form for 'one' ("ett"), otherwise use the common form ("en").

        Returns:
            str: The Swedish word for the number if 0-12, otherwise the number as a string.
        """
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
        Get the hg38 genomic position for a given chromosome and position.

        This function calls an external script (specified in the application config as HG38_POS_SCRIPT)
        with the provided chromosome and position as arguments. It returns the chromosome and position
        in hg38 coordinates as a tuple.

        Args:
            chr (str): The chromosome identifier (e.g., 'chr1', '1').
            pos (str): The position on the chromosome.

        Returns:
            tuple: A tuple containing the hg38 chromosome and position as strings.
        """

        hg38 = subprocess.check_output([app.config["HG38_POS_SCRIPT"], chr, pos]).decode("utf-8")
        hg38_chr, hg38_pos = hg38.split(":")

        return hg38_chr, hg38_pos

    @staticmethod
    def get_ncbi_link(chr: str, pos: str) -> str:
        """
        Generate an HTML link to the NCBI genomic region for a given chromosome and position.

        Returns a hyperlink to the NCBI nuccore page, displaying the genomic region
        centered at the specified position (±500 bases).

        Returns:
            str: HTML anchor tag linking to the NCBI genomic region.
        """
        _chr = app.config["NCBI_CHR"].get(chr)
        return f'<a href="https://www.ncbi.nlm.nih.gov/nuccore/{_chr}?report=fasta&from={int(pos) - 500}&to={int(pos) + 500}">NCBI genomic region</a>'

    @staticmethod
    def get_thermo_link(chr: str, pos: str) -> str:
        """
        Generate an HTML link to the ThermoFisher genomic region for a given chromosome and position.

        Args:
            chr (str): The chromosome identifier.
            pos (str): The position on the chromosome.

        Returns:
            str: HTML anchor tag linking to the ThermoFisher genomic region for ordering primers.
        """
        return f'<a href="https://www.thermofisher.com/order/genome-database/searchResults?searchMode=keyword&CID=&ICID=&productTypeSelect=ceprimer&targetTypeSelect=ceprimer_all&alternateTargetTypeSelect=&alternateProductTypeSelect=&originalCount=0&species=Homo+sapiens&otherSpecies=&additionalFilter=ceprimer-human-exome&keyword=&sequenceInput=&selectedInputType=&chromosome={chr}&chromStart={pos}&chromStop={pos}&vcfUpload=&multiChromoSome=&batchText=&batchUpload=&sequenceUpload=&multiSequence=&multiSequenceNames=&priorSearchTerms=%28NR%29">Order primers from ThermoFisher</a>'

    @staticmethod
    def nl_join(arr: list, joiner: str) -> str:
        """
        Join a list of strings in a natural language style using the given joiner.

        Args:
            arr (list): List of strings to join.
            joiner (str): The word to use as the conjunction (e.g., "and", "or").

        Returns:
            str: The joined string in natural language format.
        """
        if len(arr) == 1:
            return arr[0]
        if len(arr) == 2:
            return f"{arr[0]} {joiner} {arr[1]}"
        if len(arr) > 2:
            last = arr.pop()
            return f"{', '.join(arr)} {joiner} {last}"

    @staticmethod
    def get_sample_type(assay: str) -> str:
        """
        Returns the sample type as a string based on the assay name.

        If the assay is not "fusion" or "fusionrna", returns "dna".
        Otherwise, returns "rna".

        Args:
            assay (str): The name of the assay.

        Returns:
            str: "dna" if the assay is not a fusion assay, otherwise "rna".
        """
        if assay not in ["fusion", "fusionrna"]:
            return "dna"
        else:
            return "rna"

    @staticmethod
    def filter_non_zero_data(data: dict) -> dict:
        """
        Remove items from the dictionary where the value is not greater than zero.

        Returns a new dictionary containing only the items with values greater than zero.

        Args:
            data (dict): The input dictionary to filter.

        Returns:
            dict: A dictionary with only items where the value is greater than zero.
        """
        return {k: v for k, v in data.items() if v > 0}

    @staticmethod
    def convert_object_id(data: Any) -> list | dict | str | Any:
        """
        Recursively convert all `ObjectId` instances in a list or dictionary to their string representation.

        Args:
            data (list | dict | ObjectId | Any): The input data structure to process.

        Returns:
            list | dict | str | Any: The data structure with all `ObjectId` instances converted to strings.
        """
        if isinstance(data, list):
            return [CommonUtility.convert_object_id(item) for item in data]
        elif isinstance(data, dict):
            return {key: CommonUtility.convert_object_id(value) for key, value in data.items()}
        elif isinstance(data, ObjectId):
            return str(data)
        else:
            return data

    @staticmethod
    def convert_to_serializable(data: Any) -> list | dict | str | Any:
        """
        Recursively convert data to a JSON-serializable format.

        This method traverses lists and dictionaries, converting any `ObjectId` to a string
        and any `datetime` object to its ISO 8601 string representation. Other types are returned as-is.

        Returns:
            list | dict | str | Any: The input data structure with all `ObjectId` and `datetime` instances converted to serializable strings.
        """
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
        """
        Convert a dictionary to a tuple of sorted key-value pairs.

        This method takes a dictionary and returns a tuple containing its key-value pairs,
        sorted by key. This is useful for creating hashable representations of dictionaries,
        such as for use as cache keys or in sets.

        Args:
            d (dict): The dictionary to convert.

        Returns:
            tuple: A tuple of (key, value) pairs sorted by key.
        """
        return tuple(sorted(d.items()))

    @staticmethod
    def tuple_to_dict(t: Tuple) -> Dict:
        """Convert a tuple of sorted key-value pairs back to a dictionary.

        Args:
            t (Tuple): A tuple of (key, value) pairs, typically produced by dict_to_tuple.

        Returns:
            dict: The reconstructed dictionary from the tuple of pairs.
        """
        return dict(t)

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
    def get_report_header(assay: str, sample: dict, header: str) -> str:
        """
        Get the report header string based on the assay type and sample data.

        If the assay is "myeloid" and the sample's "subpanel" is "Hem-Snabb", the header is modified:
        - If "sample_no" is 2, appends ": fullständig parad analys" (full paired analysis).
        - Otherwise, appends ": preliminär oparad analys" (preliminary unpaired analysis).

        Args:
            assay (str): The assay name.
            sample (dict): The sample data dictionary.
            header (str): The initial header string.

        Returns:
            str: The formatted report header.
        """
        if assay == "myeloid" and sample.get("subpanel") == "Hem-Snabb":
            if sample.get("sample_no") == 2:
                header += ": fullständig parad analys"
            else:
                header += ": preliminär oparad analys"
        return header

    @staticmethod
    def write_report(report_data: str, report_path: str) -> bool:
        """
        Write report data to a file.

        Writes the provided `report_data` string to the file specified by `report_path`.
        Creates any necessary parent directories if they do not exist.

        Args:
            report_data (str): The content to write to the file.
            report_path (str): The path where the report will be saved.

        Returns:
            bool: True if the report was written successfully, False otherwise.
        """
        try:
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as report_file:
                report_file.write(report_data)
            return True
        except Exception as exc:
            app.logger.error(f"Failed to write report to '{report_path}': {exc}")
            return False

    @staticmethod
    def get_base64_image(image_path: str) -> str:
        """
        Get a base64-encoded string representation of an image file.

        Args:
            image_path (str): The file path to the image.

        Returns:
            str: The base64-encoded string of the image content.
        """
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        return base64_image

    @staticmethod
    def get_plot(fn: str, assay_config: dict = None) -> bool:
        """
        Check if plots should be shown in the report.

        This method determines whether plots should be included in the report based on the provided
        assay configuration and file name. If a valid plot directory and file name are given, it
        returns the base64-encoded image content; otherwise, it returns False.

        Args:
            fn (str): The file name of the plot image.
            assay_config (dict, optional): The assay configuration dictionary, expected to contain
                a 'REPORT' section with a 'plots_path' key.

        Returns:
            str | bool: The base64-encoded image string if the plot exists, otherwise False.
        """
        plot_dir = assay_config.get("REPORT", {}).get("plots_path", "")
        if plot_dir and fn:
            image_path = os.path.join(plot_dir, f"{fn}")
            return CommonUtility.get_base64_image(image_path)
        return False

    @staticmethod
    def get_date_today() -> str:
        """
        Get today's date as a string in YYYY-MM-DD format.

        Returns:
            str: The current date in ISO format (YYYY-MM-DD).
        """
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_date_days_ago(days: int) -> str:
        """
        Get the date a specified number of days ago as a string in YYYY-MM-DD format.

        Args:
            days (int): The number of days to subtract from today.

        Returns:
            str: The date in ISO format (YYYY-MM-DD) for the specified days ago.
        """
        return datetime.now() - timedelta(days=days)

    @staticmethod
    def generate_sample_cache_key(**kwargs) -> str:
        """
        Generate a stable cache key for sample data.

        This method creates a unique, stable cache key string based on the provided keyword arguments.
        It removes internal-use keys (such as 'self' and 'use_cache'), sorts any list of user groups,
        normalizes datetime values to date strings, and serializes the arguments to a JSON string.
        The resulting string is hashed using MD5 and prefixed with 'samples:'.

        Returns:
            str: A stable cache key for the sample data.
        """
        # Remove unneeded internal keys if present (e.g., 'self')
        kwargs.pop("self", None)
        kwargs.pop("use_cache", None)

        # Normalize lists (e.g., user_groups)
        if "user_groups" in kwargs and isinstance(kwargs["user_groups"], list):
            kwargs["user_groups"] = sorted(kwargs["user_groups"])

        from datetime import datetime

        for key, value in kwargs.items():
            if isinstance(value, datetime):
                # Truncate to just the date
                kwargs[key] = value.date().isoformat()
            elif not isinstance(value, (str, int, float, bool, type(None), list, dict)):
                kwargs[key] = str(value)

        # Serialize to stable JSON
        raw_key = json.dumps(kwargs, sort_keys=True, separators=(",", ":"))

        # Return hashed cache key
        return f"samples:{md5(raw_key.encode()).hexdigest()}"

    @staticmethod
    def encrypt_json(data: dict, fernet: Fernet) -> str:
        """
        Encrypt a JSON-serializable dictionary using the provided Fernet key.

        Args:
            data (dict): The dictionary to encrypt. Must be JSON-serializable.
            fernet (Fernet): The Fernet encryption object used to encrypt the data.

        Returns:
            str: The encrypted string representation of the JSON data.
        """
        json_data = json.dumps(data, default=str)  # ← handles datetime
        return fernet.encrypt(json_data.encode()).decode()

    @staticmethod
    def format_assay_config(config: dict, schema: dict) -> dict:
        """
        Format the assay configuration dictionary to match the provided schema.

        This method restructures the `config` dictionary so that its keys and default values
        align with the sections and fields defined in the `schema` dictionary. It separates
        filter and reporting keys into their respective sub-dictionaries, using defaults from
        the schema if a key is missing in the config.

        Args:
            config (dict): The assay configuration dictionary to format.
            schema (dict): The schema dictionary defining expected sections and default values.

        Returns:
            dict: The formatted assay configuration dictionary matching the schema structure.
        """
        if config is None:
            config = {}
        if schema is None:
            schema = {}
        filter_keys = schema.get("sections", {}).get("filters", [])
        report_keys = schema.get("sections", {}).get("reporting", [])

        config_filters = {}
        config_report = {}
        for key in filter_keys:
            if key in config:
                config_filters[key] = config.pop(key)
            else:
                config_filters[key] = schema["sections"]["filters"][key].get("default")

        for key in report_keys:
            if key in config:
                config_report[key] = config.pop(key)
            else:
                config_report[key] = schema["sections"]["reporting"][key].get("default")

        config["filters"] = config_filters
        config["reporting"] = config_report
        return config

    @staticmethod
    def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
        """
        Format filters from a WTForm (or dict) to match the schema.

        This function takes filter data from a WTForm or a dictionary and formats it to match the expected
        structure defined by the provided assay configuration schema. It extracts filter fields, groups
        prefixed fields (such as vep consequences, genelists, fusionlists, etc.) into lists, and returns
        a dictionary of filters that aligns with the schema.

        Args:
            form_data: The WTForm or dictionary containing filter data.
            assay_config_schema (dict): The schema dictionary defining filter sections and expected fields.

        Returns:
            dict: A dictionary of filters formatted according to the schema.
        """
        # If it's a WTForm, convert it to a dict of name: data
        if hasattr(form_data, "__iter__") and not isinstance(form_data, dict):
            form_data = {field.name: field.data for field in form_data}

        fields = assay_config_schema.get("sections", {}).get("filters", [])

        filters = {}
        (
            vep_consequences,
            genelists,
            fusionlists,
            fusion_callers,
            fusioneffects,
            cnveffects,
        ) = ([], [], [], [], [], [])

        prefix_map = {
            "vep_": vep_consequences,
            "genelist_": genelists,
            "fusionlist_": fusionlists,
            "fusioncaller_": fusion_callers,
            "fusioneffect_": fusioneffects,
            "cnveffect_": cnveffects,
        }

        for k, v in form_data.items():
            for prefix, target_list in prefix_map.items():
                if isinstance(k, str) and k.startswith(prefix) and v:
                    target_list.append(k.replace(prefix, ""))
                    break

        for _field in fields:
            if _field == "vep_consequences":
                filters["vep_consequences"] = vep_consequences
            elif _field == "genelists":
                filters["genelists"] = genelists
            elif _field == "fusionlists":
                filters["fusionlists"] = fusionlists
            elif _field == "fusion_callers":
                filters["fusion_callers"] = fusion_callers
            elif _field == "fusioneffects":
                filters["fusioneffects"] = fusioneffects
            elif _field == "cnveffects":
                filters["cnveffects"] = cnveffects
            else:
                filters[_field] = form_data.get(_field)

        return filters

    @staticmethod
    def create_assay_group_map(assay_groups_panels: list) -> dict:
        """
        Create a dictionary mapping each assay group to a list of its associated asp.

        Args:
            assay_groups_panels (list): A list of dictionaries, each representing an assay panel with keys such as
                "asp_group", "assay_name", "display_name", and "asp_category".

        Returns:
            dict: A dictionary where each key is an assay group name and the value is a list of panel dictionaries
            containing "assay_name", "display_name", and "asp_category".
        """
        assay_group_map = {}

        for _assay in assay_groups_panels:
            group = _assay.get("asp_group")
            if group not in assay_group_map:
                assay_group_map[group] = []

            group_map = {}
            group_map["assay_name"] = _assay.get("assay_name")
            group_map["display_name"] = _assay.get("display_name")
            group_map["asp_category"] = _assay.get("asp_category")
            assay_group_map[group].append(group_map)

        return assay_group_map

    @staticmethod
    def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
        """
        Retrieve case and control sample IDs from a sample document.

        This method extracts the 'case_id' and 'control_id' fields from the provided sample document
        and returns them in a dictionary with the keys 'case' and 'control'. If either field is missing,
        it will be omitted from the result.

        Args:
            sample_doc (dict): The sample document containing possible 'case_id' and 'control_id' fields.

        Returns:
            dict: A dictionary with 'case' and/or 'control' keys mapped to their respective IDs.
        """
        sample_ids = {}
        case = sample_doc.get("case_id")
        control = sample_doc.get("control_id")
        if case:
            sample_ids["case"] = case
        if control:
            sample_ids["control"] = control

        return sample_ids

    @staticmethod
    def create_classified_variant_doc(
        variant: str,
        nomenclature: str,
        class_num: int,
        variant_data: dict,
        **kwargs,
    ) -> Any:
        """
        Insert a classified variant into the database.

        This method creates a document representing a classified variant and inserts it into the MongoDB collection.
        The document includes details such as the variant, nomenclature, classification, assay, subpanel, and additional
        metadata like the author and creation time.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            class_num (int): The classification number assigned to the variant.
            variant_data (dict): A dictionary containing additional variant details, such as:
                - assay_group (str): The assay type (e.g., 'solid').
                - subpanel (str): The subpanel identifier.
                - gene (str): The gene symbol (if applicable).
                - transcript (str): The transcript identifier (if applicable).
                - gene1 (str): The first gene symbol (if nomenclature is 'f').
                - gene2 (str): The second gene symbol (if nomenclature is 'f').
            **kwargs: Additional optional arguments, such as:
                - text (str): A textual comment or description for the variant.

        Returns:
            Any: The result of the insert operation, which may include the inserted document ID or other relevant information.
        """
        document = {
            "author": current_user.username,
            "time_created": datetime.now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "assay": variant_data.get("assay_group", None),
            "subpanel": variant_data.get("subpanel", None),
        }

        if "text" in kwargs:
            document["text"] = kwargs["text"]
        else:
            document["class"] = class_num

        if nomenclature != "f":
            document["gene"] = variant_data.get("gene", None)
            document["transcript"] = variant_data.get("transcript", None)
        else:
            document["gene1"] = variant_data.get("gene1", None)
            document["gene2"] = variant_data.get("gene2", None)

        return document

    @staticmethod
    def safe_json_load(data: Any, fallback=None) -> dict:
        """
        Safely load JSON data from a string.

        Attempts to parse the input `data` as JSON and return the resulting dictionary.
        If parsing fails due to a `JSONDecodeError`, returns the provided `fallback` dictionary,
        or an empty dictionary if no fallback is specified.

        Args:
            data (Any): The JSON string to parse.
            fallback (dict, optional): The dictionary to return if parsing fails. Defaults to None.

        Returns:
            dict: The parsed JSON dictionary, or the fallback/empty dictionary on failure.
        """
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return fallback or {}

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
    def get_sample_effective_genes(sample: dict, asp_doc: dict, checked_gl_dict: dict) -> tuple:
        """
        Return effective gene lists for a sample and its assay panel.

        This function resolves the sample's selected genelists (from sample["filters"]["genelists"])
        via store.isgl_handler.get_isgl_by_ids, appends any adhoc_genes defined in the sample filters,
        and computes which genes are covered by the provided assay panel using
        CommonUtility.get_genes_covered_in_panel. A deduplicated list of effective genes is produced
        using CommonUtility.create_filter_genelist.

        Args:
            sample (dict): Sample document containing 'filters' with optional 'genelists' and 'adhoc_genes'.
            asp_doc (dict): Assay panel document containing a 'covered_genes' list.

        Returns:
            tuple[list[dict], list[str]]: A tuple (covered_genelists, effective_filter_genes) where:
                - covered_genelists: list of genelist dicts augmented with 'covered' and 'uncovered' keys.
                - effective_filter_genes: deduplicated list of gene symbols to use for filtering.
        """
        sample_filters = sample.get("filters", {})

        # Add AdHoc Genes which are a part of sample settings and not ASP or ASPC
        adhoc_genes = sample_filters.get("adhoc_genes", {}).get("genes", {})
        adhoc_key = sample_filters.get("adhoc_genes", {}).get("label", "AdHoc genes")
        if adhoc_genes:
            checked_gl_dict[adhoc_key] = {
                "displayname": adhoc_key,
                "is_active": True,
                "genes": adhoc_genes,
                "adhoc": True,
            }

        genes_covered_in_panel: dict = CommonUtility.get_genes_covered_in_panel(
            checked_gl_dict, asp_doc
        )

        effective_filter_genes = CommonUtility.create_filter_genelist(genes_covered_in_panel)

        return genes_covered_in_panel, effective_filter_genes
