"""Restricted reference metadata used by trusted ingestion tooling."""

from collections.abc import Callable
from typing import Any

from coyote3.application.operations.runtime import ApplicationRuntime


class InternalReferenceServices:
    """Host-owned reference lookups without exposing storage implementations."""

    def __init__(
        self,
        *,
        role_levels: Callable[[], dict[str, int]],
        gene_list_metadata: Callable[[str], dict[str, Any]],
    ) -> None:
        """Bind reference metadata readers used by authenticated ingestion tooling.

        Args:
            role_levels: Loads registered role identifiers and numerical access levels.
            gene_list_metadata: Loads a list's ad-hoc flag and display name by identifier.
        """
        self.role_levels, self.gene_list_metadata = role_levels, gene_list_metadata


class InternalReferences:
    """Read allowlisted ingestion metadata under a verified internal capability."""

    def __init__(self, runtime: ApplicationRuntime, services: InternalReferenceServices) -> None:
        """Bind current authentication, access audit and allowlisted reference readers."""
        self._runtime, self._services = runtime, services

    def role_levels(self) -> dict[str, Any]:
        """Read role levels with internal.ingest:manage permission."""
        return self._runtime.execute(
            "internal_references.role_levels",
            ("internal.ingest:manage",),
            lambda actor, sample: {"status": "ok", "role_levels": self._services.role_levels()},
        )

    def gene_list_metadata(self, identifier: str) -> dict[str, Any]:
        """Read limited ingestion metadata with internal.ingest:manage permission.

        Args:
            identifier: Registered gene-list identifier.

        Returns:
            List identifier, ad-hoc status and display name, excluding gene content.

        Raises:
            AppError: Authentication, permission or the credential audience rejects the read.
        """
        return self._runtime.execute(
            "internal_references.gene_list_metadata",
            ("internal.ingest:manage",),
            lambda actor, sample: {
                "status": "ok",
                "isgl_id": identifier,
                **self._services.gene_list_metadata(identifier),
            },
        )
