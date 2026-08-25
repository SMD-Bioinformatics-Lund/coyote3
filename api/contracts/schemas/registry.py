"""Collection-to-model contract registry."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from api.contracts.schemas.app_controls import AppControlsDoc
from api.contracts.schemas.assay import (
    AspConfigDoc,
    AssayPanelToAssayGroupMappingDoc,
    AssaySpecificPanelsDoc,
    BlacklistDoc,
    InsilicoGenelistsDoc,
)
from api.contracts.schemas.dna import (
    BiomarkersDoc,
    CnvsDoc,
    GroupCoverageDoc,
    PanelCovDoc,
    PgxDoc,
    ReportedVariantsDoc,
    TranslocationsDoc,
    VariantsDoc,
)
from api.contracts.schemas.governance import PermissionsDoc, RolesDoc, UsersDoc
from api.contracts.schemas.reference import (
    AnnotationDoc,
    AnnoVepDoc,
    BrcaExchangeDoc,
    CivicGenesDoc,
    CivicVariantsDoc,
    ClinPgxGenesPublicDoc,
    CosmicDoc,
    DashboardMetricsDoc,
    HgncGenesDoc,
    HpaExprDoc,
    IarcTp53Doc,
    ManeSelectDoc,
    OncoKbActionableDoc,
    OncoKbCancerGenesPublicDoc,
    OncoKbGenesDoc,
    OncoKbGenesPublicDoc,
    OncoKbPublicDoc,
    VepMetadataDoc,
)
from api.contracts.schemas.rna import FusionsDoc, RnaClassificationDoc, RnaExpressionDoc, RnaQcDoc
from api.contracts.schemas.samples import SampleCommentRecordDoc, SampleReportRecordDoc, SamplesDoc

COLLECTION_MODEL_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "samples": TypeAdapter(SamplesDoc),
    "sample_comments": TypeAdapter(SampleCommentRecordDoc),
    "reports": TypeAdapter(SampleReportRecordDoc),
    "variants": TypeAdapter(VariantsDoc),
    "anno_vep": TypeAdapter(AnnoVepDoc),
    "cnvs": TypeAdapter(CnvsDoc),
    "translocations": TypeAdapter(TranslocationsDoc),
    "biomarkers": TypeAdapter(BiomarkersDoc),
    "pgx": TypeAdapter(PgxDoc),
    "panel_coverage": TypeAdapter(PanelCovDoc),
    "fusions": TypeAdapter(FusionsDoc),
    "rna_expression": TypeAdapter(RnaExpressionDoc),
    "rna_classification": TypeAdapter(RnaClassificationDoc),
    "rna_qc": TypeAdapter(RnaQcDoc),
    "users": TypeAdapter(UsersDoc),
    "roles": TypeAdapter(RolesDoc),
    "permissions": TypeAdapter(PermissionsDoc),
    "annotation": TypeAdapter(AnnotationDoc),
    "reported_variants": TypeAdapter(ReportedVariantsDoc),
    "asp_configs": TypeAdapter(AspConfigDoc),
    "assay_specific_panels": TypeAdapter(AssaySpecificPanelsDoc),
    "insilico_genelists": TypeAdapter(InsilicoGenelistsDoc),
    "blacklist": TypeAdapter(BlacklistDoc),
    "brcaexchange": TypeAdapter(BrcaExchangeDoc),
    "civic_genes": TypeAdapter(CivicGenesDoc),
    "civic_variants": TypeAdapter(CivicVariantsDoc),
    "cosmic": TypeAdapter(CosmicDoc),
    "dashboard_metrics": TypeAdapter(DashboardMetricsDoc),
    "group_coverage": TypeAdapter(GroupCoverageDoc),
    "hgnc_genes": TypeAdapter(HgncGenesDoc),
    "hpaexpr": TypeAdapter(HpaExprDoc),
    "iarc_tp53": TypeAdapter(IarcTp53Doc),
    "mane_select": TypeAdapter(ManeSelectDoc),
    "oncokb_actionable": TypeAdapter(OncoKbActionableDoc),
    "oncokb_genes": TypeAdapter(OncoKbGenesDoc),
    "oncokb_public": TypeAdapter(OncoKbPublicDoc),
    "oncokb_genes_public": TypeAdapter(OncoKbGenesPublicDoc),
    "oncokb_cancer_genes_public": TypeAdapter(OncoKbCancerGenesPublicDoc),
    "clinpgx_genes_public": TypeAdapter(ClinPgxGenesPublicDoc),
    "vep_metadata": TypeAdapter(VepMetadataDoc),
    "asp_to_groups": TypeAdapter(AssayPanelToAssayGroupMappingDoc),
    "app_controls": TypeAdapter(AppControlsDoc),
}

INGEST_DEPENDENT_COLLECTIONS: dict[str, str] = {
    "snvs": "variants",
    "cnvs": "cnvs",
    "biomarkers": "biomarkers",
    "pgx": "pgx",
    "transloc": "translocations",
    "cov": "panel_coverage",
    "fusions": "fusions",
    "rna_expr": "rna_expression",
    "rna_class": "rna_classification",
    "rna_qc": "rna_qc",
}

INGEST_SINGLE_DOCUMENT_KEYS: frozenset[str] = frozenset(
    {"biomarkers", "pgx", "cov", "rna_expr", "rna_class", "rna_qc"}
)


def validate_collection_document(collection: str, payload: dict[str, Any]) -> None:
    """Validate one document against the mapped collection model."""
    adapter = COLLECTION_MODEL_ADAPTERS.get(collection)
    if not adapter:
        raise ValueError(f"No DB document model registered for collection '{collection}'")
    adapter.validate_python(payload)


def normalize_collection_document(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and return normalized payload for collection writes."""
    adapter = COLLECTION_MODEL_ADAPTERS.get(collection)
    if not adapter:
        raise ValueError(f"No DB document model registered for collection '{collection}'")
    parsed = adapter.validate_python(payload)
    normalized = parsed.model_dump(by_alias=True)
    if collection == "annotation":
        from api.domain.core.annotation_identity import (
            ANNOTATION_CONTEXT_FIELDS,
            ANNOTATION_IDENTITY_FIELDS,
            NOMENCLATURE_FIELDS,
            NOMENCLATURE_REQUIRED_FIELDS,
        )

        allowed = NOMENCLATURE_FIELDS[parsed.nomenclature]
        required = NOMENCLATURE_REQUIRED_FIELDS[parsed.nomenclature]
        for field in (*ANNOTATION_IDENTITY_FIELDS, *ANNOTATION_CONTEXT_FIELDS):
            if field not in allowed:
                normalized.pop(field, None)
            elif field not in required and field not in parsed.model_fields_set:
                normalized.pop(field, None)
        if normalized.get("class") is not None:
            normalized.pop("text", None)
        else:
            normalized.pop("class", None)
    if normalized.get("_id") is None:
        normalized.pop("_id", None)
    return normalized


def supported_collections() -> list[str]:
    """Return sorted collection names with registered document contracts."""
    return sorted(COLLECTION_MODEL_ADAPTERS)
