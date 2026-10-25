"""Allowed individual metadata keys for resource integration endpoints."""

from datetime import datetime
from typing import Literal

FieldValue = str | bool | int | datetime | list[str] | None

SampleField = Literal[
    "name",
    "asp_id",
    "asp_group",
    "diagnosis_id",
    "environment",
    "asp_category",
    "asp_family",
    "ingest_status",
    "reported",
    "version",
    "time_added",
]
AssayField = Literal[
    "asp_id",
    "display_name",
    "asp_group",
    "asp_category",
    "asp_family",
    "platform",
    "is_active",
    "version",
    "supported_analyses",
    "expected_files",
    "required_files",
]
ConfigurationField = Literal[
    "aspc_id",
    "display_name",
    "asp_id",
    "asp_group",
    "diagnosis_id",
    "environment",
    "asp_category",
    "platform",
    "reference_genome",
    "is_active",
    "version",
    "analysis_types",
    "report_sections",
]
GroupField = Literal["group_id", "display_name", "parent_group_id", "is_active", "version"]
DiagnosisField = Literal[
    "diagnosis_id",
    "display_name",
    "description",
    "is_active",
    "version",
    "asp_ids",
]
GeneListField = Literal[
    "isgl_id",
    "displayname",
    "name",
    "list_type",
    "diagnosis",
    "asp_ids",
    "asp_groups",
    "gene_count",
    "is_active",
    "is_public",
    "adhoc",
    "version",
]
