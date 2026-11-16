# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Guarded administrative routes for installed synthetic demonstrations."""

from coyote_api.interfaces.http.tags import TAG_ADMIN_OPERATIONS
from coyote_api.security.access import ApiUser, require_access
from fastapi import APIRouter, Depends

from coyote_demo.api.dependencies import get_demo_installation
from coyote_demo.contracts import DemoInstallationPlan, DemoInstallResult
from coyote_demo.operations import DemoInstallation

router = APIRouter(tags=[TAG_ADMIN_OPERATIONS])


@router.get(
    "/api/v1/admin/demo-installation", response_model=DemoInstallationPlan, include_in_schema=False
)
def demo_installation_plan(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: DemoInstallation = Depends(get_demo_installation),
):
    """Inspect packaged demo configuration and sample status with demo:install permission."""
    return service.plan()


@router.post(
    "/api/v1/admin/demo-installation/starter",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_starter(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: DemoInstallation = Depends(get_demo_installation),
):
    """Install connected starter configuration and its first synthetic sample; requires demo:install."""
    return service.starter()


@router.post(
    "/api/v1/admin/demo-installation/configuration",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_configuration(
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: DemoInstallation = Depends(get_demo_installation),
):
    """Install synthetic testing configuration; existing fixture identities are never replaced."""
    return service.configuration()


@router.post(
    "/api/v1/admin/demo-installation/samples/{key}",
    response_model=DemoInstallResult,
    include_in_schema=False,
)
def install_demo_sample(
    key: str,
    user: ApiUser = Depends(require_access(permission="demo:install")),
    service: DemoInstallation = Depends(get_demo_installation),
):
    """Ingest an allowlisted synthetic sample with demo:install permission."""
    return service.sample(key)
