"""Backend-owned form generation for managed resources."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import PydanticUndefined

from coyote3.contracts.authoring.fields import (
    RESOURCE_EXCLUDED_FIELDS,
    RESOURCE_EXTRA_FIELDS,
    RESOURCE_FIELD_OVERRIDES,
    RESOURCE_SECTIONS,
)
from coyote3.contracts.authoring.resources import ManagedResourceSpec
from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS


def _unwrap_optional(annotation: Any) -> Any:
    """Unwrap a typing.Union that has exactly one non-None member.

    Args:
        annotation: Field annotation to inspect.

    Returns:
        The sole non-None member of a matching union, otherwise the annotation
        unchanged. PEP 604 unions are not explicitly handled.
    """
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _field_data_type(annotation: Any) -> tuple[str, list[Any] | None]:
    """Map a field annotation to a managed-form data type and literal choices.

    Args:
        annotation: Pydantic field annotation before optional unwrapping.

    Returns:
        A data-type key and, for Literal annotations, a list of choices.
        Unsupported annotations fall back to text with no choices.
    """
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
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return "json", None
    return "text", None


def _default_display_type(data_type: str, options: list[Any] | None) -> str:
    """Select the default form control for a data type and available choices.

    Args:
        data_type: Managed-form type key such as bool, json, or list.
        options: Selectable values; None and an empty list mean no choices.

    Returns:
        Checkbox for bool, JSON editor for json, select for nonempty choices,
        textarea for a choice-free list, or input for other types.
    """
    if data_type == "bool":
        return "checkbox"
    if data_type == "json":
        return "jsoneditor"
    if options:
        return "select"
    if data_type == "list":
        return "multi-select" if options else "textarea"
    return "input"


def _section_payload(spec_key: str, fields: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Group available form fields using a resource's configured sections.

    Args:
        spec_key: Resource key used to look up section definitions.
        fields: Available field definitions in display order.

    Returns:
        Nonempty configured sections in declared order, with unassigned fields
        under advanced. Resources without section definitions use general.
    """
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


def build_form_spec(spec: ManagedResourceSpec) -> dict[str, Any]:
    """Build editable fields and readable labels without renaming contract keys.

    Args:
        spec: Registered resource whose collection supplies the Pydantic model.

    Returns:
        Form fields, defaults, sections and resource-specific UI instructions.

    Raises:
        ValueError: If the collection adapter has no resolvable model.
    """
    adapter = COLLECTION_MODEL_ADAPTERS[spec.collection]
    model_cls = getattr(adapter, "_type", None)
    if model_cls is None:
        raise ValueError(f"Cannot resolve model for collection '{spec.collection}'")

    fields: dict[str, dict[str, Any]] = {}
    resource_labels = {
        "asp_id": "Assay ID",
        "asp_ids": "Assays",
        "asp_category": "Modality",
        "asp_group": "Biological group",
        "asp_groups": "Biological groups",
        "asp_family": "Sequencing family",
        "aspc_id": "Configuration ID",
        "isgl_id": "Gene list ID",
    }
    model_fields = getattr(model_cls, "model_fields", {})
    excluded_fields = RESOURCE_EXCLUDED_FIELDS.get(spec.key, set())
    for field_name, field_info in model_fields.items():
        if field_name in {"id_", "id", "_id"}:
            continue
        if field_name in excluded_fields:
            continue
        data_type, options = _field_data_type(field_info.annotation)
        display_type = _default_display_type(data_type, options)
        label = resource_labels.get(field_name, field_name.replace("_", " ").title())
        field_payload: dict[str, Any] = {
            "label": label,
            "data_type": data_type,
            "display_type": display_type,
            "required": bool(field_info.is_required()),
            "placeholder": f"Enter {label.lower()}",
        }
        if options:
            field_payload["options"] = options
        if field_info.default is not PydanticUndefined:
            field_payload["default"] = field_info.default
        fields[field_name] = field_payload

    # Resource workflows always stamp metadata; expose them in the form payload
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

    display_name_fields = {"display_name", "displayname"} & fields.keys()
    display_example, short_example = {
        "asp": ("Example Sequencing Panel", "Example Panel"),
        "aspc_dna": ("Example DNA Base Configuration", "Example DNA Base"),
        "aspc_rna": ("Example RNA Base Configuration", "Example RNA Base"),
        "isgl": ("Myeloid Neoplasm Gene List", "Myeloid genes"),
        "role": ("Clinical Variant Reviewer", "Variant reviewer"),
        "permission": ("View Audit Log", "Audit view"),
    }.get(spec.key, ("Clinical Review", "Review"))
    if "name" in fields and display_name_fields:
        fields["name"]["help"] = (
            "Short name used in tables, dropdowns, filters and compact badges. "
            "Use Display name for the full name shown on cards and detail headings. "
            f"Example: {short_example}."
        )
    for field_name in display_name_fields:
        fields[field_name]["help"] = "Full name shown on cards and detail headings. " + (
            "Tables, dropdowns and filters prefer Name; this full name is the fallback "
            "when no short name is set."
            if "name" in fields
            else "This resource has no separate short name, so its display name is "
            "also used in tables and dropdowns."
        )
        fields[field_name]["help"] += f" Example: {display_example}."

    identity_field = {
        "asp": "asp_id",
        "isgl": "isgl_id",
        "role": "name",
        "permission": "permission_id",
        "user": "username",
    }.get(spec.key)
    if identity_field in fields:
        fields[identity_field].update(readonly=False, readonly_mode=["edit"])
        fields[identity_field].pop("derive_from", None)
    if spec.key.startswith("aspc_"):
        fields["aspc_id"]["help"] = (
            "Generated as assay::diagnosis::environment; for example hematology_gmsv1::mpn::testing."
        )
        fields["analysis_types"]["show_unavailable_options"] = True
        fields["analysis_types"]["help"] = (
            "Available analyses depend on the assay expected input files."
        )
        tier_analysis = "FUSION" if spec.key == "aspc_rna" else "SNV"
        fields["reporting"]["groups"].append(
            {
                "title": "Reportable tiers",
                "fields": [
                    {
                        "key": f"reportable_tiers.{tier_analysis}",
                        "label": f"{tier_analysis} reportable tiers",
                        "type": "checkbox-group",
                        "options": ["1", "2", "3", "4"],
                        "default": [1, 2, 3],
                        "help": "No selected tiers excludes all findings of this type.",
                    }
                ],
            }
        )
        for group in fields["reporting"].get("groups", []):
            for field in group["fields"]:
                if field["key"] == "report_sections":
                    field["options_from_field"] = "analysis_types"
                    field["show_unavailable_options"] = True

    for ownership_field in ("system_managed", "system_installed"):
        if ownership_field not in fields:
            continue
        fields[ownership_field].update(
            {
                "readonly": True,
                "hidden_mode": ["create", "edit"],
                "help": (
                    "Assigned by the application installer. System-installed records "
                    "are read-only; create a separate resource to customize them."
                ),
            }
        )

    sections = _section_payload(spec.key, fields)

    return {
        "form_type": spec.form_type,
        "form_category": spec.form_category,
        "version": spec.contract_version,
        "fields": fields,
        "subschemas": {},
        "sections": sections,
        "source": "backend-contract",
    }
