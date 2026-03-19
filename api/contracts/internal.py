"""Internal API route contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RoleLevelsPayload(BaseModel):
    """Represent the role levels payload."""

    status: str
    role_levels: dict[str, int]


class IsglMetaPayload(BaseModel):
    """Represent the isgl meta payload."""

    status: str
    isgl_id: str
    is_adhoc: bool
    display_name: str | None = None


class InternalIngestDependentsRequest(BaseModel):
    """Represent internal dependent-data ingest request payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sample_id": "65f0c0ffee00000000000001",
                "sample_name": "DEMO_SAMPLE_001",
                "delete_existing": True,
                "preload": {"cnvs": [{"chr": "7", "start": 1, "end": 2}]},
            }
        }
    )

    sample_id: str
    sample_name: str
    delete_existing: bool = False
    preload: dict[str, Any]


class InternalIngestDependentsPayload(BaseModel):
    """Represent internal dependent-data ingest response payload."""

    status: str
    sample_id: str
    written: dict[str, int]


class InternalSampleIngestSpec(BaseModel):
    """Represent structured fields for sample-bundle ingestion."""

    model_config = ConfigDict(extra="allow")

    name: str
    genome_build: int | None = None
    assay: str | None = None
    profile: str | None = None
    subpanel: str | None = None
    vcf_files: str | None = None
    cnv: str | None = None
    biomarkers: str | None = None
    transloc: str | None = None
    lowcov: str | None = None
    cov: str | None = None
    fusion_files: str | None = None
    expression_path: str | None = None
    classification_path: str | None = None
    qc: str | None = None
    increment: bool = False


class InternalIngestSampleBundleRequest(BaseModel):
    """Represent internal sample+analysis bundle ingest request payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "spec": {
                        "name": "DEMO_SAMPLE_001",
                        "assay": "ASSAY_A",
                        "profile": "test",
                        "genome_build": 38,
                        "vcf_files": "/data/demo.vcf",
                    },
                    "update_existing": False,
                },
                {
                    "yaml_content": "name: DEMO_SAMPLE_001\nassay: ASSAY_A\nprofile: test\n",
                    "update_existing": False,
                },
            ]
        }
    )

    spec: InternalSampleIngestSpec | None = None
    yaml_content: str | None = None
    update_existing: bool = False


class InternalIngestSampleBundlePayload(BaseModel):
    """Represent internal sample+analysis bundle ingest response payload."""

    status: str
    sample_id: str
    sample_name: str
    written: dict[str, int]
    data_counts: dict[str, int | bool]


class InternalCollectionInsertRequest(BaseModel):
    """Represent request body for single document insert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection": "users",
                "document": {
                    "email": "admin@your-center.org",
                    "fullname": "Center Admin",
                    "role": "admin",
                    "is_active": True,
                },
                "ignore_duplicate": True,
            }
        }
    )

    collection: str
    document: dict[str, Any]
    ignore_duplicate: bool = False


class InternalCollectionBulkInsertRequest(BaseModel):
    """Represent request body for bulk document insert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection": "refseq_canonical",
                "documents": [
                    {"gene": "EGFR", "canonical": "NM_005228"},
                    {"gene": "TP53", "canonical": "NM_000546"},
                ],
                "ignore_duplicates": True,
            }
        }
    )

    collection: str
    documents: list[dict[str, Any]]
    ignore_duplicates: bool = False


class InternalCollectionInsertPayload(BaseModel):
    """Represent collection insert response payload."""

    status: str
    collection: str
    inserted_count: int
    inserted_id: str | None = None


class InternalCollectionSupportPayload(BaseModel):
    """Represent supported collection list response payload."""

    status: str
    collections: list[str]
