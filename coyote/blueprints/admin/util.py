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
Utility functions and classes for administrative operations in the Coyote3 framework.

This module provides static methods for configuration management, form processing, versioning, gene list extraction, schema validation, and sample trace deletion. All methods are documented with their purpose, arguments, return values, and exceptions, following Python documentation best practices.
"""

from datetime import datetime, timezone
from dateutil.parser import parse as parse_datetime
from coyote.blueprints.admin import validators
from flask import current_app as app
from flask import flash
from coyote.extensions import store
import json
import os
from typing import Any, Union
import hashlib
from bson import ObjectId
from coyote.util.common_utility import CommonUtility


class AdminUtility:
    """
    AdminUtility provides static methods for common administrative operations in the Coyote3 framework.

    This class includes utilities for:
    - Processing and validating form and schema data
    - Managing version history and computing configuration deltas
    - Extracting and restructuring gene lists and assay configurations
    - Cleaning and flattening configuration data for comparison or form rendering
    - Loading schema templates and deleting sample traces from the database

    All methods are stateless and designed for use in admin-related workflows.
    """

    @staticmethod
    def cast_value(value: Any, field_type: str) -> Union[str, int, float, bool, list, dict, None]:
        """
        Casts the input value to the specified field type.

        Args:
            value (Any): The value to cast.
            field_type (str): The target data type (e.g., 'int', 'float', 'bool', 'list', 'json', etc.).

        Returns:
            Union[str, int, float, bool, list, dict, None]: The value cast to the appropriate type, or None if casting fails.
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if field_type in [
                "list",
                "multi-select",
                "select",
                "checkbox-group",
                "checkbox",
            ]:
                return []
            elif field_type in ["json", "jsoneditor", "jsoneditor-or-upload"]:
                return {}
            return None

        if (
            isinstance(value, list)
            and len(value) == 1
            and field_type
            not in [
                "list",
                "multi-select",
                "select",
                "checkbox-group",
                "checkbox",
                "json",
            ]
        ):
            value = value[0]

        if field_type == "int":
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return None
        elif field_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif field_type == "bool":
            return str(value).lower() in ["true", "1", "yes", "on"]
        elif field_type in [
            "list",
            "multi-select",
            "select",
            "checkbox",
            "checkbox-group",
        ]:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return [v.strip() for v in value.split(",") if v.strip()]
            return value
        elif field_type in [
            "json",
            "jsoneditor",
            "jsoneditor-or-upload",
            "dict",
        ]:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return {}
            return value
        return value

    @staticmethod
    def process_form_to_config(form: dict, schema: dict) -> dict:
        """
        Converts a form dictionary into a configuration dictionary according to the provided schema.

        Each field in the schema is processed:
        - If present in the form, its value is cast to the correct type.
        - If missing but defined as a subschema, initializes as an empty list or dict.
        - Otherwise, sets a default value based on the field type (e.g., empty list, dict, False, or None).

        Returns:
            dict: The resulting configuration dictionary with values cast and structured per the schema.
        """
        config = {}

        for key, field in schema.get("fields", {}).items():
            field_type = field.get("data_type")
            if key in form:
                config[key] = AdminUtility.cast_value(form[key], field_type)
            elif field_type == "subschema" and "schema" in field:
                subschema = schema.get("subschemas", {}).get(field["schema"])
                if not subschema:
                    config[key] = [] if field.get("data_type") == "list" else {}
                else:
                    config[key] = [] if field.get("data_type") == "list" else {}
            else:
                if field_type in [
                    "list",
                    "multi-select",
                    "select",
                    "checkbox",
                    "checkbox-group",
                ]:
                    config[key] = []
                elif field_type in [
                    "json",
                    "jsoneditor",
                    "jsoneditor-or-upload",
                ]:
                    config[key] = {}
                elif field_type == "bool":
                    config[key] = False
                else:
                    config[key] = None

        return config

    @staticmethod
    def hash_config(config: dict) -> str:
        """
        Generate a deterministic SHA-256 hash of the given configuration dictionary.

        This method ensures that the hash is stable by:
        - Removing volatile metadata fields (such as timestamps and user info).
        - Recursively sorting dictionary keys and serializing values in a consistent manner.
        - Using compact JSON serialization with sorted keys.

        Args:
            config (dict): The configuration dictionary to hash.

        Returns:
            str: The SHA-256 hexadecimal hash of the sanitized and serialized configuration.
        """

        def sanitize(value):
            """
            Recursively sanitize a value for deterministic hashing by:
            - Sorting dictionary keys and recursively sanitizing their values.
            - Recursively sanitizing list elements.
            - Returning primitive values as-is.
            """
            if isinstance(value, dict):
                return {k: sanitize(value[k]) for k in sorted(value)}
            elif isinstance(value, list):
                return [sanitize(v) for v in value]
            return value

        # Strip volatile metadata keys (if any)
        ignored_keys = {
            "created_on",
            "updated_on",
            "created_by",
            "updated_by",
            "version_history",
        }
        sanitized = {k: v for k, v in config.items() if k not in ignored_keys}
        stable_dict = sanitize(sanitized)

        # Serialize deterministically
        serialized = json.dumps(stable_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def inject_version_history(
        user_email: str,
        new_config: dict,
        old_config=None,
        is_new: bool = True,
    ) -> dict:
        """
        Initializes the version history for a configuration dictionary using delta-only logic.

        If `is_new` is True, an initial version entry is added with an 'initial' flag instead of a computed delta.
        If `is_new` is False, only the changed, new, or removed keys are included in the delta, as determined by comparing
        the old and new configurations.

        Args:
            user_email (str): The email address of the user making the change.
            new_config (dict): The new configuration dictionary.
            old_config (dict, optional): The previous configuration dictionary. Defaults to an empty dict.
            is_new (bool, optional): Whether this is the initial version. Defaults to True.

        Returns:
            dict: The new configuration dictionary with an updated version history.
        """
        if old_config is None:
            old_config = {}
        version = new_config.get("version", 1)
        version_history = old_config.pop("version_history", [])
        raw_timestamp = new_config.get("created_on", CommonUtility.utc_now())

        # Ensure it's a real datetime object
        if isinstance(raw_timestamp, str):
            try:
                timestamp = parse_datetime(raw_timestamp)
            except (ValueError, TypeError):
                timestamp = CommonUtility.utc_now()
        else:
            timestamp = raw_timestamp

        hash_val = AdminUtility.hash_config(new_config)

        if is_new:
            delta = {"initial": True}
        else:
            _, delta = AdminUtility.generate_version_delta(old_config, new_config)
            delta = {k: v for k, v in delta.items() if v}

        version_entry = {
            "version": version,
            "timestamp": timestamp,
            "user": user_email,
            "delta": delta,
            "hash": hash_val,
        }

        version_history.append(version_entry)

        new_config["version_history"] = version_history
        return new_config

    @staticmethod
    def generate_version_delta(old: dict, new: dict) -> tuple[dict, dict]:
        """
        Compute the difference and delta between two versioned configuration dictionaries.

        Args:
            old (dict): The original configuration dictionary.
            new (dict): The updated configuration dictionary.

        Returns:
            tuple[dict, dict]:
                - diff: A dictionary mapping keys to their old and new values where changes occurred.
                - delta: A dictionary with the following structure:
                    - 'only_in_old': Keys present only in the old configuration.
                    - 'only_in_new': Keys present only in the new configuration.
                    - 'changed': Keys whose values have changed, with their old and new values.
        """
        exclude_keys = {
            "version",
            "updated_by",
            "updated_on",
            "version_history",
        }

        diff = {
            key: {"old": old.get(key), "new": new.get(key)}
            for key in new
            if old.get(key) != new.get(key) and key not in exclude_keys
        }

        delta = {
            "only_in_old": {k: old[k] for k in old if k not in new and k not in exclude_keys},
            "only_in_new": {k: new[k] for k in new if k not in old and k not in exclude_keys},
            "changed": diff,
        }

        return diff, delta

    @staticmethod
    def apply_version_delta(base: dict, future_delta: dict) -> dict:
        """
        Restores a configuration dictionary to a previous version by applying the delta from the subsequent version.

        This method takes a base configuration and a delta (typically from the next version in the version history)
        and reverts the configuration to its earlier state by:
        - Restoring keys that were removed or changed to their previous values.
        - Removing keys that were newly added in the next version.

        Args:
            base (dict): The configuration dictionary to revert.
            future_delta (dict): The delta dictionary from the next version, containing 'only_in_old', 'only_in_new', and 'changed' keys.

        Returns:
            dict: The reverted configuration dictionary.
        """
        patched = base.copy()

        # Restore removed or changed keys (revert to old values)
        for key, old_val in future_delta.get("only_in_old", {}).items():
            patched[key] = old_val

        # Remove keys that were newly added in the next version
        for key in future_delta.get("only_in_new", {}):
            patched.pop(key, None)

        # Restore changed keys to their old values
        for key, change in future_delta.get("changed", {}).items():
            if "old" in change:
                patched[key] = change["old"]
            else:
                patched.pop(key, None)

        return patched

    @staticmethod
    def extract_gene_list(file_obj, pasted_text: str) -> list[str]:
        """
        Extracts a sorted, deduplicated gene list from either a file or pasted text.

        Parameters:
            file_obj (FileStorage | None): A file-like object containing gene identifiers, typically from `request.files.get(...)`.
            pasted_text (str): Raw text input containing gene identifiers, usually pasted into a textarea.

        Returns:
            list[str]: A sorted list of unique gene identifiers.
        """
        # Process file if provided and has a filename
        if file_obj and getattr(file_obj, "filename", ""):
            content = file_obj.read().decode("utf-8")
            genes = content

        # If no valid file, fallback to pasted text
        elif pasted_text and pasted_text.strip():
            genes = pasted_text

        else:
            return []

        gene_list = [g.strip() for g in genes.replace(",", "\n").splitlines() if g.strip()]

        return sorted(set(gene_list))

    @staticmethod
    def clean_config_for_comparison(cfg: dict) -> dict:
        """
        Removes metadata fields (such as timestamps, user info, and version) from the given configuration dictionary.

        This utility is useful for preparing configuration data for direct value comparison by eliminating fields that are not relevant to the actual configuration content.

        Args:
            cfg (dict): The configuration dictionary to clean.

        Returns:
            dict: A shallow copy of the configuration dictionary with metadata fields removed.
        """
        cfg = dict(cfg)  # shallow copy
        for meta_key in [
            "updated_on",
            "updated_by",
            "created_on",
            "created_by",
            "version",
        ]:
            cfg.pop(meta_key, None)
        return cfg

    @staticmethod
    def load_json5_template() -> str:
        """
        Loads the JSON5 schema template from the static directory.

        Returns:
            str: The contents of the JSON5 schema template file as a string.

        Raises:
            FileNotFoundError: If the schema template file does not exist.
            OSError: If there is an error reading the file.
        """
        path = os.path.join(
            app.root_path,
            "blueprints",
            "admin",
            "static",
            "schemas",
            "schema_template.json5",
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def validate_schema_structure(schema: dict) -> list[str]:
        """
        Validates the structure of the provided schema dictionary.

        - Checks for required top-level keys as defined in `validators.REQUIRED_SCHEMA_KEYS`.
        - Ensures the `sections` key is a dictionary, and each section contains a list of field names.
        - Verifies that every field listed in sections is defined in either `fields` or `subschemas`.
        - Supports dot notation for referencing subschema fields.

        Returns:
            list[str]: A list of error messages describing any structural issues found in the schema.
        """
        errors = []

        # Check for required top-level keys
        for key in validators.REQUIRED_SCHEMA_KEYS:
            if key not in schema:
                errors.append(f"Missing required key: '{key}'")

        # Ensure `sections` is a dict with lists of field names
        if "sections" in schema and not isinstance(schema["sections"], dict):
            errors.append("'sections' must be a dictionary")
        else:
            for section, keys in schema.get("sections", {}).items():
                if not isinstance(keys, list):
                    errors.append(f"Section '{section}' should contain a list of field keys")

        # Ensure each field listed in sections is defined in fields or subschemas
        defined_fields = set(schema.get("fields", {}).keys())
        defined_subschemas = schema.get("subschemas", {})
        for section, keys in schema.get("sections", {}).items():
            for field in keys:
                # Direct field match
                if field in defined_fields or field in defined_subschemas:
                    continue

                # Dot notation match
                if "." in field:
                    parent, child = field.split(".", 1)
                    if parent in defined_subschemas:
                        subschema_fields = defined_subschemas[parent].get("fields", {})
                        if child in subschema_fields:
                            continue

                errors.append(
                    f"Field '{field}' in section '{section}' is not defined in 'fields' or in any valid subschema"
                )

        return errors

    @staticmethod
    def delete_all_sample_traces(sample_id: str):
        """
        Deletes all traces of a sample from the database.

        This method removes all associated records for the given sample, including:
        - Variants
        - CNVs (Copy Number Variations)
        - Coverage data
        - Trans-locations
        - Fusions
        - Biomarkers
        - The sample record itself
        - RNA Expressions
        - RNA QC
        - RNA Classifications

        Args:
            sample_id (str): The unique identifier of the sample to delete.

        Side Effects:
            - Calls deletion handlers for each data type.
            - Displays a flash message for each deletion result.
        """
        sample_name = store.sample_handler.get_sample_by_id(sample_id)
        actions = [
            store.variant_handler.delete_sample_variants,
            store.cnv_handler.delete_sample_cnvs,
            store.coverage_handler.delete_sample_coverage,
            store.coverage2_handler.delete_sample_coverage,
            store.transloc_handler.delete_sample_translocs,
            store.fusion_handler.delete_sample_fusions,
            store.biomarker_handler.delete_sample_biomarkers,
            store.sample_handler.delete_sample,
        ]
        for handler in actions:
            handler(sample_id)
            result = handler(sample_id)
            collection_name = handler.__name__.replace("delete_sample_", "").replace("_handler", "")
            if collection_name == "delete_sample":
                collection_name = "sample"
            if result:
                flash(
                    f"Deleted {collection_name} for {sample_name.get('name')}",
                    "green",
                )
            else:
                flash(
                    f"Failed to delete {collection_name} for {sample_name.get('name')}",
                    "red",
                )

    @staticmethod
    def restore_objectids(obj) -> dict | list | Any:
        """
        Recursively convert string '_id' fields back to bson.ObjectId.
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "_id" and isinstance(value, str):
                    obj[key] = ObjectId(value)
                else:
                    AdminUtility.restore_objectids(value)
        elif isinstance(obj, list):
            for item in obj:
                AdminUtility.restore_objectids(item)

        return obj
