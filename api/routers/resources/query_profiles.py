"""Query-profile option lookup route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.contracts.admin import AdminQueryProfileOptionsPayload
from api.deps.services import get_admin_query_profile_service
from api.extensions import util
from api.security.access import ApiUser, require_access
from api.services.resources.aspc import QueryProfileService

router = APIRouter(tags=["resource-query-profiles"])


@router.get(
    "/api/v1/resources/query_profiles/options",
    response_model=AdminQueryProfileOptionsPayload,
)
def query_profile_options_read(
    assay_name: str = Query(default=""),
    assay_group: str = Query(default=""),
    environment: str = Query(default=""),
    user: ApiUser = Depends(require_access(permission="view_aspc", min_role="user", min_level=9)),
    service: QueryProfileService = Depends(get_admin_query_profile_service),
):
    _ = user
    return util.common.convert_to_serializable(
        service.options_payload(
            assay_name=assay_name,
            assay_group=assay_group,
            environment=environment,
        )
    )
