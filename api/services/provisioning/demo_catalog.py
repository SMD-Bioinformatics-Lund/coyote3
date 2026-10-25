"""Compile synthetic catalog offerings from the same resources used by ingestion."""

from typing import Any

from coyote3.application.public.offering_snapshots import build_offering_snapshot


class DemoCatalogResources:
    """Expose validated staged resources to the standard public offering compiler."""

    def __init__(self, documents: dict[str, list[dict]], groups: list[dict]) -> None:
        """Bind a validated installation bundle for read-only catalog compilation.

        Args:
            documents: Current collection documents indexed by logical collection name.
            groups: Validated biological group records from the bootstrap registry.
        """
        self.documents = documents
        self.groups = {row["group_id"]: row for row in groups}

    def get_asp(self, identifier: str) -> dict | None:
        """Find the exact staged sequencing assay.

        Args:
            identifier: Canonical ASP business key.

        Returns:
            The staged assay, or None when it is absent from the bundle.
        """
        return next(
            (r for r in self.documents["assay_specific_panels"] if r["asp_id"] == identifier), None
        )

    def get_aspc_with_id(self, identifier: str) -> dict | None:
        """Find the exact assay, diagnosis and environment configuration.

        Args:
            identifier: Compound ASPC business key, including its environment.

        Returns:
            The staged configuration, or None when no key matches.
        """
        return next((r for r in self.documents["asp_configs"] if r["aspc_id"] == identifier), None)

    def get_isgl(self, identifier: str, **conditions: Any) -> dict | None:
        """Find a reusable list only when its publication conditions match.

        Args:
            identifier: Canonical ISGL business key.
            **conditions: Required field values, such as is_active and is_public.

        Returns:
            The matching list, or None when absent or ineligible.
        """
        return next(
            (
                r
                for r in self.documents["insilico_genelists"]
                if r["isgl_id"] == identifier and all(r.get(k) == v for k, v in conditions.items())
            ),
            None,
        )

    def get(self, identifier: str) -> dict | None:
        """Return the registered biological group.

        Args:
            identifier: Stable biological group key.

        Returns:
            The group record, or None when unregistered.
        """
        return self.groups.get(identifier)

    def list_for_assay(self, identifier: str, *, active_only: bool) -> list[dict]:
        """Join explicit assay associations to shared diagnosis definitions.

        Args:
            identifier: ASP business key whose diagnosis links are requested.
            active_only: Require both the definition and its assay link to be active.

        Returns:
            Joined definitions with separate association and definition revisions.

        Raises:
            KeyError: A staged association references an absent diagnosis definition.
        """
        definitions = {r["diagnosis_id"]: r for r in self.documents["diagnoses"]}
        return [
            {
                **definitions[r["diagnosis_id"]],
                **r,
                "definition_version": definitions[r["diagnosis_id"]]["version"],
            }
            for r in self.documents["diagnosis_associations"]
            if r["asp_id"] == identifier
            and (
                not active_only or (r["is_active"] and definitions[r["diagnosis_id"]]["is_active"])
            )
        ]

    def compile(self, catalog: dict) -> dict:
        """Validate offering links and capture their published genes and revisions.

        Args:
            catalog: Presentation document with explicit assay and configuration links.

        Returns:
            A catalog copy containing offering snapshots and resource revision references.

        Raises:
            AppError: An offering references unavailable or ineligible resources.
        """
        return build_offering_snapshot(
            catalog, panels=self, configurations=self, gene_lists=self, groups=self, diagnoses=self
        )
