# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Host-owned factories for account and managed-resource implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coyote.application.accounts.permissions import PermissionManagementService
    from coyote.application.accounts.recovery import AccountRecoveryService
    from coyote.application.accounts.roles import RoleManagementService
    from coyote.application.accounts.sessions import SessionActivityRepository
    from coyote.application.accounts.users import UserManagementService
    from coyote.application.resources.asp import AspService
    from coyote.application.resources.aspc import AspcService
    from coyote.application.resources.assay_groups import AssayGroupService
    from coyote.application.resources.assay_setup import AssaySetupService
    from coyote.application.resources.diagnoses import DiagnosisService
    from coyote.application.resources.fields import ResourceFieldService
    from coyote.application.resources.isgl import IsglService
    from coyote.application.resources.public_assay_catalog import (
        PublicAssayCatalogManagementService,
    )
    from coyote.application.resources.sample import ResourceSampleService


class AdministrationServices:
    """Host-owned factories for account and managed-resource implementations."""

    def __init__(
        self,
        *,
        users: Callable[[], UserManagementService],
        recovery: Callable[[], AccountRecoveryService],
        sessions: Callable[[], SessionActivityRepository],
        roles: Callable[[], RoleManagementService],
        permissions: Callable[[], PermissionManagementService],
        assays: Callable[[], AspService],
        assay_groups: Callable[[], AssayGroupService],
        diagnoses: Callable[[], DiagnosisService],
        assay_configurations: Callable[[], AspcService],
        gene_lists: Callable[[], IsglService],
        sample_administration: Callable[[], ResourceSampleService],
        assay_setups: Callable[[], AssaySetupService],
        catalog_authoring: Callable[[], PublicAssayCatalogManagementService],
        reference_data: Callable[[], ResourceFieldService],
    ) -> None:
        """Bind administrative implementations without exposing repositories to callers.

        Args:
            users: Account lifecycle, safe forms and assignment validation.
            recovery: Provider-specific assisted account recovery.
            sessions: Aggregate login-session counts without credentials.
            roles: Registered role and permission-assignment workflows.
            permissions: Permission-policy definitions and lifecycle workflows.
            assays: Assay-panel configuration and lifecycle workflows.
            assay_groups: Biological group registration and availability changes.
            diagnoses: Shared diagnosis definitions and assay associations.
            assay_configurations: Scope-bound assay configuration authoring.
            gene_lists: Managed gene-list authoring and inspection.
            sample_administration: Privileged sample editing and deletion workflows.
            assay_setups: Draft-first setup validation, optional review and atomic activation.
            catalog_authoring: Catalog previews, revisions, assignment and publication.
            reference_data: Permitted fields and metadata for managed reference resources.
        """
        self.recovery = recovery
        self.users = users
        self.sessions = sessions
        self.roles = roles
        self.permissions = permissions
        self.assays = assays
        self.assay_groups = assay_groups
        self.diagnoses = diagnoses
        self.assay_configurations = assay_configurations
        self.gene_lists = gene_lists
        self.sample_administration = sample_administration
        self.assay_setups = assay_setups
        self.catalog_authoring = catalog_authoring
        self.reference_data = reference_data
