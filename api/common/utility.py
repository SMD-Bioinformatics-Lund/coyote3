"""
Coyote3 Common Utility
===============================
This file contains utility functions and helper methods for common operations
used throughout the Coyote3 project, including configuration handling,
data formatting, serialization, and reporting.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, Tuple

from werkzeug.security import generate_password_hash

from api.common.assay_filters import (
    assay_config as _assay_config,
)
from api.common.assay_filters import (
    assay_exists as _assay_exists,
)
from api.common.assay_filters import (
    assay_info_vars as _assay_info_vars,
)
from api.common.assay_filters import (
    assay_names_for_db_query as _assay_names_for_db_query,
)
from api.common.assay_filters import (
    assay_qc_vars as _assay_qc_vars,
)
from api.common.assay_filters import (
    assays_in_assay_group as _assays_in_assay_group,
)
from api.common.assay_filters import (
    create_assay_group_map as _create_assay_group_map,
)
from api.common.assay_filters import (
    create_filter_genelist as _create_filter_genelist,
)
from api.common.assay_filters import (
    cutoff_config as _cutoff_config,
)
from api.common.assay_filters import (
    format_assay_config as _format_assay_config,
)
from api.common.assay_filters import (
    format_filters_from_form as _format_filters_from_form,
)
from api.common.assay_filters import (
    get_assay_genelist_names as _get_assay_genelist_names,
)
from api.common.assay_filters import (
    get_case_and_control_sample_ids as _get_case_and_control_sample_ids,
)
from api.common.assay_filters import (
    get_fusions_settings as _get_fusions_settings,
)
from api.common.assay_filters import (
    get_genes_covered_in_panel as _get_genes_covered_in_panel,
)
from api.common.assay_filters import (
    get_group_parameters as _get_group_parameters,
)
from api.common.assay_filters import (
    get_sample_effective_genes as _get_sample_effective_genes,
)
from api.common.assay_filters import (
    get_sample_subtypes as _get_sample_subtypes,
)
from api.common.assay_filters import (
    has_subtypes as _has_subtypes,
)
from api.common.assay_filters import (
    merge_sample_settings_with_assay_config as _merge_sample_settings_with_assay_config,
)
from api.common.assay_filters import (
    subtype_id_var as _subtype_id_var,
)
from api.common.assay_filters import (
    table_config as _table_config,
)
from api.common.serialization import (
    convert_object_id as _convert_object_id,
)
from api.common.serialization import (
    convert_to_serializable as _convert_to_serializable,
)
from api.common.serialization import (
    dict_to_tuple as _dict_to_tuple,
)
from api.common.serialization import (
    safe_json_load as _safe_json_load,
)
from api.common.serialization import (
    tuple_to_dict as _tuple_to_dict,
)
from api.core.dna.variant_identity import (
    build_simple_id,
    normalize_simple_id,
)
from api.runtime_state import app, current_username


class CommonUtility:
    """
    Collection of utility functions and helper methods for common operations
    used throughout the Coyote3 project. These utilities include configuration
    handling, data formatting, serialization, reporting, and other shared logic
    across Coyote main, RNA, and other blueprints.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Generate a secure password hash using PBKDF2-HMAC-SHA256.

        Args:
            password (str): The plaintext password to hash.

        Returns:
            str: A salted, iterated password hash string suitable for storing
                 in the database. The generated format typically looks like:
                 'pbkdf2:sha256:<iterations>$<salt>$<hash>'.

        Notes:
            - PBKDF2 with SHA-256 is a strong, industry-standard key derivation
              function that helps protect stored passwords against brute-force attacks.
            - `generate_password_hash` automatically generates a random salt and
              encodes the parameters inside the final hash string.
        """
        return generate_password_hash(password, method="pbkdf2:sha256")

    @staticmethod
    def utc_now():
        """
        Get the current UTC datetime.
        """
        return datetime.now(timezone.utc)

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
        existing = variant.get("simple_id")
        if existing:
            return normalize_simple_id(existing)
        return build_simple_id(
            variant.get("CHROM"),
            variant.get("POS"),
            variant.get("REF"),
            variant.get("ALT"),
        )

    @staticmethod
    def assay_config(assay_name: str = None) -> dict:
        return _assay_config(assay_name)

    @staticmethod
    def get_group_parameters(group: str) -> dict:
        return _get_group_parameters(group)

    @staticmethod
    def table_config() -> dict:
        return _table_config()

    @staticmethod
    def cutoff_config(assay_name: str, sample_type: str = None) -> dict:
        return _cutoff_config(assay_name, sample_type)

    @staticmethod
    def assay_info_vars(assay_name: str) -> list:
        return _assay_info_vars(assay_name)

    @staticmethod
    def assay_qc_vars(assay_name: str) -> list:
        return _assay_qc_vars(assay_name)

    @staticmethod
    def assays_in_assay_group(assay_name: str) -> list:
        return _assays_in_assay_group(assay_name)

    @staticmethod
    def has_subtypes(assay_name: str) -> bool:
        return _has_subtypes(assay_name)

    @staticmethod
    def get_sample_subtypes(assay_name: str) -> list:
        return _get_sample_subtypes(assay_name)

    @staticmethod
    def subtype_id_var(assay_name: str) -> list:
        return _subtype_id_var(assay_name)

    @staticmethod
    def assay_exists(assay_name: str) -> bool:
        return _assay_exists(assay_name)

    @staticmethod
    def assay_names_for_db_query(assay_category_name: str) -> list:
        return _assay_names_for_db_query(assay_category_name)

    @staticmethod
    def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config: dict) -> dict:
        return _merge_sample_settings_with_assay_config(sample_doc, assay_config)

    @staticmethod
    def get_fusions_settings(sample: dict, settings: dict) -> dict:
        return _get_fusions_settings(sample, settings)

    @staticmethod
    def create_filter_genelist(genelist_dict: dict) -> list:
        return _create_filter_genelist(genelist_dict)

    @staticmethod
    def get_genes_covered_in_panel(genelists: dict, assay_panel_doc: dict) -> dict:
        return _get_genes_covered_in_panel(genelists, assay_panel_doc)

    @staticmethod
    def get_assay_genelist_names(genelists: dict) -> list:
        return _get_assay_genelist_names(genelists)

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
    def convert_object_id(data: Any) -> list | dict | str | Any:
        """
        Recursively convert all `ObjectId` instances in a list or dictionary to their string representation.

        Args:
            data (list | dict | ObjectId | Any): The input data structure to process.

        Returns:
            list | dict | str | Any: The data structure with all `ObjectId` instances converted to strings.
        """
        return _convert_object_id(data)

    @staticmethod
    def convert_to_serializable(data: Any) -> list | dict | str | Any:
        """
        Recursively convert data to a JSON-serializable format.

        This method traverses lists and dictionaries, converting any `ObjectId` to a string
        and any `datetime` object to its ISO 8601 string representation. Other types are returned as-is.

        Returns:
            list | dict | str | Any: The input data structure with all `ObjectId` and `datetime` instances converted to serializable strings.
        """
        return _convert_to_serializable(data)

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
        return _dict_to_tuple(d)

    @staticmethod
    def tuple_to_dict(t: Tuple) -> Dict:
        """Convert a tuple of sorted key-value pairs back to a dictionary.

        Args:
            t (Tuple): A tuple of (key, value) pairs, typically produced by dict_to_tuple.

        Returns:
            dict: The reconstructed dictionary from the tuple of pairs.
        """
        return _tuple_to_dict(t)

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
            app.logger.error("Failed to write report to '%s': %s", report_path, exc)
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
    def format_assay_config(config: dict, schema: dict) -> dict:
        return _format_assay_config(config, schema)

    @staticmethod
    def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
        return _format_filters_from_form(form_data, assay_config_schema)

    @staticmethod
    def create_assay_group_map(assay_groups_panels: list) -> dict:
        return _create_assay_group_map(assay_groups_panels)

    @staticmethod
    def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
        return _get_case_and_control_sample_ids(sample_doc)

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
            "author": current_username(),
            "time_created": CommonUtility.utc_now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "assay": variant_data.get("assay_group", None),
            "subpanel": variant_data.get("subpanel", None),
        }

        if "text" in kwargs:
            document["text"] = kwargs["text"]
        else:
            document["class"] = class_num

        if "source" in kwargs:
            document["source"] = kwargs["source"]

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
        return _safe_json_load(data, fallback=fallback)

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
    def get_sample_effective_genes(
        sample: dict, asp_doc: dict, checked_gl_dict: dict, target: str = "snv"
    ) -> tuple:
        return _get_sample_effective_genes(sample, asp_doc, checked_gl_dict, target=target)


# ---------------------------------------------------------------------------
# Module-level aliases — prefer importing these directly over CommonUtility.X
# ---------------------------------------------------------------------------
utc_now = CommonUtility.utc_now
hash_password = CommonUtility.hash_password
get_simple_id = CommonUtility.get_simple_id
nl_num = CommonUtility.nl_num
nl_join = CommonUtility.nl_join
get_report_header = CommonUtility.get_report_header
write_report = CommonUtility.write_report
get_base64_image = CommonUtility.get_base64_image
get_plot = CommonUtility.get_plot
generate_sample_cache_key = CommonUtility.generate_sample_cache_key
get_tier_classification = CommonUtility.get_tier_classification
create_classified_variant_doc = CommonUtility.create_classified_variant_doc
convert_to_serializable = _convert_to_serializable
convert_object_id = _convert_object_id
dict_to_tuple = _dict_to_tuple
tuple_to_dict = _tuple_to_dict
merge_sample_settings_with_assay_config = _merge_sample_settings_with_assay_config
get_sample_effective_genes = _get_sample_effective_genes
get_assay_genelist_names = _get_assay_genelist_names
