"""Authorize and install the application's packaged deployment catalogs."""

from collections.abc import Callable
from typing import Any

from api.contracts.deployment_data import DeploymentDataModule, DeploymentDataScope
from api.domain.common.errors import api_error


class DeploymentDataService:
    """Keep authorization at the data-addition boundary, shared by API callers and tooling."""

    def __init__(
        self,
        repository: Any,
        seed_loader: Callable[[str, DeploymentDataScope], dict[str, Any]],
        demo: Any = None,
    ) -> None:
        """Bind configured storage and the server-owned, validated seed-pack loader."""
        self.repository = repository
        self.seed_loader = seed_loader
        self.demo = demo

    def install(
        self, *, user: Any, modules: list[DeploymentDataModule], force: bool = False
    ) -> dict[str, dict[str, str]]:
        """Install missing packaged catalogs for an authenticated administrator.

        Args:
            user: Current API-session principal; its username supplies provenance.
            modules: Explicitly selected catalogs or the packaged demonstration.
            force: Repair selected bundled records; unrelated data and accounts are preserved.

        Returns:
            Per-collection loaded/skipped results; populated collections are preserved.

        Raises:
            AppError: The session principal is not an administrator or superuser.
        """
        if (
            not user
            or not str(getattr(user, "username", "")).strip()
            or not ({"admin", "sys_admin", "superuser"} & set(getattr(user, "roles", []) or []))
        ):
            raise api_error(403, "Only an administrator or superuser can install deployment data")
        if getattr(user, "must_change_password", False):
            raise api_error(403, "Change your temporary password before installing data")
        documents = None
        results = {}
        # Prerequisites are applied before demonstration data, regardless of argument order.
        for module in ("identity", "application", "knowledgebase", "demo"):
            if module not in modules:
                continue
            if module == "demo":
                results["demo"] = self.demo.install_starter(
                    user.username, force=force, created_by="system"
                )["status"]
                continue
            if not force and not self.repository.pending(module):
                results.update(self.repository.skipped(module))
                continue
            if documents is None:
                documents = self.seed_loader(
                    "system", "all" if "knowledgebase" in modules else "application"
                )
            results.update(
                self.repository.install(documents, scope=module, actor=user.username, force=force)
            )
        return {"collections": results}
