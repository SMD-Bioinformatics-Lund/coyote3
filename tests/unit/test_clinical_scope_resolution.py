"""Clinical scope canonicalization and ASPC fallback regression coverage."""

from __future__ import annotations

import pytest

from coyote3.application.common.release_resources import capture_assay_resource
from coyote3.application.ingest.helpers import assay_default_filters
from coyote3.config.constants import normalize_clinical_identifier
from coyote3.contracts.schemas.samples import SampleAspcResolutionDoc


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
    assert normalize_clinical_identifier("Hem-Snabb", label="diagnosis_id") == "hem-snabb"
    assert normalize_clinical_identifier("GMS_BarnCancer", label="isgl_id") == "gms_barncancer"
    with pytest.raises(ValueError, match="only letters, digits, underscores, and hyphens"):
        normalize_clinical_identifier("GMS BarnCancer V1.0", label="isgl_id")


def test_base_aspc_is_explicitly_recorded_when_diagnosis_configuration_is_absent():
    """Base fallback retains the requested diagnosis and records the scope warning."""
    collection = _Collection(
        [
            {
                "_id": "aspc-base",
                "aspc_id": "hema_gmsv1_base_production",
                "asp_id": "hema_gmsv1",
                "diagnosis_id": "base",
                "assay_resource_release": capture_assay_resource(
                    {
                        "asp_id": "hema_gmsv1",
                        "asp_group": "hematology",
                        "asp_family": "panel-dna",
                        "asp_category": "dna",
                        "version": 1,
                    }
                ),
                "environment": "production",
                "is_active": True,
                "analysis_intents": ["somatic"],
                "asp_group": "hematology",
                "analysis_types": ["SNV"],
                "version": 1,
                "filters": {"somatic": {"snv": {}}},
            }
        ]
    )

    resolved = assay_default_filters(
        collection.find_one,
        {
            "asp_id": "hema_GMSv1",
            "diagnosis_id": "Hem-Snabb",
            "environment": "production",
            "asp_category": "dna",
        },
    )

    assert resolved is not None
    assert resolved["aspc"]["aspc_id"] == "hema_gmsv1_base_production"
    assert SampleAspcResolutionDoc.from_resolution(resolved["aspc_resolution"]).model_dump() == {
        "resolved_diagnosis_id": "base",
        "used_base_configuration": True,
        "warning": "No diagnosis-specific ASPC is active; base configuration is in use.",
    }
    assert resolved["aspc_resolution"] == {
        "context": {
            "group_id": "hematology",
            "assay_id": "hema_gmsv1",
            "assay_revision": 1,
            "modality": "dna",
            "family": "panel-dna",
            "diagnosis_id": "hem-snabb",
            "environment": "production",
            "configuration_id": "hema_gmsv1_base_production",
            "configuration_revision": 1,
            "analyses": ["SNV"],
            "intents": ["somatic"],
            "reference_genome": None,
        },
        "requested_diagnosis_id": "hem-snabb",
        "resolved_diagnosis_id": "base",
        "used_base_configuration": True,
        "warning": "No diagnosis-specific ASPC is active; base configuration is in use.",
    }
