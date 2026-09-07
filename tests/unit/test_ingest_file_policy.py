"""Tests for ASP/ASPC-owned ingest file policy validation."""

from pathlib import Path

import pytest

from api.application.ingest.file_policy import (
    assay_file_policy,
    validate_declared_file_resources,
    validate_payload_file_keys,
)


class FakeCollection:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def find_one(self, query: dict):
        return next(
            (
                document
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )


def resolver(*, panels: list[dict], configurations: list[dict]):
    collections = {
        "assay_specific_panels": FakeCollection(panels),
        "asp_configs": FakeCollection(configurations),
    }
    return collections.__getitem__


def dna_panel(**overrides):
    return {
        "asp_id": "panel_a",
        "asp_category": "dna",
        "expected_files": ["vcf_files", "cnv"],
        "required_files": ["vcf_files"],
        **overrides,
    }


def active_aspc(**overrides):
    return {
        "aspc_id": "panel_a_base_production",
        "asp_id": "panel_a",
        "subpanel_id": "base",
        "environment": "production",
        "analysis_types": ["SNV"],
        "is_active": True,
        **overrides,
    }


def test_assay_file_policy_requires_registered_consistent_asp():
    collection = resolver(panels=[], configurations=[])

    with pytest.raises(ValueError, match="assay is required"):
        assay_file_policy(collection, assay_name=None, omics_layer="dna")
    with pytest.raises(ValueError, match="ASP is not registered"):
        assay_file_policy(collection, assay_name="panel_a", omics_layer="dna")

    inconsistent = resolver(
        panels=[dna_panel(required_files=["vcf_files", "cov"])], configurations=[]
    )
    with pytest.raises(ValueError, match="required_files outside expected_files"):
        assay_file_policy(inconsistent, assay_name="panel_a", omics_layer="dna")


def test_payload_rejects_files_outside_asp_contract():
    collection = resolver(panels=[dna_panel()], configurations=[active_aspc()])

    with pytest.raises(ValueError, match="does not accept declared ingest file"):
        validate_payload_file_keys(
            collection,
            {
                "asp_id": "panel_a",
                "omics_layer": "dna",
                "files": {"vcf_files": "/data/sample.vcf", "cov": "/data/sample.cov.json"},
            },
        )


def test_declared_resources_use_base_aspc_and_validate_paths(tmp_path: Path):
    vcf = tmp_path / "sample.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    collection = resolver(panels=[dna_panel()], configurations=[active_aspc()])
    payload = {
        "asp_id": "panel_a",
        "subpanel_id": "not_configured",
        "environment": "production",
        "omics_layer": "dna",
        "files": {"vcf_files": str(vcf)},
    }

    assert validate_declared_file_resources(collection, payload) == {"vcf_files"}


def test_declared_resources_reject_missing_unreadable_and_invalid_analysis(tmp_path: Path):
    collection = resolver(panels=[dna_panel()], configurations=[active_aspc()])
    base_payload = {
        "asp_id": "panel_a",
        "subpanel_id": "base",
        "environment": "production",
        "omics_layer": "dna",
        "files": {},
    }

    with pytest.raises(ValueError, match="Missing required ingest file"):
        validate_declared_file_resources(collection, base_payload)

    unreadable = {**base_payload, "files": {"vcf_files": str(tmp_path / "missing.vcf")}}
    with pytest.raises(FileNotFoundError, match="not readable"):
        validate_declared_file_resources(collection, unreadable)

    incompatible = resolver(
        panels=[dna_panel()],
        configurations=[active_aspc(analysis_types=["SNV", "COVERAGE"])],
    )
    with pytest.raises(ValueError, match="not declared by the ASP"):
        validate_declared_file_resources(incompatible, unreadable)


def test_declared_resources_require_active_aspc():
    collection = resolver(panels=[dna_panel()], configurations=[])

    with pytest.raises(ValueError, match="No active ASPC"):
        validate_declared_file_resources(
            collection,
            {
                "asp_id": "panel_a",
                "subpanel_id": "base",
                "environment": "production",
                "omics_layer": "dna",
            },
        )
