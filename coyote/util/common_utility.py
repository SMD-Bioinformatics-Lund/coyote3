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
from hashlib import md5
from cryptography.fernet import Fernet
import base64, json
from flask_login import current_user


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
        assay_names = CommonUtility.assay_config(
            assay_category_name.removesuffix("_restored")
        ).get("include_assays")
        if assay_category_name.endswith("_restored"):
            assay_names = [
                f"{assay_name}_restored" for assay_name in assay_names
            ]

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
    def merge_sample_settings_with_assay_config(
        sample_doc, assay_config
    ) -> dict:
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

        # Update the sample_doc with the merged filters
        sample_doc["filters"] = merged_filters
        sample_doc.pop(
            "use_diagnosis_genelist", None
        )  # Remove this key if it exists
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
            settings["error_cov"] = int(
                group.get("error_cov", settings["error_cov"])
            )
            settings["warn_cov"] = int(
                group.get("warn_cov", settings["warn_cov"])
            )
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
                group.get(
                    "default_min_cnv_size", settings["default_min_cnv_size"]
                )
            )
            settings["default_max_cnv_size"] = int(
                group.get(
                    "default_max_cnv_size", settings["default_max_cnv_size"]
                )
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
            float(
                sample.get("filter_min_reads", settings["default_min_reads"])
            )
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
            sample.get(
                "filter_min_spanreads", settings.get("default_spanreads", 0)
            )
        )
        fusion_settings["min_spanpairs"] = int(
            sample.get(
                "filter_min_spanpairs", settings.get("default_spanpairs", 0)
            )
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
        for genelist_id, genelist_values in genelist_dict.items():
            if genelist_values.get("is_active", False):
                filter_genes.extend(genelist_values["covered"])

        return list(set(filter_genes))

    @staticmethod
    def get_genes_covered_in_panel(
        genelists: dict, assay_panel_doc: dict
    ) -> dict:
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

        for genelist_id, genelist_values in genelists.items():
            genelist_genes = set(genelist_values.get("genes", []))
            # Keep only genes present in the assay panel and move the rest to a separate list
            genelist_values["covered"] = list(
                genelist_genes.intersection(covered_genes_set)
            )
            genelist_values["uncovered"] = list(
                genelist_genes.difference(covered_genes_set)
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

        hg38 = subprocess.check_output(
            [app.config["HG38_POS_SCRIPT"], chr, pos]
        ).decode("utf-8")
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
            return {
                key: CommonUtility.convert_object_id(value)
                for key, value in data.items()
            }
        elif isinstance(data, ObjectId):
            return str(data)
        else:
            return data

    @staticmethod
    def convert_to_serializable(data) -> list | dict | str | Any:
        if isinstance(data, list):
            return [
                CommonUtility.convert_to_serializable(item) for item in data
            ]
        elif isinstance(data, dict):
            return {
                key: CommonUtility.convert_to_serializable(value)
                for key, value in data.items()
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
    def get_genelist_dispnames(
        genelists: dict, filter_list: None | list
    ) -> str:
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
            display_names = [
                genelist.get("displayname") for genelist in genelists
            ]
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
        Get report header based on assay and sample data
        """
        if assay == "myeloid" and sample.get("subpanel") == "Hem-Snabb":
            if sample.get("num_samples") == 2:
                header += ": fullständig parad analys"
            else:
                header += ": preliminär oparad analys"
        return header

    @staticmethod
    def write_report(report_data: str, report_path: str) -> bool:
        """
        Write report data to a file.

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
            app.logger.error(
                f"Failed to write report to '{report_path}': {exc}"
            )
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
    def get_plot(fn: str, assay_config: dict = None) -> bool:
        """
        Check if plots should be shown in the report
        """
        plot_dir = assay_config.get("REPORT", {}).get("plots_path", "")
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

    @staticmethod
    def generate_sample_cache_key(**kwargs) -> str:
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
            elif not isinstance(
                value, (str, int, float, bool, type(None), list, dict)
            ):
                kwargs[key] = str(value)

        # Serialize to stable JSON
        raw_key = json.dumps(kwargs, sort_keys=True, separators=(",", ":"))

        # Return hashed cache key
        return f"samples:{md5(raw_key.encode()).hexdigest()}"

    @staticmethod
    def encrypt_json(data, fernet):
        json_data = json.dumps(data, default=str)  # ← handles datetime
        return fernet.encrypt(json_data.encode()).decode()

    @staticmethod
    def format_assay_config(config: dict, schema: dict) -> dict:

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
                config_filters[key] = schema["sections"]["filters"][key].get(
                    "default"
                )

        for key in report_keys:
            if key in config:
                config_report[key] = config.pop(key)
            else:
                config_report[key] = schema["sections"]["reporting"][key].get(
                    "default"
                )

        config["filters"] = config_filters
        config["reporting"] = config_report
        return config

    @staticmethod
    def format_filters_from_form(form_data, assay_config_schema: dict) -> dict:
        """
        Format filters from a WTForm (or dict) to match the schema.
        """
        # If it's a WTForm, convert it to a dict of name: data
        if hasattr(form_data, "__iter__") and not isinstance(form_data, dict):
            form_data = {field.name: field.data for field in form_data}

        print("form_data", form_data)
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
        Create a mapping of assay groups to their respective panels.
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
        Get case and control sample IDs from a sample document.
        Returns a dictionary with 'case' and 'control' keys.
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
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return fallback or {}
