# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorize and install the application's packaged deployment catalogs."""

from collections.abc import Callable
from typing import Any

from coyote.domain.common.errors import api_error
from coyote_mongo.config.collections import DeploymentDataScope

from coyote_api.contracts.deployment_data import DeploymentDataModule


class DeploymentDataService:
    """Keep authorization at the data-addition boundary, shared by API callers and tooling."""

    def __init__(
        self,
        repository: Any,
        seed_loader: Callable[[str, DeploymentDataScope], dict[str, Any]],
        *,
        reference_metadata: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        """Bind storage, validated seed loading and optional reference provenance.

        Args:
            repository: Persistence adapter for the selected deployment databases.
            seed_loader: Validates and normalizes documents for the requested scope.
            reference_metadata: Lazy source-bundle metadata saved with successful
                knowledgebase installations; absent for callers without a bundle.
        """
        self.repository = repository
        self.seed_loader = seed_loader
        self.reference_metadata = reference_metadata

    @staticmethod
    def authorize(user: Any) -> None:
        """Require an authenticated installation administrator with a permanent password.

        Args:
            user: Current verified session principal, never caller-supplied role data.

        Raises:
            AppError: The user is absent, lacks an installation role or must change password.
        """
        if (
            not user
            or not str(getattr(user, "username", "")).strip()
            or not ({"admin", "sys_admin", "superuser"} & set(getattr(user, "roles", []) or []))
        ):
            raise api_error(403, "Only an administrator or superuser can install deployment data")
        if getattr(user, "must_change_password", False):
            raise api_error(403, "Change your temporary password before installing data")

    def install(
        self, *, user: Any, modules: list[DeploymentDataModule], force: bool = False
    ) -> dict[str, dict[str, str]]:
        """Install missing packaged catalogs for an authenticated administrator.

        Args:
            user: Current API-session principal; its username supplies provenance.
            modules: Explicitly selected identity, application or reference catalogs.
            force: Repair selected bundled records; unrelated data and accounts are preserved.

        Returns:
            Per-collection loaded/skipped results; populated collections are preserved.

        Raises:
            AppError: The session principal is not an administrator or superuser.
        """
        self.authorize(user)
        documents = None
        results = {}
        for module in ("identity", "application", "knowledgebase"):
            if module not in modules:
                continue
            if not force and not self.repository.pending(module):
                results.update(self.repository.skipped(module))
                continue
            if documents is None:
                documents = self.seed_loader(
                    "system", "all" if "knowledgebase" in modules else "application"
                )
            results.update(
                self.repository.install(
                    documents,
                    scope=module,
                    actor=user.username,
                    force=force,
                    **(
                        {"reference_metadata": self.reference_metadata()}
                        if module == "knowledgebase" and self.reference_metadata is not None
                        else {}
                    ),
                )
            )
        return {"collections": results}
