"""Expose shared configuration, serialization, identity, and reporting utilities."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, Tuple

from werkzeug.security import generate_password_hash

from api.app.runtime_state import app, current_username
from api.app.utilities import assay_filters, serialization
from api.domain.common import assay_filters as domain_assay_filters
from api.domain.common.reporting import nl_num as render_swedish_number
from api.domain.core.annotation_identity import (
    annotation_context_fields,
    annotation_identity_fields,
)
from api.domain.core.dna.variant_identity import (
    build_simple_id,
    normalize_simple_id,
)


class CommonUtility:
    """Expose configuration, serialization, identity, and report utilities to API callers."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Generate a salted password hash using PBKDF2-HMAC-SHA256.

        Args:
            password (str): The plaintext password to hash.

        Returns:
            A password hash containing the algorithm, iteration count, random
            salt, and digest in Werkzeug's storage format.

        Notes:
            Werkzeug selects its default iteration count and generates the salt.
        """
        return generate_password_hash(password, method="pbkdf2:sha256")

    @staticmethod
    def utc_now():
        """Read the current wall-clock time in UTC.

        Returns:
            A timezone-aware datetime with timezone.utc.
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def get_simple_id(variant: dict) -> str:
        """Normalize an existing simple ID or build one from variant coordinates.

        Args:
            variant: Document with a truthy simple_id, or CHROM, POS, REF, and ALT
                fields. Missing or null coordinate fields normalize to empty text.

        Returns:
            Canonical CHROM_POS_REF_ALT text. An existing ID without four
            underscore-delimited parts is returned as stripped text. The input
            document is not changed.
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
        """Copy all assay settings or one assay's configured value.

        Args:
            assay_name: ASSAYS key, or None for the entire mapping.

        Returns:
            A deep copy, preserving a selected explicit None. Missing or null
            ASSAYS and unknown keys yield an empty dictionary.
        """
        return assay_filters.assay_config(assay_name)

    @staticmethod
    def get_group_parameters(group: str) -> dict:
        """Copy runtime parameters for an assay group.

        Args:
            group: Key in GROUP_CONFIGS.

        Returns:
            A deep copy of the group value, or None for a missing or null group.
            Missing or null GROUP_CONFIGS yields an empty dictionary instead.
        """
        return assay_filters.get_group_parameters(group)

    @staticmethod
    def table_config() -> dict:
        """Copy runtime table settings.

        Returns:
            A deep copy of TABLE, or None if absent or null.
        """
        return assay_filters.table_config()

    @staticmethod
    def cutoff_config(assay_name: str, sample_type: str = None) -> dict:
        """Copy configured cutoffs for an assay and optional sample type.

        Args:
            assay_name: Key in CUTOFFS.
            sample_type: Subsection key, or None for all assay cutoffs.

        Returns:
            A deep copy of the selected value. Missing or null CUTOFFS and absent
            assays yield an empty dictionary. Missing sample types yield None;
            null assay values are preserved when sample_type is None.

        Raises:
            AttributeError: A sample type is requested from a null assay value.
        """
        return assay_filters.cutoff_config(assay_name, sample_type)

    @staticmethod
    def assay_info_vars(assay_name: str) -> list:
        """Read copied sample-information fields for an assay.

        Args:
            assay_name: Assay key in ASSAYS.

        Returns:
            The sample_info value, or None if the assay or field is missing.
        """
        return assay_filters.assay_info_vars(assay_name)

    @staticmethod
    def assay_qc_vars(assay_name: str) -> list:
        """Read copied quality-control fields for an assay.

        Args:
            assay_name: Assay key in ASSAYS.

        Returns:
            The sample_qc value, or None if the assay or field is missing.
        """
        return assay_filters.assay_qc_vars(assay_name)

    @staticmethod
    def assays_in_assay_group(assay_name: str) -> list:
        """Read copied member assays for a configured group.

        Args:
            assay_name: Group key in ASSAYS.

        Returns:
            The include_assays value, or None if the group or field is missing.
        """
        return assay_filters.assays_in_assay_group(assay_name)

    @staticmethod
    def has_subtypes(assay_name: str) -> bool:
        """Test for the presence of an assay's subtypes key.

        Args:
            assay_name: Assay key in ASSAYS.

        Returns:
            True when subtypes exists, even if empty or null; otherwise False.
        """
        return assay_filters.has_subtypes(assay_name)

    @staticmethod
    def get_sample_subtypes(assay_name: str) -> list:
        """Read copied subtype names for an assay.

        Args:
            assay_name: Assay key in ASSAYS.

        Returns:
            subtype_names, or None when the assay, section, or names are absent.

        Raises:
            AttributeError: The subtypes section is explicitly null.
        """
        return assay_filters.get_sample_subtypes(assay_name)

    @staticmethod
    def subtype_id_var(assay_name: str) -> list:
        """Read the identifier-column setting for an assay with subtypes.

        Args:
            assay_name: Assay key in ASSAYS.

        Returns:
            The copied subtype_id_col value, commonly a string, without coercion.
            Returns None when subtypes is absent or the column value is null.

        Raises:
            AttributeError: subtypes exists but subtype_id_col is missing.
        """
        return assay_filters.subtype_id_var(assay_name)

    @staticmethod
    def assay_exists(assay_name: str) -> bool:
        """Test whether an assay key is registered.

        Args:
            assay_name: Key to look up in ASSAYS.

        Returns:
            True if the key exists, including when its configured value is null.
        """
        return assay_filters.assay_exists(assay_name)

    @staticmethod
    def assay_names_for_db_query(assay_category_name: str) -> list:
        """Expand a group into assay names, preserving restored-query suffixes.

        Args:
            assay_category_name: Group key, optionally ending in _restored.

        Returns:
            Copied include_assays in order, with _restored appended to each name
            for restored queries. Missing or null members yield None otherwise.

        Raises:
            TypeError: A restored group has missing or null include_assays.
        """
        return assay_filters.assay_names_for_db_query(assay_category_name)

    @staticmethod
    def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config: dict) -> dict:
        """Replace a sample's filters in place with copied settings or defaults.

        Args:
            sample_doc: Sample to mutate. Truthy filters are retained as a deep
                copy; missing, null, or empty filters select assay defaults.
            assay_config: Default filters source. Missing filters means an empty
                dictionary; explicit null filters remain None.

        Returns:
            The same sample dictionary, with filters replaced and
            use_diagnosis_genelist removed. Individual fields are not merged.
        """
        return assay_filters.merge_sample_settings_with_assay_config(sample_doc, assay_config)

    @staticmethod
    def get_fusions_settings(sample: dict, settings: dict) -> dict:
        """Resolve integer read and pair thresholds for fusion filtering.

        Args:
            sample: filter_min_spanreads and filter_min_spanpairs overrides.
            settings: default_spanreads and default_spanpairs for absent sample
                keys, defaulting to zero. Explicit nulls do not fall back.

        Returns:
            A new dictionary of integer min_spanreads and min_spanpairs counts.

        Raises:
            TypeError: A selected threshold is None or cannot be passed to int.
            ValueError: A selected threshold string is not an integer.
        """
        return assay_filters.get_fusions_settings(sample, settings)

    @staticmethod
    def create_filter_genelist(genelist_dict: dict) -> list:
        """Collect unique covered genes from active gene-list records.

        Args:
            genelist_dict: Records keyed by list ID, selected by truthy is_active.

        Returns:
            A new deduplicated list of covered genes, with unspecified ordering.

        Raises:
            KeyError: An active record lacks covered.
            TypeError: Covered genes are not iterable or contain unhashable values.
        """
        return assay_filters.create_filter_genelist(genelist_dict)

    @staticmethod
    def get_genes_covered_in_panel(genelists: dict, assay_panel_doc: dict) -> dict:
        """Annotate supplied gene-list records with panel coverage in place.

        Args:
            genelists: Records keyed by list ID; absent genes means no genes.
            assay_panel_doc: covered_genes and asp_family settings. WGS/WTS,
                matched case-insensitively, cover every gene in each list.

        Returns:
            A new outer dictionary sharing the mutated input records, each with
            sorted, deduplicated covered and uncovered gene lists.

        Raises:
            TypeError: A genes or covered_genes value is null or not iterable.
        """
        return assay_filters.get_genes_covered_in_panel(genelists, assay_panel_doc)

    @staticmethod
    def get_assay_genelist_names(genelists: dict) -> list:
        """Extract IDs from an iterable of gene-list documents.

        Args:
            genelists: Documents, normally a list, each containing _id.

        Returns:
            A new list of IDs in input order, preserving duplicates and null IDs.

        Raises:
            KeyError: A document lacks _id.
        """
        return assay_filters.get_assay_genelist_names(genelists)

    @staticmethod
    def nl_num(i: int, gender: str) -> Any | str:
        """Render small report counts with the configured Swedish cardinal words.

        Args:
            i: Integer count; negative or out-of-table values use decimal text.
            gender: "t" selects neuter words; all other values select common gender.

        Returns:
            The configured word for an in-range count, otherwise str(i).
        """
        return render_swedish_number(i, gender)

    @staticmethod
    def nl_join(arr: list, joiner: str) -> str:
        """Join strings with commas and a conjunction before the final item.

        Args:
            arr (list): List of strings to join.
            joiner (str): The word to use as the conjunction (e.g., "and", "or").

        Returns:
            Empty text for an empty list, the single item unchanged for one item,
            or joined text for multiple items. The input list is not mutated.
        """
        if not arr:
            return ""
        if len(arr) == 1:
            return arr[0]
        if len(arr) == 2:
            return f"{arr[0]} {joiner} {arr[1]}"
        return f"{', '.join(arr[:-1])} {joiner} {arr[-1]}"

    @staticmethod
    def convert_object_id(data: Any) -> list | dict | str | Any:
        """Convert ObjectId values within lists and dictionaries to strings.

        Args:
            data: Scalar or nested lists/dictionaries; dictionary keys are not converted.

        Returns:
            New lists/dictionaries with stringified ObjectId values. Other values,
            including None and tuples, pass through unchanged; inputs are not mutated.
        """
        return serialization.convert_object_id(data)

    @staticmethod
    def convert_to_serializable(data: Any) -> list | dict | str | Any:
        """Recursively convert supported objects to plain containers and scalar text.

        Args:
            data: Value or nested structure, including Pydantic models and objects
                with a callable dict method defined on their type.

        Returns:
            ObjectIds become strings and dates/datetimes become ISO text. Models
            and mappings become dictionaries (including converted keys); lists,
            tuples, and sets become lists. Other values, including None, pass
            through unchanged, so arbitrary inputs are not guaranteed JSON-safe.

        Notes:
            Delegates without changing caller containers; custom dict methods
            are invoked and their errors propagate.
        """
        return serialization.convert_to_serializable(data)

    @staticmethod
    def dict_to_tuple(d: Dict) -> Tuple:
        """Convert a dictionary to a tuple of sorted key-value pairs.

        Values are not converted or copied, so the result is hashable only when
        all retained keys and values are hashable.

        Args:
            d (dict): The dictionary to convert.

        Returns:
            tuple: A tuple of (key, value) pairs sorted by key.

        Raises:
            TypeError: Keys cannot be compared for sorting.
        """
        return serialization.dict_to_tuple(d)

    @staticmethod
    def tuple_to_dict(t: Tuple) -> Dict:
        """Build a dictionary from key-value pairs without copying their values.

        Args:
            t: Iterable of two-element pairs with hashable keys; sorting is not required.

        Returns:
            A new dictionary; later duplicate keys overwrite earlier values.

        Raises:
            TypeError: The input is not iterable or a key is unhashable.
            ValueError: An entry does not contain exactly two elements.
        """
        return serialization.tuple_to_dict(t)

    @staticmethod
    def get_report_header(assay: str, sample: dict, header: str) -> str:
        """Get the report header string based on the assay type and sample data.

        If the assay is "myeloid" and the sample's ``subpanel_id`` is ``hem-snabb``, the header is modified:
        - If "sample_no" is 2, appends ": fullständig parad analys" (full paired analysis).
        - Otherwise, appends ": preliminär oparad analys" (preliminary unpaired analysis).

        Args:
            assay (str): The assay name.
            sample (dict): The sample data dictionary.
            header (str): The initial header string.

        Returns:
            str: The formatted report header.
        """
        if assay == "myeloid" and sample.get("subpanel_id") == "hem-snabb":
            if sample.get("sample_no") == 2:
                header += ": fullständig parad analys"
            else:
                header += ": preliminär oparad analys"
        return header

    @staticmethod
    def write_report(report_data: str, report_path: str) -> bool:
        """Write UTF-8 report text, creating parent directories as needed.

        An existing file is truncated before writing. Failures are logged and do
        not restore any previous file contents.

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
        """Get a base64-encoded string representation of an image file.

        Args:
            image_path (str): The file path to the image.

        Returns:
            str: The base64-encoded string of the image content.

        Raises:
            OSError: The file cannot be opened or read.
        """
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        return base64_image

    @staticmethod
    def get_plot(fn: str, assay_config: dict = None) -> bool:
        """Read a configured report plot as base64 when a directory and name are set.

        Args:
            fn: Plot filename joined to REPORT.plots_path; a falsy name skips loading.
            assay_config: Mapping with an optional REPORT.plots_path. Despite the
                default of None, callers must supply a mapping.

        Returns:
            Base64 file content, or False when the directory or filename is falsy.
            File existence is not checked before reading.

        Raises:
            AttributeError: assay_config or its REPORT section is None.
            OSError: The selected plot cannot be opened or read, including missing files.
        """
        plot_dir = assay_config.get("REPORT", {}).get("plots_path", "")
        if plot_dir and fn:
            image_path = os.path.join(plot_dir, f"{fn}")
            return CommonUtility.get_base64_image(image_path)
        return False

    @staticmethod
    def generate_sample_cache_key(**kwargs) -> str:
        """Generate a stable cache key for sample data.

        This method creates a cache key string based on the provided keyword arguments.
        It removes internal-use keys (such as 'self' and 'use_cache'), sorts any list of user groups,
        normalizes datetime values to date strings, and serializes the arguments to a JSON string.
        The resulting string is hashed using MD5 and prefixed with 'samples:'.

        Args:
            **kwargs: Sample-query parameters. self and use_cache are ignored;
                user_groups lists are sorted. Only top-level datetime and unsupported
                values are normalized; nested containers must already be JSON-compatible.

        Returns:
            str: A stable cache key for the sample data.

        Raises:
            TypeError: User groups cannot be sorted or values cannot be JSON-encoded.
            ValueError: Nested containers have circular references.

        Notes:
            The local keyword dictionary is changed, not caller containers. Datetimes
            on the same date intentionally share a representation; uniqueness is not guaranteed.
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
        """Move flat assay settings into filters and reporting in place.

        Args:
            config: Dictionary to mutate, or None for a new dictionary.
            schema: Schema with filter/reporting sections as mappings or field
                lists; None means no schema fields.

        Returns:
            The same config, or a new dictionary for None. Flat fields take
            precedence over nested fields, then defaults, preserving explicit None.
            Non-dictionary existing sections are replaced. Nested extension keys
            survive except _id, id, id_ and the section's own name.

        Notes:
            Consumed flat fields are removed. Mutable values and defaults remain
            shared with the inputs; the wrapper does not copy config first.
        """
        return assay_filters.format_assay_config(config, schema)

    @staticmethod
    def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
        """Extract schema-selected values and truthy checkbox groups from a form.

        Args:
            form_data: Dictionary or iterable of fields exposing name and data.
            assay_config_schema: Schema with sections.filters as a mapping or
                list of field names/descriptors; missing sections select nothing.

        Returns:
            A new dictionary of schema fields. Checkbox prefixes vep_, snvlist_,
            fusionlist_, fusioncaller_, fusioneffect_, and cnveffect_ populate
            corresponding lists in submission order, with prefix text removed.
            Other missing fields become None; schema defaults are not applied.
            Inputs are not mutated, but ordinary field values remain shared.
        """
        return assay_filters.format_filters_from_form(form_data, assay_config_schema)

    @staticmethod
    def create_assay_group_map(assay_groups_panels: list) -> dict:
        """Group panel metadata by its configured assay group.

        Args:
            assay_groups_panels: Panel documents with asp_group, asp_id,
                display_name, and asp_category values.

        Returns:
            New lists of asp_id/display_name/asp_category dictionaries in input
            order. Missing groups use the None key; missing metadata stays None.
        """
        return assay_filters.create_assay_group_map(assay_groups_panels)

    @staticmethod
    def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
        """Extract truthy case and control identifiers without changing the sample.

        Args:
            sample_doc: Document with optional case_id and control_id values.

        Returns:
            A new dictionary with case/control entries; absent, null, and other
            falsy identifiers are omitted.
        """
        return assay_filters.get_case_and_control_sample_ids(sample_doc)

    @staticmethod
    def create_classified_variant_doc(
        variant: str,
        nomenclature: str,
        class_num: int,
        variant_data: dict,
        **kwargs,
    ) -> Any:
        """Build a classification or annotation dictionary without inserting it.

        Args:
            variant: Primary display identity for the finding.
            nomenclature: Identity category, normally p, c, g, cn, f, or t; passed
                to the canonical context and identity helpers without validation here.
            class_num: Classification stored as class only when text is not supplied.
            variant_data: Source for assay_group, subpanel, and nomenclature-specific
                gene, transcript, and alternate identity fields. Missing assay_group
                and subpanel values become None.
            **kwargs: Only text is used. Its presence, even with None or an empty
                value, stores text instead of class; other keywords are ignored.

        Returns:
            A new dictionary with current request author (falling back to "api"),
            timezone-aware UTC creation time, and canonical context/identity fields.
            The input is not mutated and no database write is performed.
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

        document.update(annotation_context_fields(nomenclature=nomenclature, source=variant_data))

        document.update(
            annotation_identity_fields(
                variant=variant,
                nomenclature=nomenclature,
                source=variant_data,
            )
        )

        return document

    @staticmethod
    def safe_json_load(data: Any, fallback=None) -> dict:
        """Decode JSON, using a truthy fallback only for JSON syntax errors.

        Args:
            data: JSON text as str, bytes, or bytearray; None is not accepted.
            fallback: Value returned on JSONDecodeError if truthy. None and other
                falsy values select a new empty dictionary.

        Returns:
            Any decoded JSON value, including lists, scalars, or None for JSON null.
            On syntax errors, returns fallback itself when truthy, otherwise {}.

        Raises:
            TypeError: data is not str, bytes, or bytearray.
            UnicodeDecodeError: Byte input cannot be decoded as JSON text.
        """
        return serialization.safe_json_load(data, fallback=fallback)

    @staticmethod
    def get_tier_classification(data: dict) -> int:
        """Return the highest-numbered tier whose value is not None.

        Args:
            data: Variant document with optional tier1 through tier4 values.
                Falsy values such as False, zero, or empty strings still count.

        Returns:
            The last matching tier number (1-4), or zero when all are absent/null.
        """
        tiers = {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}
        class_num = 0
        for key, value in tiers.items():
            if data.get(key, None) is not None:
                class_num = value

        return class_num

    @staticmethod
    def get_sample_effective_genes(
        sample: dict,
        asp_doc: dict,
        checked_gl_dict: dict,
        target: str = "snv",
        intent: str = "somatic",
    ) -> tuple:
        """Resolve target-specific gene coverage using the canonical domain helper.

        Args:
            sample: Sample filters, omics_layer, and analysis_intents used to
                resolve the profile and ad-hoc genes; absent filters are normalized.
            asp_doc: Panel covered_genes and asp_family settings.
            checked_gl_dict: Records keyed by list IDs selected for this target;
                None means no selected lists. Records are copied before annotation.
            target: Analysis scope, normally snv (default), cnv, fusion, or
                translocation. Other values do not restrict lists by list_type.
            intent: Filter profile to resolve, defaulting to somatic.

        Returns:
            Coverage-annotated records and deduplicated active covered genes as a
            pair. With no applicable lists or ad-hoc genes, uses sorted panel
            coverage. Empty genes can mean an unrestricted panel or a selection
            without overlap; caller documents are not mutated.
        """
        return domain_assay_filters.get_sample_effective_genes(
            sample,
            asp_doc,
            checked_gl_dict,
            target=target,
            intent=intent,
        )


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
convert_to_serializable = serialization.convert_to_serializable
convert_object_id = serialization.convert_object_id
dict_to_tuple = serialization.dict_to_tuple
tuple_to_dict = serialization.tuple_to_dict
merge_sample_settings_with_assay_config = assay_filters.merge_sample_settings_with_assay_config
get_sample_effective_genes = domain_assay_filters.get_sample_effective_genes
get_assay_genelist_names = assay_filters.get_assay_genelist_names
