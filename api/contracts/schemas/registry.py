"""Collection-to-model contract registry."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

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
    ReportedVariantsDoc,
    TranslocationsDoc,
    VariantsDoc,
)
from api.contracts.schemas.governance import PermissionsDoc, RolesDoc, UsersDoc
from api.contracts.schemas.reference import (
    AnnotationDoc,
    BrcaExchangeDoc,
    CivicGenesDoc,
    CivicVariantsDoc,
    CosmicDoc,
    DashboardMetricsDoc,
    HgncGenesDoc,
    HpaExprDoc,
    IarcTp53Doc,
    ManeSelectDoc,
    OncoKbActionableDoc,
    OncoKbGenesDoc,
    RefSeqCanonicalDoc,
    VepMetadataDoc,
)
from api.contracts.schemas.rna import FusionsDoc, RnaClassificationDoc, RnaExpressionDoc, RnaQcDoc
from api.contracts.schemas.samples import SamplesDoc

COLLECTION_MODEL_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "samples": TypeAdapter(SamplesDoc),
    "variants": TypeAdapter(VariantsDoc),
    "cnvs": TypeAdapter(CnvsDoc),
    "translocations": TypeAdapter(TranslocationsDoc),
    "biomarkers": TypeAdapter(BiomarkersDoc),
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
    "refseq_canonical": TypeAdapter(RefSeqCanonicalDoc),
    "vep_metadata": TypeAdapter(VepMetadataDoc),
    "asp_to_groups": TypeAdapter(AssayPanelToAssayGroupMappingDoc),
}


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
    return parsed.model_dump(by_alias=True, exclude_none=False)


def supported_collections() -> list[str]:
    """Return sorted collection names with registered document contracts."""
    return sorted(COLLECTION_MODEL_ADAPTERS)
