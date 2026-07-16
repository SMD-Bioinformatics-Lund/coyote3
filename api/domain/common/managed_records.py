"""Pure managed-record normalization helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from api.contracts.managed_ui_schemas import build_form_spec


def normalize_field_value(value: Any, field_type: str | None) -> Any:
    """Normalize a submitted managed-resource field based on UI schema type."""
    if field_type in ["bool", "checkbox"]:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    if field_type in ["int", "integer", "number"]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if field_type in ["float", "decimal"]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if field_type in ["list", "multi-select", "select", "checkbox-group"]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [v.strip() for v in value.split(",") if v.strip()]
        return value
    if field_type in ["json", "jsoneditor", "jsoneditor-or-upload", "dict"]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value
    return value


def normalize_form_payload(form: dict, schema: dict) -> dict:
    """Normalize flat form payload into the schema-shaped config payload."""
    config: dict[str, Any] = {}
    for key, field in schema.get("fields", {}).items():
        field_type = field.get("data_type")
        if key in form:
            config[key] = normalize_field_value(form[key], field_type)
        elif field_type in ["list", "multi-select", "select", "checkbox", "checkbox-group"]:
            config[key] = []
        elif field_type in ["json", "jsoneditor", "jsoneditor-or-upload"]:
            config[key] = {}
        elif field_type == "bool":
            config[key] = False
        elif "default" in field:
            config[key] = field.get("default")
        elif field_type in ["text", "string", "email", "password"]:
            config[key] = ""
        else:
            config[key] = None
    return config


def normalize_managed_form_payload(spec, form_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize submitted form data using the managed resource form spec."""
    config = normalize_form_payload(form_data, build_form_spec(spec))
    for key, value in form_data.items():
        config.setdefault(key, value)
    return config


def inject_version_history(
    *,
    actor_username: str,
    new_config: dict[str, Any],
    old_config: dict[str, Any] | None = None,
    is_new: bool,
) -> dict[str, Any]:
    """Attach deterministic version-history metadata to a config payload."""
    config = deepcopy(new_config)
    history = list(old_config.get("version_history", [])) if isinstance(old_config, dict) else []
    history.append(
        {
            "version": int(config.get("version", 1) or 1),
            "actor": actor_username,
            "action": "create" if is_new else "update",
            "updated_on": config.get("updated_on"),
        }
    )
    config["version_history"] = history
    return config
