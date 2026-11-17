# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized metadata retrieval through a database-independent repository port."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

from coyote_contracts.retrieval import ReadResource, ResourceReadPage, ResourceReadQuery
from pydantic import BaseModel, ConfigDict

from coyote.domain.common.errors import api_error
from coyote.domain.identity.assay_access import grants_for

if TYPE_CHECKING:
    from coyote.application.operations.runtime import ApplicationRuntime

READ_PERMISSIONS = {
    ReadResource.ASP: "assay.panel:view",
    ReadResource.ASPC: "assay.config:view",
    ReadResource.SAMPLES: "sample:view",
    ReadResource.ISGL: "gene_list.insilico:view",
    ReadResource.ASSAY_GROUPS: "assay.panel:view",
    ReadResource.DIAGNOSES: "assay.panel:view",
}


class ResourceReadScope(BaseModel):
    """Trusted actor scope, never populated from a retrieval request.

    None grants denotes a verified superuser. Other scopes contain exact paired
    assay/environment assignments. Empty groups imposes no additional group filter,
    consistent with sample access; explicit groups restrict authoritative assays.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grants: list[dict[str, Any]] | None
    groups: tuple[str, ...] = ()


class ResourceReadRepository(Protocol):
    """Persisted metadata reads with scope applied before totals and pagination."""

    def query(
        self, resource: ReadResource, query: ResourceReadQuery, scope: ResourceReadScope
    ) -> ResourceReadPage:
        """Return allowed metadata only, using bounded deterministic pagination."""
        ...


class ResourceReads:
    """Read safe named resources under freshly evaluated permissions and scope."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        repository: Callable[[], ResourceReadRepository],
    ) -> None:
        """Bind trusted runtime and lazy persistence without opening a connection."""
        self._runtime, self._repository = runtime, repository

    def query(self, resource: ReadResource, query: ResourceReadQuery) -> ResourceReadPage:
        """Authorize a metadata read, including related resources and aggregates.

        Args:
            resource: One named public metadata resource.
            query: Typed filters, projection, operation and bounded pagination.

        Returns:
            Only authorized records or values, with corresponding totals.

        Raises:
            AppError: Authentication, permissions or field validation fails.
        """
        try:
            resource = ReadResource(resource)
            query = ResourceReadQuery.model_validate(
                query.model_dump(by_alias=True, exclude_unset=True, warnings="none")
            ).validate_resource(resource)
        except ValueError as exc:
            raise api_error(422, str(exc)) from exc
        permissions = [READ_PERMISSIONS[resource]]
        if resource in {ReadResource.ASP, ReadResource.ASPC, ReadResource.ISGL}:
            permissions.append(READ_PERMISSIONS[resource].removesuffix(":view") + ":list")
        if "assay" in query.include or "assay" in query.related_filters:
            permissions.append(READ_PERMISSIONS[ReadResource.ASP])
        if "configuration" in query.include or "configuration" in query.related_filters:
            permissions.append(READ_PERMISSIONS[ReadResource.ASPC])

        def read(actor: Any, sample: dict[str, Any] | None) -> ResourceReadPage:
            """Build trusted scope from the freshly authenticated actor."""
            grants = grants_for(actor)
            groups = tuple(getattr(actor, "asp_groups", []) or []) if grants is not None else ()
            return self._repository().query(
                resource, query, ResourceReadScope(grants=grants, groups=groups)
            )

        return self._runtime.execute(
            f"resources.{resource.value}.{query.operation}", tuple(permissions), read
        )
