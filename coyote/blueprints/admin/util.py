from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from flask import current_app as app
from coyote.extensions import store
from bisect import bisect_left
import json


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
        Process form data into an assay config dict based on schema field types.
        Converts strings to appropriate Python types.
        """

        config = {}

        for key, field in schema.get("fields", {}).items():
            if field["type"] == "subschema":
                subschema = schema.get("subschemas", {}).get(field["schema"])
                if subschema:
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
        # flatten form data if it’s a list with single value
        if isinstance(value, list) and len(value) == 1 and field_type not in ["list", "json"]:
            value = value[0]

        if field_type == "int":
            return int(float(value))  # handles both "5" and "5.0"
        elif field_type == "float":
            return float(value)
        elif field_type == "bool":
            return str(value).lower() in ["true", "1", "yes", "on"]
        elif field_type == "list":
            try:
                return json.loads(value) if isinstance(value, str) else value
            except Exception:
                return []
        elif field_type == "json":
            try:
                return json.loads(value) if isinstance(value, str) else value
            except Exception:
                return {}
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
