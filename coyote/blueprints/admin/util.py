from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from coyote.blueprints.admin import validators
from coyote.services.audit_logs.decorators import log_action
from flask import current_app as app
from flask import flash
from coyote.extensions import store
from bisect import bisect_left
import json
import os


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
            if field["type"] == "subschema":
                subschema = schema.get("subschemas", {}).get(field["schema"])
                if subschema:
                    if field.get("type") == "list":
                        # Handle list of subschemas
                        sub_configs = []
                        # Assume form[key] is a list of dicts or json string
                        if key in form:
                            entries = (
                                json.loads(form[key]) if isinstance(form[key], str) else form[key]
                            )
                            for entry in entries:
                                sub_config = {}
                                for subkey, subfield in subschema["fields"].items():
                                    if subkey in entry:
                                        sub_config[subkey] = AdminUtility.cast_value(
                                            entry[subkey], subfield["type"]
                                        )
                                sub_configs.append(sub_config)
                        config[key] = sub_configs
                    else:
                        # Normal nested dict subschema
                        sub_config = {}
                        for subkey, subfield in subschema["fields"].items():
                            form_key = f"{key}.{subkey}"
                            if form_key in form:
                                sub_config[subkey] = AdminUtility.cast_value(
                                    form[form_key], subfield["type"]
                                )
                        config[key] = sub_config
            else:
                if key in form:
                    config[key] = AdminUtility.cast_value(form[key], field["type"])

        return config

    @staticmethod
    def cast_value(value, field_type):
        """
        Casts a value to the specified field type.
        Handles types: int, float, bool, list, json safely.
        """

        # Handle None or empty strings gracefully
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if field_type in ["list", "json"]:
                return [] if field_type == "list" else {}
            return None

        # Flatten list if needed
        if isinstance(value, list) and len(value) == 1 and field_type not in ["list", "json"]:
            value = value[0]

        if field_type == "int":
            try:
                return int(float(value))  # Safe parse
            except (ValueError, TypeError):
                return None
        elif field_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif field_type == "bool":
            return str(value).lower() in ["true", "1", "yes", "on"]
        elif field_type == "list":
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    # Fallback to simple comma split
                    return [v.strip() for v in value.split(",") if v.strip()]
            return value
        elif field_type == "json":
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return {}
            return value

        return value

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
            app.root_path, "blueprints", "admin", "static", "schemas", "schema_template.json5"
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
