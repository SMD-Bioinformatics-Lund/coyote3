"""Backend-owned form generation for managed resources."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import PydanticUndefined

from api.config.constants import (
    ALL_SAMPLE_FILE_KEYS,
    ASP_CATEGORY_OPTIONS,
    ASP_FAMILY_OPTIONS,
    ASP_GROUP_OPTIONS,
    AUTH_TYPE_OPTIONS,
    DNA_ANALYSIS_TYPE_OPTIONS,
    ENVIRONMENT_OPTIONS,
    GENELIST_ADHOC_TYPE_OPTIONS,
    GENELIST_STANDARD_TYPE_OPTIONS,
    GENELIST_TYPE_OPTIONS,
    PERMISSION_CATEGORY_OPTIONS,
    PLATFORM_OPTIONS,
    READ_MODE_OPTIONS,
    RNA_ANALYSIS_TYPE_OPTIONS,
    SAMPLE_FILE_KEYS,
    SUBPANEL_BASE_ID,
)
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
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return "json", None
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
    },
    "aspc_rna": {},
}

RESOURCE_FIELD_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "asp": {
        "assay_name": {"display_type": "input"},
        "asp_group": {"display_type": "select", "options": list(ASP_GROUP_OPTIONS)},
        "asp_family": {
            "display_type": "select",
            "options": list(ASP_FAMILY_OPTIONS),
        },
        "asp_category": {"display_type": "select", "options": list(ASP_CATEGORY_OPTIONS)},
        "platform": {"display_type": "select", "options": list(PLATFORM_OPTIONS)},
        "read_mode": {"display_type": "select", "options": list(READ_MODE_OPTIONS)},
        "display_name": {"display_type": "input"},
        "description": {"display_type": "textarea"},
        "expected_files": {
            "display_type": "checkbox-group",
            "options": list(ALL_SAMPLE_FILE_KEYS),
            "category_options": {key: list(values) for key, values in SAMPLE_FILE_KEYS.items()},
            "help": "Files the assay is able to ingest. A declared file must be successfully loaded before the sample becomes ready.",
        },
        "required_files": {
            "display_type": "checkbox-group",
            "options": list(ALL_SAMPLE_FILE_KEYS),
            "category_options": {key: list(values) for key, values in SAMPLE_FILE_KEYS.items()},
            "help": "Minimum files required for this assay. A manifest missing one of these files fails ingest.",
        },
        "covered_genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Assay-level targeted genes. Use canonical HGNC symbols and one symbol per entry.",
        },
        "germline_genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Genes for which the assay applies its configured germline review statement.",
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "aspc_dna": {
        "asp_id": {
            "display_type": "select",
            "label": "ASP",
            "dynamic_options": {"resource": "asp", "value": "asp_id", "label": "display_name"},
        },
        "subpanel_id": {
            "display_type": "select",
            "label": "Subpanel",
            "options": [SUBPANEL_BASE_ID],
            "default": SUBPANEL_BASE_ID,
            "dynamic_options": {
                "resource": "isgl",
                "value": "subpanel_id",
                "label": "displayname",
                "depends_on": "asp_id",
                "include_base": True,
            },
        },
        "aspc_id": {"readonly": True, "derive_from": ["asp_id", "subpanel_id", "environment"]},
        "asp_group": {"readonly": True},
        "asp_category": {"readonly": True},
        "platform": {"readonly": True},
        "use_diagnosis_genelist": {
            "display_type": "checkbox",
            "label": "Auto Select Diagnosis/Sub Panel Genelists",
            "default": True,
        },
        "environment": {
            "display_type": "select",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "analysis_types": {
            "display_type": "checkbox-group",
            "options": list(DNA_ANALYSIS_TYPE_OPTIONS),
            "default": ["SNV", "CNV"],
        },
        "catalog": {
            "data_type": "json",
            "label": "Public Catalog Metadata",
            "display_type": "catalog-structured",
            "groups": [
                {
                    "title": "Public Display",
                    "fields": [
                        {
                            "key": "is_public",
                            "label": "Show In Public Catalog",
                            "type": "checkbox",
                            "default": True,
                        },
                        {
                            "key": "display_order",
                            "label": "Display Order",
                            "type": "int",
                            "default": 100,
                        },
                        {"key": "title", "label": "Catalog Title", "type": "text"},
                        {"key": "description", "label": "Catalog Description", "type": "textarea"},
                    ],
                },
                {
                    "title": "Operational Metadata",
                    "fields": [
                        {"key": "input_material", "label": "Input Material", "type": "text"},
                        {"key": "tat", "label": "Turnaround Time", "type": "text"},
                        {"key": "sample_modes", "label": "Sample Modes", "type": "list"},
                        {
                            "key": "clinical_indications",
                            "label": "Clinical Indications",
                            "type": "list",
                        },
                        {"key": "limitations", "label": "Limitations", "type": "textarea"},
                        {"key": "public_notes", "label": "Public Notes", "type": "textarea"},
                    ],
                },
            ],
        },
        "filters": {
            "data_type": "json",
            "label": "Filters (SNV and CNV strategy)",
            "display_type": "filters-structured",
            "placeholder": "Configure threshold keys for SNV/CNV filtering",
            "groups": [
                {
                    "title": "SNV Thresholds",
                    "fields": [
                        {
                            "key": "min_alt_reads",
                            "label": "Min Alt Reads",
                            "type": "int",
                            "default": 5,
                        },
                        {"key": "min_depth", "label": "Min Depth", "type": "int", "default": 100},
                        {"key": "min_freq", "label": "Min AF", "type": "float", "default": 0.03},
                        {"key": "max_freq", "label": "Max AF", "type": "float", "default": 1.0},
                        {
                            "key": "max_control_freq",
                            "label": "Max Control AF",
                            "type": "float",
                            "default": 0.05,
                        },
                        {
                            "key": "max_popfreq",
                            "label": "Max Population AF",
                            "type": "float",
                            "default": 0.01,
                        },
                    ],
                },
                {
                    "title": "CNV Thresholds",
                    "fields": [
                        {
                            "key": "min_cnv_size",
                            "label": "Min CNV Size",
                            "type": "int",
                            "default": 100,
                        },
                        {
                            "key": "max_cnv_size",
                            "label": "Max CNV Size",
                            "type": "int",
                            "default": 1000000,
                        },
                        {
                            "key": "cnv_loss_cutoff",
                            "label": "CNV Loss Cutoff",
                            "type": "float",
                            "default": -0.3,
                        },
                        {
                            "key": "cnv_gain_cutoff",
                            "label": "CNV Gain Cutoff",
                            "type": "float",
                            "default": 0.3,
                        },
                        {
                            "key": "warn_cov",
                            "label": "Warn Coverage",
                            "type": "int",
                            "default": 500,
                        },
                        {
                            "key": "error_cov",
                            "label": "Error Coverage",
                            "type": "int",
                            "default": 100,
                        },
                    ],
                },
                {
                    "title": "Gene Scope And Consequences",
                    "fields": [
                        {
                            "key": "vep_consequences",
                            "label": "VEP Consequences",
                            "type": "checkbox-group",
                            "options": [],
                            "dynamic_options": {"resource": "vep_consequence_groups"},
                        },
                        {
                            "key": "snvlists",
                            "label": "SNV Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                            "dynamic_options": {
                                "resource": "isgl",
                                "filter": {"list_type": "snv", "adhoc": False},
                                "value": "isgl_id",
                                "label": "displayname",
                            },
                        },
                        {
                            "key": "cnvlists",
                            "label": "CNV Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                            "dynamic_options": {
                                "resource": "isgl",
                                "filter": {"list_type": "cnv", "adhoc": False},
                                "value": "isgl_id",
                                "label": "displayname",
                            },
                        },
                        {
                            "key": "cnveffects",
                            "label": "CNV Effects (gain/loss)",
                            "type": "checkbox-group",
                            "options": ["gain", "loss"],
                            "default": ["gain", "loss"],
                        },
                    ],
                },
            ],
        },
        "reporting": {
            "display_type": "reporting-structured",
            "groups": [
                {
                    "title": "Report Sections",
                    "fields": [
                        {
                            "key": "report_sections",
                            "label": "Report Sections",
                            "type": "checkbox-group",
                            "options": list(DNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["SNV", "CNV"],
                        },
                        {
                            "key": "analysis",
                            "label": "Available Analysis",
                            "type": "checkbox-group",
                            "options": list(DNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["SNV", "CNV"],
                        },
                    ],
                },
                {
                    "title": "Report Text",
                    "fields": [
                        {
                            "key": "report_header",
                            "label": "Report Header",
                            "type": "text",
                            "default": "Coyote3 DNA Report",
                        },
                        {
                            "key": "report_method",
                            "label": "Report Method",
                            "type": "text",
                            "default": "NGS panel analysis",
                        },
                        {
                            "key": "report_description",
                            "label": "Report Description",
                            "type": "textarea",
                            "default": "DNA panel summary report",
                        },
                        {
                            "key": "general_report_summary",
                            "label": "General Summary",
                            "type": "textarea",
                            "default": "Automated summary generated from configured assay filters.",
                        },
                    ],
                },
                {
                    "title": "Clinical Rule Release",
                    "fields": [
                        {
                            "key": "clinical_rule_release",
                            "label": "Published Clinical Rule Release",
                            "type": "clinical-rule-release",
                            "required": True,
                            "help": (
                                "Select the published YAML release that matches this ASP and subpanel. "
                                "The selected release is stored as an immutable reporting reference."
                            ),
                        },
                    ],
                },
                {
                    "title": "Report Paths",
                    "fields": [
                        {
                            "key": "plots_path",
                            "label": "Plots Path",
                            "type": "text",
                            "default": "/tmp",
                        },
                        {
                            "key": "report_folder",
                            "label": "Report Folder",
                            "type": "text",
                            "default": "reports",
                        },
                    ],
                },
            ],
        },
        "verification_samples": {"display_type": "jsoneditor"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "aspc_rna": {
        "asp_id": {
            "display_type": "select",
            "label": "ASP",
            "dynamic_options": {"resource": "asp", "value": "asp_id", "label": "display_name"},
        },
        "subpanel_id": {
            "display_type": "select",
            "label": "Subpanel",
            "options": [SUBPANEL_BASE_ID],
            "default": SUBPANEL_BASE_ID,
            "dynamic_options": {
                "resource": "isgl",
                "value": "subpanel_id",
                "label": "displayname",
                "depends_on": "asp_id",
                "include_base": True,
            },
        },
        "aspc_id": {"readonly": True, "derive_from": ["asp_id", "subpanel_id", "environment"]},
        "asp_group": {"readonly": True},
        "asp_category": {"readonly": True},
        "platform": {"readonly": True},
        "use_diagnosis_genelist": {
            "display_type": "checkbox",
            "label": "Auto Select Diagnosis/Sub Panel Genelists",
            "default": True,
        },
        "environment": {
            "display_type": "select",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "analysis_types": {
            "display_type": "checkbox-group",
            "options": list(RNA_ANALYSIS_TYPE_OPTIONS),
            "default": ["FUSION"],
        },
        "catalog": {
            "data_type": "json",
            "label": "Public Catalog Metadata",
            "display_type": "catalog-structured",
            "groups": [
                {
                    "title": "Public Display",
                    "fields": [
                        {
                            "key": "is_public",
                            "label": "Show In Public Catalog",
                            "type": "checkbox",
                            "default": True,
                        },
                        {
                            "key": "display_order",
                            "label": "Display Order",
                            "type": "int",
                            "default": 100,
                        },
                        {"key": "title", "label": "Catalog Title", "type": "text"},
                        {"key": "description", "label": "Catalog Description", "type": "textarea"},
                    ],
                },
                {
                    "title": "Operational Metadata",
                    "fields": [
                        {"key": "input_material", "label": "Input Material", "type": "text"},
                        {"key": "tat", "label": "Turnaround Time", "type": "text"},
                        {"key": "sample_modes", "label": "Sample Modes", "type": "list"},
                        {
                            "key": "clinical_indications",
                            "label": "Clinical Indications",
                            "type": "list",
                        },
                        {"key": "limitations", "label": "Limitations", "type": "textarea"},
                        {"key": "public_notes", "label": "Public Notes", "type": "textarea"},
                    ],
                },
            ],
        },
        "filters": {
            "data_type": "json",
            "label": "Filters (Fusion strategy)",
            "display_type": "filters-structured",
            "placeholder": "Configure RNA thresholds and fusion_* strategy keys",
            "groups": [
                {
                    "title": "Fusion Thresholds",
                    "fields": [
                        {
                            "key": "min_spanning_reads",
                            "label": "Min Spanning Reads",
                            "type": "int",
                            "default": 5,
                        },
                        {
                            "key": "min_spanning_pairs",
                            "label": "Min Spanning Pairs",
                            "type": "int",
                            "default": 5,
                        },
                    ],
                },
                {
                    "title": "Fusion Lists",
                    "fields": [
                        {
                            "key": "fusion_callers",
                            "label": "Fusion Callers",
                            "type": "checkbox-group",
                            "options": ["arriba", "starfusion", "fusioncatcher"],
                            "default": ["arriba", "starfusion"],
                        },
                        {
                            "key": "fusion_effects",
                            "label": "Fusion Effects",
                            "type": "checkbox-group",
                            "options": ["in-frame", "out-of-frame"],
                            "default": ["in-frame", "out-of-frame"],
                        },
                        {
                            "key": "fusionlists",
                            "label": "Fusion Gene Lists",
                            "type": "checkbox-group",
                            "options": [],
                            "disabled": True,
                            "help": "TODO: define fusion genelist partner/breakpoint schema before enabling this selector.",
                        },
                    ],
                },
            ],
        },
        "reporting": {
            "display_type": "reporting-structured",
            "groups": [
                {
                    "title": "Report Sections",
                    "fields": [
                        {
                            "key": "report_sections",
                            "label": "Report Sections",
                            "type": "checkbox-group",
                            "options": list(RNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["FUSION"],
                        },
                        {
                            "key": "analysis",
                            "label": "Available Analysis",
                            "type": "checkbox-group",
                            "options": list(RNA_ANALYSIS_TYPE_OPTIONS),
                            "default": ["FUSION"],
                        },
                    ],
                },
                {
                    "title": "Report Text",
                    "fields": [
                        {
                            "key": "report_header",
                            "label": "Report Header",
                            "type": "text",
                            "default": "Coyote3 RNA Report",
                        },
                        {
                            "key": "report_method",
                            "label": "Report Method",
                            "type": "text",
                            "default": "RNA fusion analysis",
                        },
                        {
                            "key": "report_description",
                            "label": "Report Description",
                            "type": "textarea",
                            "default": "RNA fusion summary report",
                        },
                        {
                            "key": "general_report_summary",
                            "label": "General Summary",
                            "type": "textarea",
                            "default": "Automated summary generated from configured assay filters.",
                        },
                    ],
                },
                {
                    "title": "Clinical Rule Release",
                    "fields": [
                        {
                            "key": "clinical_rule_release",
                            "label": "Published Clinical Rule Release",
                            "type": "clinical-rule-release",
                            "required": True,
                            "help": (
                                "Select the published YAML release that matches this ASP and subpanel. "
                                "The selected release is stored as an immutable reporting reference."
                            ),
                        },
                    ],
                },
                {
                    "title": "Report Paths",
                    "fields": [
                        {
                            "key": "plots_path",
                            "label": "Plots Path",
                            "type": "text",
                            "default": "/tmp",
                        },
                        {
                            "key": "report_folder",
                            "label": "Report Folder",
                            "type": "text",
                            "default": "reports",
                        },
                    ],
                },
            ],
        },
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "isgl": {
        "list_type": {
            "display_type": "checkbox-group",
            "options": list(GENELIST_TYPE_OPTIONS),
            "conditional_options": {
                "field": "adhoc",
                "truthy": list(GENELIST_ADHOC_TYPE_OPTIONS),
                "falsy": list(GENELIST_STANDARD_TYPE_OPTIONS),
            },
            "help": "Choose the clinical analysis domain. Ad-hoc lists expose only ad-hoc list types; curated lists expose only standard list types.",
        },
        "subpanel_id": {
            "display_type": "input",
            "default": SUBPANEL_BASE_ID,
            "help": "Use 'base' for global assay lists, or a clinical subpanel identifier such as myeloid.",
        },
        "diagnosis": {"display_type": "textarea"},
        "assay_groups": {"display_type": "checkbox-group", "options": list(ASP_GROUP_OPTIONS)},
        "assays": {
            "display_type": "checkbox-group",
            "dynamic_options": {"resource": "asp", "value": "asp_id", "label": "display_name"},
        },
        "genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Curated gene symbols for the selected clinical list type, one per entry.",
        },
        "germline_genes": {
            "display_type": "jsoneditor-or-upload",
            "help": "Optional germline subset associated with this curated list.",
        },
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
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "user": {
        "auth_type": {"display_type": "checkbox-group", "options": list(AUTH_TYPE_OPTIONS)},
        "roles": {"display_type": "checkbox-group"},
        "username": {"readonly_mode": ["edit"]},
        "password": {"display_type": "password"},
        "environments": {
            "display_type": "checkbox-group",
            "options": list(ENVIRONMENT_OPTIONS),
        },
        "assay_groups": {"display_type": "checkbox-group", "options": list(ASP_GROUP_OPTIONS)},
        "assays": {"display_type": "checkbox-group"},
        "must_change_password": {"display_type": "checkbox"},
        "is_active": {"display_type": "checkbox", "default": True},
        "created_by": {"readonly": True},
        "created_on": {"readonly": True},
        "updated_by": {"readonly": True},
        "updated_on": {"readonly": True},
        "version": {"readonly": True},
    },
    "permission": {
        "category": {"display_type": "select", "options": list(PERMISSION_CATEGORY_OPTIONS)},
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
            "assay identity",
            [
                "assay_name",
                "display_name",
                "asp_group",
                "asp_family",
                "asp_category",
                "platform",
                "read_mode",
                "description",
            ],
        ),
        (
            "ingest contract",
            [
                "expected_files",
                "required_files",
            ],
        ),
        ("clinical gene scope", ["covered_genes", "germline_genes"]),
        ("lifecycle", ["is_active"]),
        ("record history", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "aspc_dna": [
        (
            "configuration scope",
            ["asp_id", "subpanel_id", "environment", "asp_group", "asp_category"],
        ),
        ("enabled analysis", ["analysis_types"]),
        ("analytical filters", ["filters"]),
        ("clinical reporting", ["reporting"]),
        ("public catalog", ["catalog"]),
        ("verification", ["verification_samples"]),
        ("lifecycle", ["is_active"]),
        ("record history", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "aspc_rna": [
        (
            "configuration scope",
            ["asp_id", "subpanel_id", "environment", "asp_group", "asp_category"],
        ),
        ("enabled analysis", ["analysis_types"]),
        ("analytical filters", ["filters"]),
        ("clinical reporting", ["reporting"]),
        ("public catalog", ["catalog"]),
        ("lifecycle", ["is_active"]),
        ("record history", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "isgl": [
        ("list identity", ["name", "displayname", "list_type", "diagnosis"]),
        ("clinical scope", ["subpanel_id", "assay_groups", "assays"]),
        ("curated gene content", ["genes", "germline_genes"]),
        ("availability", ["adhoc", "is_public", "is_active"]),
        ("record history", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "user": [
        ("identity", ["firstname", "lastname", "fullname", "username", "email", "job_title"]),
        ("auth", ["auth_type", "password", "must_change_password"]),
        ("role_access", ["roles"]),
        ("scope", ["environments", "assay_groups", "assays"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "role": [
        ("identity", ["name", "label", "description", "color", "level"]),
        ("permissions", ["permissions"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
    "permission": [
        ("identity", ["permission_id", "label", "category", "description", "tags"]),
        ("status", ["is_active"]),
        ("metadata", ["created_by", "created_on", "updated_by", "updated_on", "version"]),
    ],
}

RESOURCE_EXCLUDED_FIELDS: dict[str, set[str]] = {
    "asp": {"asp_id", "version_history"},
    "aspc_dna": {"id_", "version_history"},
    "aspc_rna": {
        "id_",
        "version_history",
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
    "permission": {"version_history"},
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


def build_form_spec(spec: ManagedResourceSpec) -> dict[str, Any]:
    """Build a form payload from the managed Pydantic contract."""
    adapter = COLLECTION_MODEL_ADAPTERS[spec.collection]
    model_cls = getattr(adapter, "_type", None)
    if model_cls is None:
        raise ValueError(f"Cannot resolve model for collection '{spec.collection}'")

    fields: dict[str, dict[str, Any]] = {}
    model_fields = getattr(model_cls, "model_fields", {})
    excluded_fields = RESOURCE_EXCLUDED_FIELDS.get(spec.key, set())
    for field_name, field_info in model_fields.items():
        if field_name in {"id_", "id", "_id"}:
            continue
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
