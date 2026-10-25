"""Immutable operational and integration contracts owned by Coyote3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class PipelineManifestContract:
    """Translate stable external pipeline fields at the ingest boundary."""

    field_aliases: dict[str, str]


@dataclass(frozen=True)
class NotificationContract:
    """Stable notification values shared by API validation and the UI."""

    tones: frozenset[str]
    categories: frozenset[str]


APP_CONTROLS_ID: Final = "default"
PIPELINE_MANIFEST: Final = PipelineManifestContract(
    field_aliases={
        "assay": "asp_id",
        "diagnosis": "diagnosis_id",
        "profile": "environment",
        "sequencing_technology": "platform",
    }
)
NOTIFICATIONS: Final = NotificationContract(
    tones=frozenset({"success", "info", "warning", "error"}),
    categories=frozenset({"application", "feature", "maintenance", "security", "warning"}),
)
