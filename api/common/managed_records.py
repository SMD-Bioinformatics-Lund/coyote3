"""Managed-record input normalization and version-history helpers."""

import hashlib
import json
from datetime import date, datetime
from typing import Any, Union

from bson import ObjectId
from dateutil.parser import parse as parse_datetime

from api.common.utility import utc_now


class ManagedRecordUtility:
    """Stateless helpers for managed-resource payloads and version history."""

    @staticmethod
    def normalize_field_value(
        value: Any, field_type: str
    ) -> Union[str, int, float, bool, list, dict, None]:
        """Normalize one UI form value using the generated field type metadata."""
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
        elif field_type == "datetime":
            if isinstance(value, str):
                try:
                    return parse_datetime(value)
                except (ValueError, TypeError):
                    return None
            return value
        elif field_type == "select":
            if isinstance(value, list):
                return value[0] if value else None
            if isinstance(value, str):
                stripped = value.strip()
                return stripped or None
            return value
        elif field_type in [
            "list",
            "multi-select",
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
    def normalize_form_payload(form: dict, schema: dict) -> dict:
        """Normalize flat form payload into the schema-shaped config payload."""
        config: dict[str, Any] = {}

        for key, field in schema.get("fields", {}).items():
            field_type = field.get("data_type")
            if key in form:
                config[key] = ManagedRecordUtility.normalize_field_value(form[key], field_type)
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
            elif isinstance(value, tuple):
                return [sanitize(v) for v in value]
            elif isinstance(value, ObjectId):
                return str(value)
            elif isinstance(value, (datetime, date)):
                return value.isoformat()
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
        actor_username: str,
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
            actor_username (str): The username of the user making the change.
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
        raw_timestamp = new_config.get("created_on", utc_now())

        # Ensure it's a real datetime object
        if isinstance(raw_timestamp, str):
            try:
                timestamp = parse_datetime(raw_timestamp)
            except (ValueError, TypeError):
                timestamp = utc_now()
        else:
            timestamp = raw_timestamp

        hash_val = ManagedRecordUtility.hash_config(new_config)

        if is_new:
            delta = {"initial": True}
        else:
            _, delta = ManagedRecordUtility.generate_version_delta(old_config, new_config)
            delta = {k: v for k, v in delta.items() if v}

        version_entry = {
            "version": version,
            "timestamp": timestamp,
            "user": actor_username,
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
    def restore_object_ids(obj) -> dict | list | Any:
        """Recursively convert string `_id` fields back to ``bson.ObjectId``."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "_id" and isinstance(value, str):
                    obj[key] = ObjectId(value)
                else:
                    ManagedRecordUtility.restore_object_ids(value)
        elif isinstance(obj, list):
            for item in obj:
                ManagedRecordUtility.restore_object_ids(item)

        return obj
