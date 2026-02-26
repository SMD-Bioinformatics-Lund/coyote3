"""Domain-organized typed models for web API payloads."""

from coyote_web.api_models.dna import (
    ApiDnaCnvsPayload,
    ApiDnaCnvDetailPayload,
    ApiDnaTranslocationsPayload,
    ApiDnaTranslocationDetailPayload,
    ApiDnaVariantDetailPayload,
    ApiDnaVariantsPayload,
)
from coyote_web.api_models.rna import (
    ApiRnaFusionDetailPayload,
    ApiRnaFusionsPayload,
)

__all__ = [
    "ApiDnaCnvsPayload",
    "ApiDnaCnvDetailPayload",
    "ApiDnaTranslocationsPayload",
    "ApiDnaTranslocationDetailPayload",
    "ApiDnaVariantDetailPayload",
    "ApiDnaVariantsPayload",
    "ApiRnaFusionDetailPayload",
    "ApiRnaFusionsPayload",
]
