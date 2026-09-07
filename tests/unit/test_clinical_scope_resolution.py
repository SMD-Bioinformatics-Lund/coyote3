"""Clinical scope canonicalization and ASPC fallback regression coverage."""

from __future__ import annotations

import pytest

from api.application.ingest.helpers import assay_default_filters_from_aspc_collection
from api.config.constants import normalize_clinical_identifier


class _Collection:
    """Minimal in-memory collection for exact ASPC lookups."""

    def __init__(self, documents: list[dict]):
        self.documents = documents

    def find_one(self, query: dict) -> dict | None:
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None


def test_clinical_identifiers_lowercase_and_preserve_accepted_separators():
    """Clinical join keys preserve hyphens and underscores but reject special characters."""
    assert normalize_clinical_identifier("Hem-Snabb", label="subpanel_id") == "hem-snabb"
    assert normalize_clinical_identifier("GMS_BarnCancer", label="isgl_id") == "gms_barncancer"
    with pytest.raises(ValueError, match="only letters, digits, underscores, and hyphens"):
        normalize_clinical_identifier("GMS BarnCancer V1.0", label="isgl_id")


def test_base_aspc_is_explicitly_recorded_when_subpanel_configuration_is_absent():
    """A legacy subpanel resolves to base and exposes a user-visible warning."""
    collection = _Collection(
        [
            {
                "_id": "aspc-base",
                "aspc_id": "hema_gmsv1_base_production",
                "asp_id": "hema_gmsv1",
                "subpanel_id": "base",
                "environment": "production",
                "is_active": True,
                "analysis_intents": ["somatic"],
                "filters": {"somatic": {"snv": {}}},
            }
        ]
    )

    resolved = assay_default_filters_from_aspc_collection(
        collection,
        {
            "asp_id": "hema_GMSv1",
            "subpanel_id": "Hem-Snabb",
            "environment": "production",
            "omics_layer": "dna",
        },
    )

    assert resolved is not None
    assert resolved["aspc"]["aspc_id"] == "hema_gmsv1_base_production"
    assert resolved["aspc_resolution"] == {
        "requested_subpanel_id": "hem-snabb",
        "resolved_subpanel_id": "base",
        "used_base_configuration": True,
        "warning": "No subpanel-specific ASPC is active; base configuration is in use.",
    }
