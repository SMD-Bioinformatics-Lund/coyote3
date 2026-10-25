"""Permission-checked reusable configuration profile authoring and review routes."""

from fastapi import APIRouter, Depends

from api.app.container import util
from api.app.deps.application import get_configuration_profiles, get_configuration_promotions
from api.interfaces.http.tags import TAG_ADMIN_ASSAYS
from api.security.access import ApiUser, require_access
from coyote3.application.operations import ConfigurationProfiles, ConfigurationPromotions
from coyote3.contracts.configuration_profiles import (
    ConfigurationProfileDoc,
    ConfigurationProfileDraft,
    ConfigurationPromotionDoc,
    ConfigurationPromotionRequest,
    ProfilePublication,
)

router = APIRouter(tags=[TAG_ADMIN_ASSAYS])


@router.get(
    "/api/v1/resources/configuration-promotions", response_model=list[ConfigurationPromotionDoc]
)
def list_promotions(
    user: ApiUser = Depends(require_access(permission="assay.config:list")),
    service: ConfigurationPromotions = Depends(get_configuration_promotions),
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
    service: ConfigurationPromotions = Depends(get_configuration_promotions),
):
    """Propose reuse of an exact source revision with validation evidence."""
    return util.common.convert_to_serializable(service.propose(payload))


@router.post(
    "/api/v1/resources/configuration-promotions/{identity}/approve",
    response_model=ConfigurationPromotionDoc,
)
def approve_promotion(
    identity: str,
    payload: ProfilePublication,
    user: ApiUser = Depends(require_access(permission="configuration:publish")),
    service: ConfigurationPromotions = Depends(get_configuration_promotions),
):
    """Approve another user's exact reviewed candidate without changing existing sample bindings."""
    return util.common.convert_to_serializable(service.approve(identity, payload))


@router.get(
    "/api/v1/resources/configuration-profiles", response_model=list[ConfigurationProfileDoc]
)
def list_profiles(
    user: ApiUser = Depends(require_access(permission="assay.config:list")),
    service: ConfigurationProfiles = Depends(get_configuration_profiles),
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
    service: ConfigurationProfiles = Depends(get_configuration_profiles),
):
    """Create an immutable draft with assay.config:create permission."""
    return util.common.convert_to_serializable(service.create(payload))


@router.post(
    "/api/v1/resources/configuration-profiles/{identity}/publish",
    response_model=ConfigurationProfileDoc,
)
def publish_profile(
    identity: str,
    payload: ProfilePublication,
    user: ApiUser = Depends(require_access(permission="configuration:publish")),
    service: ConfigurationProfiles = Depends(get_configuration_profiles),
):
    """Publish another author's reviewed draft with configuration:publish permission."""
    return util.common.convert_to_serializable(service.publish(identity, payload))
