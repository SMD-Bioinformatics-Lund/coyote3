"""Domain-organized typed models for web API payloads."""

from coyote_web.api_models.base import ApiMutationResultPayload
from coyote_web.api_models.dna import (
    ApiDnaCnvsPayload,
    ApiDnaCnvDetailPayload,
    ApiDnaReportPreviewPayload,
    ApiDnaReportSavePayload,
    ApiDnaTranslocationsPayload,
    ApiDnaTranslocationDetailPayload,
    ApiDnaVariantDetailPayload,
    ApiDnaVariantsPayload,
)
from coyote_web.api_models.rna import (
    ApiRnaFusionDetailPayload,
    ApiRnaFusionsPayload,
    ApiRnaReportPreviewPayload,
    ApiRnaReportSavePayload,
)

__all__ = [
    "ApiMutationResultPayload",
    "ApiDnaCnvsPayload",
    "ApiDnaCnvDetailPayload",
    "ApiDnaReportPreviewPayload",
    "ApiDnaReportSavePayload",
    "ApiDnaTranslocationsPayload",
    "ApiDnaTranslocationDetailPayload",
    "ApiDnaVariantDetailPayload",
    "ApiDnaVariantsPayload",
    "ApiRnaFusionDetailPayload",
    "ApiRnaFusionsPayload",
    "ApiRnaReportPreviewPayload",
    "ApiRnaReportSavePayload",
]
