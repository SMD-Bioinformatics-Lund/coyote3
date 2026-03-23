"""Backend-owned UI schema generation for managed admin resources."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, Union, get_args, get_origin

from pydantic.fields import PydanticUndefined

from api.contracts.managed_resources import ManagedResourceSpec
from api.contracts.schemas import COLLECTION_MODEL_ADAPTERS


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _field_data_type(annotation: Any) -> tuple[str, list[Any] | None]:
    inner = _unwrap_optional(annotation)
    origin = get_origin(inner)

    if origin is Literal:
        options = list(get_args(inner))
        return "select", options
    if origin in (list, tuple, set):
        return "list", None
    if origin is dict:
        return "json", None
    if inner is bool:
        return "bool", None
    if inner is datetime:
        return "datetime", None
    if inner is int:
        return "int", None
    if inner is float:
        return "float", None
    return "text", None


def _default_display_type(data_type: str, options: list[Any] | None) -> str:
    if data_type == "bool":
        return "checkbox"
    if data_type == "json":
        return "jsoneditor"
    if options:
        return "select"
    if data_type == "list":
        return "multi-select" if options else "textarea"
    return "input"


RESOURCE_EXTRA_FIELDS: dict[str, dict[str, dict[str, Any]]] = {
    "asp": {
        "platform": {
            "label": "Platform",
            "data_type": "text",
            "display_type": "input",
            "required": False,
        },
    },
    "aspc_dna": {
        "verification_samples": {
            "label": "Verification Samples",
            "data_type": "json",
            "display_type": "jsoneditor",
            "required": False,
            "default": {},
        },
        "query": {
            "label": "Query",
            "data_type": "json",
            "display_type": "jsoneditor",
            "required": False,
            "default": {},
        },
    },
}

RESOURCE_FIELD_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "asp": {
        "assay_name": {"display_type": "input"},
        "asp_group": {"display_type": "input"},
        "asp_family": {"display_type": "input"},
        "asp_category": {"display_type": "select", "options": ["DNA", "RNA"]},
        "display_name": {"display_type": "input"},
        "description": {"display_type": "textarea"},
        "covered_genes": {"display_type": "jsoneditor-or-upload"},
        "germline_genes": {"display_type": "jsoneditor-or-upload"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "aspc_dna": {
        "assay_name": {"display_type": "select"},
        "environment": {
            "display_type": "select",
            "options": ["production", "development", "test", "validation"],
        },
        "analysis_types": {"display_type": "checkbox-group"},
        "report_sections": {"display_type": "checkbox-group"},
        "vep_consequences": {"display_type": "checkbox-group"},
        "cnveffects": {"display_type": "checkbox-group"},
        "verification_samples": {"display_type": "jsoneditor"},
        "query": {"display_type": "jsoneditor"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "aspc_rna": {
        "assay_name": {"display_type": "select"},
        "environment": {
            "display_type": "select",
            "options": ["production", "development", "test", "validation"],
        },
        "analysis_types": {"display_type": "checkbox-group"},
        "report_sections": {"display_type": "checkbox-group"},
        "vep_consequences": {"display_type": "checkbox-group"},
        "cnveffects": {"display_type": "checkbox-group"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "isgl": {
        "diagnosis": {"display_type": "textarea"},
        "assay_groups": {"display_type": "checkbox-group"},
        "assays": {"display_type": "checkbox-group"},
        "genes": {"display_type": "jsoneditor-or-upload"},
        "adhoc": {"display_type": "checkbox"},
        "is_public": {"display_type": "checkbox"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "role": {
        "permissions": {"display_type": "checkbox-group"},
        "deny_permissions": {"display_type": "checkbox-group"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "user": {
        "auth_type": {"display_type": "select"},
        "role": {"display_type": "select"},
        "password": {"display_type": "password"},
        "environments": {"display_type": "checkbox-group"},
        "assay_groups": {"display_type": "checkbox-group"},
        "assays": {"display_type": "checkbox-group"},
        "permissions": {"display_type": "checkbox-group"},
        "deny_permissions": {"display_type": "checkbox-group"},
        "must_change_password": {"display_type": "checkbox"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "permission": {
        "tags": {"display_type": "textarea"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
}

RESOURCE_SECTIONS: dict[str, list[tuple[str, list[str]]]] = {
    "asp": [
        (
            "identity",
            [
                "assay_name",
                "display_name",
                "asp_group",
                "asp_family",
                "asp_category",
                "platform",
                "description",
            ],
        ),
        ("gene_content", ["covered_genes", "germline_genes"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "aspc_dna": [
        ("identity", ["assay_name", "environment", "asp_group"]),
        ("analysis", ["analysis_types", "report_sections", "vep_consequences", "cnveffects"]),
        ("advanced_json", ["verification_samples", "query"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "aspc_rna": [
        ("identity", ["assay_name", "environment", "asp_group"]),
        ("analysis", ["analysis_types", "report_sections"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "isgl": [
        ("identity", ["name", "displayname", "list_type", "diagnosis"]),
        ("assignment", ["assay_groups", "assays"]),
        ("gene_content", ["genes"]),
        ("status", ["adhoc", "is_public", "is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "user": [
        ("identity", ["firstname", "lastname", "fullname", "username", "email", "job_title"]),
        ("auth", ["auth_type", "password", "must_change_password"]),
        ("role_access", ["role", "permissions", "deny_permissions"]),
        ("scope", ["environments", "assay_groups", "assays"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "role": [
        ("identity", ["name", "label", "description", "color", "level"]),
        ("permissions", ["permissions", "deny_permissions"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "permission": [
        ("identity", ["permission_name", "label", "category", "description", "tags"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
}

RESOURCE_EXCLUDED_FIELDS: dict[str, set[str]] = {
    "asp": {"asp_id", "version_history"},
    "aspc_dna": {"aspc_id", "version_history"},
    "aspc_rna": {
        "aspc_id",
        "version_history",
        "vep_consequences",
        "cnveffects",
    },
    "isgl": {"isgl_id", "version_history"},
    "user": {
        "version_history",
        "password_updated_on",
        "password_action_token_hash",
        "password_action_purpose",
        "password_action_expires_at",
        "password_action_issued_at",
        "password_action_issued_by",
    },
    "role": {"role_id", "version_history"},
    "permission": {"permission_id", "version_history"},
}


def _section_payload(spec_key: str, fields: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    section_spec = RESOURCE_SECTIONS.get(spec_key, [])
    if not section_spec:
        return {"general": list(fields.keys())}

    sections: dict[str, list[str]] = {}
    used: set[str] = set()
    for section_name, keys in section_spec:
        present = [key for key in keys if key in fields]
        if present:
            sections[section_name] = present
            used.update(present)

    remaining = [key for key in fields if key not in used]
    if remaining:
        sections["advanced"] = remaining
    return sections


def build_managed_schema(spec: ManagedResourceSpec) -> dict[str, Any]:
    """Build a UI schema payload from the managed Pydantic contract."""
    adapter = COLLECTION_MODEL_ADAPTERS[spec.collection]
    model_cls = getattr(adapter, "_type", None)
    if model_cls is None:
        raise ValueError(f"Cannot resolve model for collection '{spec.collection}'")

    fields: dict[str, dict[str, Any]] = {}
    model_fields = getattr(model_cls, "model_fields", {})
    excluded_fields = RESOURCE_EXCLUDED_FIELDS.get(spec.key, set())
    for field_name, field_info in model_fields.items():
        if field_name in excluded_fields:
            continue
        data_type, options = _field_data_type(field_info.annotation)
        display_type = _default_display_type(data_type, options)
        field_payload: dict[str, Any] = {
            "label": field_name.replace("_", " ").title(),
            "data_type": data_type,
            "display_type": display_type,
            "required": bool(field_info.is_required()),
            "placeholder": f"Enter {field_name.replace('_', ' ')}",
        }
        if options:
            field_payload["options"] = options
        if field_info.default is not PydanticUndefined:
            field_payload["default"] = field_info.default
        fields[field_name] = field_payload

    # Admin workflows always stamp metadata; expose them in UI schema payload
    # even if contract models allow them via extra fields.
    metadata_defaults: dict[str, dict[str, Any]] = {
        "created_by": {"data_type": "text", "display_type": "input", "required": False},
        "created_on": {"data_type": "datetime", "display_type": "input", "required": False},
        "updated_by": {"data_type": "text", "display_type": "input", "required": False},
        "updated_on": {"data_type": "datetime", "display_type": "input", "required": False},
        "version": {
            "data_type": "int",
            "display_type": "input",
            "required": False,
            "default": 1,
        },
    }
    for key, shape in metadata_defaults.items():
        if key not in fields:
            fields[key] = {
                "label": key.replace("_", " ").title(),
                "placeholder": f"Enter {key.replace('_', ' ')}",
                **shape,
            }

    for field_name, field_payload in RESOURCE_EXTRA_FIELDS.get(spec.key, {}).items():
        fields[field_name] = deepcopy(field_payload)

    for field_name, override in RESOURCE_FIELD_OVERRIDES.get(spec.key, {}).items():
        if field_name in fields:
            fields[field_name].update(deepcopy(override))

    sections = _section_payload(spec.key, fields)

    return {
        "_id": spec.schema_id,
        "schema_id": spec.schema_id,
        "schema_type": spec.schema_type,
        "schema_category": spec.schema_category,
        "version": spec.contract_version,
        "is_active": True,
        "fields": fields,
        "subschemas": {},
        "sections": sections,
        "source": "backend-contract",
    }


def build_managed_schema_bundle(
    spec: ManagedResourceSpec,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (schemas, selected_schema) in the shape admin routes already expect."""
    selected = build_managed_schema(spec)
    return [deepcopy(selected)], selected
