"""Domain-organized typed models for web API payloads."""

from coyote_web.api_models.base import ApiMutationResultPayload
from coyote_web.api_models.admin import (
    ApiAdminPermissionContextPayload,
    ApiAdminPermissionCreateContextPayload,
    ApiAdminPermissionsPayload,
    ApiAdminRoleContextPayload,
    ApiAdminRoleCreateContextPayload,
    ApiAdminRolesPayload,
    ApiAdminUserContextPayload,
    ApiAdminUserCreateContextPayload,
    ApiAdminUsersPayload,
)
from coyote_web.api_models.dna import (
    ApiDnaBiomarkersPayload,
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
    "ApiAdminRolesPayload",
    "ApiAdminRoleCreateContextPayload",
    "ApiAdminRoleContextPayload",
    "ApiAdminPermissionsPayload",
    "ApiAdminPermissionCreateContextPayload",
    "ApiAdminPermissionContextPayload",
    "ApiAdminUsersPayload",
    "ApiAdminUserCreateContextPayload",
    "ApiAdminUserContextPayload",
    "ApiDnaBiomarkersPayload",
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
