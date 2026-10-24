"""Permission-checked reusable configuration profile authoring and review routes."""

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.services import (
    get_configuration_profile_service,
    get_configuration_promotion_service,
)
from api.application.resources.configuration_profiles import ConfigurationProfileService
from api.application.resources.configuration_promotions import ConfigurationPromotionService
from api.contracts.configuration_profiles import (
    ConfigurationProfileDoc,
    ConfigurationProfileDraft,
    ConfigurationPromotionDoc,
    ConfigurationPromotionRequest,
    ProfilePublication,
)
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get(
    "/api/v1/resources/configuration-promotions", response_model=list[ConfigurationPromotionDoc]
)
def list_promotions(
    user: ApiUser = Depends(require_access(permission="assay.config:list")),
    service: ConfigurationPromotionService = Depends(get_configuration_promotion_service),
):
    """List reviewable environment promotion proposals with assay.config:list permission."""
    return util.common.convert_to_serializable(service.list())


@router.post(
    "/api/v1/resources/configuration-promotions",
    response_model=ConfigurationPromotionDoc,
    status_code=201,
)
def propose_promotion(
    payload: ConfigurationPromotionRequest,
    user: ApiUser = Depends(require_access(permission="assay.config:create")),
    service: ConfigurationPromotionService = Depends(get_configuration_promotion_service),
):
    """Propose reuse of an exact source revision with validation evidence."""
    return util.common.convert_to_serializable(service.propose(payload, actor=user.username))


@router.post(
    "/api/v1/resources/configuration-promotions/{identity}/approve",
    response_model=ConfigurationPromotionDoc,
)
def approve_promotion(
    identity: str,
    payload: ProfilePublication,
    user: ApiUser = Depends(require_access(permission="configuration:publish")),
    service: ConfigurationPromotionService = Depends(get_configuration_promotion_service),
):
    """Approve another user's exact reviewed candidate without changing existing sample bindings."""
    return util.common.convert_to_serializable(
        service.approve(
            identity,
            actor=user.username,
            content_hash=payload.content_hash,
            reason=payload.reason,
        )
    )


@router.get(
    "/api/v1/resources/configuration-profiles", response_model=list[ConfigurationProfileDoc]
)
def list_profiles(
    user: ApiUser = Depends(require_access(permission="assay.config:list")),
    service: ConfigurationProfileService = Depends(get_configuration_profile_service),
):
    """List source revisions for configuration authoring with assay.config:list permission."""
    return util.common.convert_to_serializable(service.list())


@router.post(
    "/api/v1/resources/configuration-profiles",
    response_model=ConfigurationProfileDoc,
    status_code=201,
)
def create_profile(
    payload: ConfigurationProfileDraft,
    user: ApiUser = Depends(require_access(permission="assay.config:create")),
    service: ConfigurationProfileService = Depends(get_configuration_profile_service),
):
    """Create an immutable draft with assay.config:create permission."""
    return util.common.convert_to_serializable(service.create(payload, actor=user.username))


@router.post(
    "/api/v1/resources/configuration-profiles/{identity}/publish",
    response_model=ConfigurationProfileDoc,
)
def publish_profile(
    identity: str,
    payload: ProfilePublication,
    user: ApiUser = Depends(require_access(permission="configuration:publish")),
    service: ConfigurationProfileService = Depends(get_configuration_profile_service),
):
    """Publish another author's reviewed draft with configuration:publish permission."""
    return util.common.convert_to_serializable(
        service.publish(
            identity,
            actor=user.username,
            content_hash=payload.content_hash,
            reason=payload.reason,
        )
    )
