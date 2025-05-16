from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from dateutil.parser import parse as parse_datetime
from flask_login import current_user
from coyote.util.common_utility import CommonUtility
from coyote.blueprints.admin import validators
from coyote.services.audit_logs.decorators import log_action
from flask import current_app as app
from flask import flash
from coyote.extensions import store
from bisect import bisect_left
import json
import os
from typing import Any
import hashlib


class AdminUtility:
    """
    Admin utility class for handling various admin-related tasks.
    """

    @staticmethod
    def deep_merge(source, updates):
        """
        Recursively merge `updates` into `source`.
        If a value is a dictionary and the key exists in source as a dictionary, merge it recursively.
        Otherwise, overwrite the value.
        """
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(source.get(key), dict):
                AdminUtility.deep_merge(source[key], value)
            else:
                source[key] = value

    @staticmethod
    def handle_json_merge_input(json_string, config):
        """
        Parses a JSON string and merges it into the existing assay config.
        Raises ValueError if the string is not valid JSON or not a dict.
        """
        try:
            updates = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        if not isinstance(updates, dict):
            raise ValueError("Top-level JSON must be an object")

        AdminUtility.deep_merge(config, updates)

    @staticmethod
    def process_form_to_config(form: dict, schema: dict) -> dict:
        """
        Process form data into a config dict based on schema field types.
        Supports nested subschemas and list of subschemas.
        """
        config = {}

        for key, field in schema.get("fields", {}).items():
            field_type = field.get(
                "data_type", field.get("type")
            )  # Support fallback to old schemas

            if field_type == "subschema":
                subschema = schema.get("subschemas", {}).get(field["schema"])
                if subschema:
                    if field.get("type") == "list":
                        sub_configs = []
                        if key in form:
                            entries = (
                                json.loads(form[key])
                                if isinstance(form[key], str)
                                else form[key]
                            )
                            for entry in entries:
                                sub_config = {}
                                for subkey, subfield in subschema[
                                    "fields"
                                ].items():
                                    if subkey in entry:
                                        sub_config[subkey] = (
                                            AdminUtility.cast_value(
                                                entry[subkey],
                                                subfield.get(
                                                    "data_type",
                                                    subfield["type"],
                                                ),
                                            )
                                        )
                                sub_configs.append(sub_config)
                        config[key] = sub_configs
                    else:
                        sub_config = {}
                        for subkey, subfield in subschema["fields"].items():
                            form_key = f"{key}.{subkey}"
                            if form_key in form:
                                sub_config[subkey] = AdminUtility.cast_value(
                                    form[form_key],
                                    subfield.get(
                                        "data_type", subfield["type"]
                                    ),
                                )
                        config[key] = sub_config
            else:
                if key in form:
                    config[key] = AdminUtility.cast_value(
                        form[key], field_type
                    )

        return config

    @staticmethod
    def cast_value(
        value, field_type
    ) -> str | int | float | bool | list[str] | dict | None | Any:
        """
        Casts a value to the specified field type.
        Handles types: int, float, bool, list, json, and schema-driven UI inputs.
        """

        # Handle None or empty string safely
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if field_type in [
                "list",
                "json",
                "multi-select",
                "checkbox-group",
            ]:
                return [] if field_type != "json" else {}
            return None

        # Normalize single-item lists
        if (
            isinstance(value, list)
            and len(value) == 1
            and field_type
            not in ["list", "multi-select", "checkbox-group", "json"]
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

        elif field_type in ["list", "multi-select", "checkbox-group"]:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return [v.strip() for v in value.split(",") if v.strip()]
            return value

        elif field_type in ["json", "jsoneditor", "jsoneditor-or-upload"]:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return [v.strip() for v in value.splitlines() if v.strip()]
            return value

        return value  # default fallback

    @staticmethod
    def hash_config(config: dict) -> str:
        """
        Generate a deterministic SHA-256 hash of the config dictionary.

        Ensures keys are sorted and values are serialized consistently.
        """

        def sanitize(value):
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
        serialized = json.dumps(
            stable_dict, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def inject_version_history(
        user_email: str,
        new_config: dict,
        old_config: dict = {},
        is_new: bool = True,
    ) -> dict:
        """
        Initializes version history with delta-only logic.
        If is_new, it adds an 'initial' flag instead of computing delta.
        Otherwise, includes only changed/new/removed keys in the delta.
        """
        version = new_config.get("version", 1)
        version_history = old_config.pop("version_history", [])
        raw_timestamp = new_config.get("created_on", datetime.utcnow())

        # Ensure it's a real datetime object
        if isinstance(raw_timestamp, str):
            try:
                timestamp = parse_datetime(raw_timestamp)
            except Exception:
                timestamp = datetime.utcnow()
        else:
            timestamp = raw_timestamp

        hash_val = AdminUtility.hash_config(new_config)

        if is_new:
            delta = {"initial": True}
        else:
            _, delta = AdminUtility.generate_version_delta(
                old_config, new_config
            )
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
        Compute the diff and delta between old and new versioned documents.

        Returns:
            - diff: dict of keys with {old, new} pairs
            - delta: dict with 'only_in_old', 'only_in_new', and 'changed'
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
            "only_in_old": {
                k: old[k]
                for k in old
                if k not in new and k not in exclude_keys
            },
            "only_in_new": {
                k: new[k]
                for k in new
                if k not in old and k not in exclude_keys
            },
            "changed": diff,
        }

        return diff, delta

    @staticmethod
    def apply_version_delta(base: dict, future_delta: dict) -> dict:
        """
        Restore the document to an earlier version using the delta from the *next* version.

        For example, to restore version 3, apply the delta stored in version 4.
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
    def restructure_assay_config(flat_config: dict, schema: dict) -> dict:
        """
        Restructures a flat configuration dictionary into a nested format according to a provided schema.

        Args:
            flat_config (dict): The flat dictionary containing configuration key-value pairs.
            schema (dict): The schema dictionary that defines the structure, including sections and their keys.

        Returns:
            dict: A nested dictionary where keys are organized into sections as specified by the schema.
                For sections named "filters", keys are grouped under that section as a sub-dictionary.
                Other keys are placed at the top level of the returned dictionary.

        Example:
            flat_config = {"a": 1, "b": 2, "filter1": 3}
            schema = {"sections": {"filters": ["filter1"]}}
            result = restructure_assay_config(flat_config, schema)
        """
        env_block = {}

        schema_sections = schema.get("sections", {})

        for section_name, section_keys in schema_sections.items():
            if section_name in ["filters"]:
                env_block[section_name] = {}
            for key in section_keys:
                if section_name in ["filters"]:
                    env_block[section_name][key] = (
                        flat_config[key] if key in flat_config else None
                    )
                else:
                    env_block[key] = flat_config.get(key)

        return env_block

    @staticmethod
    def flatten_config_for_form(config: dict, schema: dict) -> dict:
        """
        Flatten nested config sections (like filters, query, verification_samples) into a flat dict
        so that schema-driven forms can render them easily.

        Keys from top-level and nested sections (as defined in schema.sections) are merged into one dict.
        """
        flat = {}

        section_keys = schema.get("sections", {})
        for section_name, keys in section_keys.items():
            for key in keys:
                if key in config:
                    flat[key] = config[key]
                elif section_name in config and isinstance(
                    config[section_name], dict
                ):
                    # Check nested sections like filters, query, verification_samples
                    if key in config[section_name]:
                        flat[key] = config[section_name][key]
                else:
                    flat[key] = None  # fallback if not found

        return flat

    @staticmethod
    def clean_config_for_comparison(cfg):
        """
        Cleans the config dictionary for comparison by removing metadata fields.
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
    def load_json5_template():
        """
        Loads the JSON5 schema template from the static directory.
        This template is used for creating new schemas.
        """
        path = os.path.join(
            app.root_path,
            "blueprints",
            "admin",
            "static",
            "schemas",
            "schema_template.json5",
        )
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def validate_schema_structure(schema: dict) -> list[str]:
        """
        Validates the structure of the schema.
        Checks for required keys and ensures that sections are defined correctly.
        Returns a list of error messages if any issues are found.
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
                    errors.append(
                        f"Section '{section}' should contain a list of field keys"
                    )

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
                        subschema_fields = defined_subschemas[parent].get(
                            "fields", {}
                        )
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
        This includes variants, CNVs, coverage, translocations, fusions, biomarkers, and the sample itself.
        """
        sample_name = store.sample_handler.get_sample_with_id(sample_id)
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
            collection_name = handler.__name__.replace(
                "delete_sample_", ""
            ).replace("_handler", "")
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
