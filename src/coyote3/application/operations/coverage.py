"""Coverage blacklist operations with shared permission and group-scope enforcement."""

from typing import Any

from coyote3.application.common.access import enforce_assay_group
from coyote3.application.operations.clinical import ClinicalServices
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error


class Coverage:
    """Read and curate coverage exclusions through the existing clinical workflow services."""

    def __init__(self, runtime: ApplicationRuntime, services: ClinicalServices) -> None:
        """Bind authenticated execution and current coverage/catalog dependencies."""
        self._runtime, self._services = runtime, services

    def blacklisted(self, group: str) -> dict[str, Any]:
        """Read exclusions only for a currently assigned group under sample:view."""
        return self._runtime.execute(
            "coverage.blacklisted",
            ("sample:view",),
            lambda actor, sample: dict(
                self._services.coverage().blacklisted_payload(group=group, user=actor)
            ),
        )

    def add_blacklist(
        self, *, gene: str, group: str, region: str, coordinate: str | None = None
    ) -> str:
        """Create a group-owned coverage exclusion with the established coordinate spelling.

        Args:
            gene: Gene identifier already validated by the caller's input contract.
            group: Biological group that must be explicitly assigned to the current actor.
            region: Existing gene/CDS/probe region selector.
            coordinate: Optional coordinate; None or empty creates the existing gene exclusion.

        Returns:
            Existing composite resource identity for the created exclusion.
        """

        def write(actor: Any, sample: dict[str, Any] | None) -> str:
            """Authorize the group before invoking the established coverage curation service."""
            enforce_assay_group(actor, group)
            coord = str(coordinate).replace(":", "_").replace("-", "_") if coordinate else ""
            self._services.catalog().add_coverage_blacklist(
                gene=gene, coord=coord or None, region=region, smp_grp=group
            )
            return f"{gene}:{region}:{coord}" if coord else f"{gene}:{region}"

        return self._runtime.execute(
            "coverage.add_blacklist", ("coverage.blacklist:manage",), write
        )

    def remove_blacklist(self, identity: str) -> None:
        """Remove an existing exclusion only after checking its authoritative group ownership.

        Args:
            identity: Existing exclusion identifier; malformed values produce validation errors.

        Raises:
            AppError: The identifier is invalid, the entry is missing or current group access fails.
        """

        def write(actor: Any, sample: dict[str, Any] | None) -> None:
            """Load group ownership before applying the existing deletion."""
            service = self._services.catalog()
            try:
                entry = service.get_coverage_blacklist_entry(obj_id=identity)
            except ValueError as exc:
                raise api_error(
                    400, "Invalid coverage blacklist entry id", str(exc), category="validation"
                ) from exc
            if not entry:
                raise api_error(
                    404,
                    "Coverage blacklist entry not found",
                    f"No coverage blacklist entry exists for id '{identity}'.",
                    category="not_found",
                )
            enforce_assay_group(actor, str(entry.get("group") or ""))
            service.remove_coverage_blacklist(obj_id=identity)

        self._runtime.execute("coverage.remove_blacklist", ("coverage.blacklist:manage",), write)
