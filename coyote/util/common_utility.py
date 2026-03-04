"""UI-scoped utility helpers.

This module intentionally contains only presentation-layer helpers used by Flask
views. Domain/business normalization and persistence helpers are owned by API
modules under `api/core` and `api/infra`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


class CommonUtility:
    """Presentation-only helpers for Flask views."""

    @staticmethod
    def utc_now() -> datetime:
        """Return current UTC datetime."""
        return datetime.now(timezone.utc)

    @staticmethod
    def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
        """Map submitted filter form values to the schema-defined payload shape."""
        if hasattr(form_data, "__iter__") and not isinstance(form_data, dict):
            form_data = {field.name: field.data for field in form_data}

        fields_raw = assay_config_schema.get("sections", {}).get("filters", [])
        fields: list[str] = []
        if isinstance(fields_raw, dict):
            fields = list(fields_raw.keys())
        elif isinstance(fields_raw, list):
            for item in fields_raw:
                if isinstance(item, str):
                    fields.append(item)
                elif isinstance(item, dict):
                    key = (
                        item.get("key")
                        or item.get("id")
                        or item.get("_id")
                        or item.get("name")
                        or item.get("field")
                    )
                    if key:
                        fields.append(str(key))

        filters: dict[str, Any] = {}
        vep_consequences: list[str] = []
        genelists: list[str] = []
        fusionlists: list[str] = []
        fusion_callers: list[str] = []
        fusion_effects: list[str] = []
        cnveffects: list[str] = []

        prefix_map = {
            "vep_": vep_consequences,
            "genelist_": genelists,
            "fusionlist_": fusionlists,
            "fusioncaller_": fusion_callers,
            "fusioneffect_": fusion_effects,
            "cnveffect_": cnveffects,
        }

        for key, value in form_data.items():
            for prefix, target_list in prefix_map.items():
                if isinstance(key, str) and key.startswith(prefix) and value:
                    target_list.append(key.replace(prefix, ""))
                    break

        for field_name in fields:
            if field_name == "vep_consequences":
                filters["vep_consequences"] = vep_consequences
            elif field_name == "genelists":
                filters["genelists"] = genelists
            elif field_name == "fusionlists":
                filters["fusionlists"] = fusionlists
            elif field_name == "fusion_callers":
                filters["fusion_callers"] = fusion_callers
            elif field_name == "fusion_effects":
                filters["fusion_effects"] = fusion_effects
            elif field_name == "cnveffects":
                filters["cnveffects"] = cnveffects
            else:
                filters[field_name] = form_data.get(field_name)

        return filters

    @staticmethod
    def safe_json_load(data: Any, fallback: dict | None = None) -> dict:
        """Safely parse JSON input and return fallback on invalid payloads."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return fallback or {}
