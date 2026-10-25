"""Admin workflows for the database-backed public assay catalog."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from coyote3.application.common.protected_records import reject_system_managed_change
from coyote3.application.public.offering_snapshots import build_offering_snapshot
from coyote3.application.public.published_catalog_views import (
    publication_context,
    publication_matrix,
)
from coyote3.application.resources.availability import available_panels
from coyote3.config.constants import (
    ALL_ANALYSIS_TYPE_OPTIONS,
    DNA_ANALYSIS_TYPE_OPTIONS,
    RNA_ANALYSIS_TYPE_OPTIONS,
)
from coyote3.contracts.schemas.catalog_offerings import CatalogDiscoveryDoc
from coyote3.contracts.schemas.public_catalog import (
    PublicAssayCatalogDoc,
    PublicAssayCatalogVersionDoc,
    PublicCatalogModalityExport,
)
from coyote3.contracts.schemas.registry import normalize_collection_document
from coyote3.domain.catalog_hierarchy import resolve_catalog_categories
from coyote3.domain.common.errors import api_error


class PublicAssayCatalogManagementService:
    """Validate, persist, audit, and package center public catalog content."""

    @classmethod
    def from_store(cls, store: Any):
        """Bind catalog governance to the store's catalog, source, and identity repositories.

        Args:
            store: Provider of catalog/version, assay, gene-list, user, and role repositories.

        Returns:
            Management service with preview and notification services still unassigned.
        """
        return cls(
            store.public_assay_catalog_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            gene_list_repository=store.gene_list_repository,
            versions=store.public_assay_catalog_version_repository,
            users=store.user_repository,
            roles=store.roles_repository,
            groups=store.assay_group_repository,
            diagnoses=store.assay_diagnosis_repository,
        )

    def __init__(
        self,
        repository: Any,
        *,
        assay_panel_repository: Any | None = None,
        assay_configuration_repository: Any | None = None,
        gene_list_repository: Any | None = None,
        versions: Any = None,
        users: Any = None,
        roles: Any = None,
        groups: Any = None,
        diagnoses: Any = None,
    ) -> None:
        """Configure catalog persistence and sources for governance choices.

        Args:
            repository: Reads the published default catalog.
            assay_panel_repository: Optional source of active assay choices.
            assay_configuration_repository: Optional source of production configurations.
            gene_list_repository: Optional source of active public, non-adhoc lists.
            versions: Version/history repository required for governance operations.
            users: Active-user repository required for assignee choices.
            roles: Role/capability repository required for assignee choices.
            groups: Biological group registry required for publication validation.
            diagnoses: Shared diagnosis associations required for named offerings.
        """
        self.repository = repository
        self.versions, self.users, self.roles = versions, users, roles
        self.groups, self.diagnoses = groups, diagnoses
        self.notification_service = None
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.gene_list_repository = gene_list_repository

    def get(self) -> dict[str, Any]:
        """Read the published catalog or construct an unpersisted starter catalog.

        Returns:
            Validated catalog data with field aliases.

        Raises:
            ValidationError: The stored catalog violates its schema.
        """
        document = self.repository.get_default()
        if document is None:
            return self._new_document().model_dump(by_alias=True)
        return PublicAssayCatalogDoc.model_validate(document).model_dump(by_alias=True)

    def export(self, *, modality: str | None = None) -> dict[str, Any]:
        """Export the catalog or one modality in its importable envelope.

        Args:
            modality: Modality key, stripped and lowercased; None or empty exports all.

        Returns:
            Complete catalog or a typed modality-export payload.

        Raises:
            AppError: With status 404 when the requested modality is absent.
        """
        document = PublicAssayCatalogDoc.model_validate(self.get())
        if not modality:
            return document.model_dump(by_alias=True)
        key = modality.strip().lower()
        definition = document.modalities.get(key)
        if definition is None:
            raise api_error(404, "Catalog modality not found")
        return PublicCatalogModalityExport(
            kind="coyote3.public_assay_catalog_modality",
            modality=key,
            definition=definition,
        ).model_dump()

    def source_options(self) -> dict[str, list[dict[str, Any]]]:
        """Expose safe identifiers and labels used by the catalog builder."""
        panels = (
            available_panels(self.assay_panel_repository) if self.assay_panel_repository else []
        )
        configurations = (
            list(self.assay_configuration_repository.get_all_aspc())
            if self.assay_configuration_repository
            else []
        )
        gene_lists = (
            self.gene_list_repository.get_all_isgl(is_active=True, is_public=True, adhoc=False)
            if self.gene_list_repository
            else []
        )
        return {
            "asps": sorted(
                [
                    {
                        "asp_id": item.get("asp_id"),
                        "label": item.get("display_name") or item.get("asp_id"),
                        "category": item.get("asp_category"),
                        "family": item.get("asp_family"),
                        "group": item.get("asp_group"),
                    }
                    for item in panels
                    if isinstance(item, dict) and item.get("asp_id")
                ],
                key=lambda item: str(item["label"]).casefold(),
            ),
            "aspcs": sorted(
                [
                    {
                        "aspc_id": item.get("aspc_id"),
                        "asp_id": item.get("asp_id"),
                        "diagnosis_id": item.get("diagnosis_id"),
                        "environment": item.get("environment"),
                        "is_active": bool(item.get("is_active")),
                    }
                    for item in configurations
                    if isinstance(item, dict)
                    and item.get("aspc_id")
                    and item.get("environment") == "production"
                    and item.get("is_active")
                ],
                key=lambda item: str(item["aspc_id"]).casefold(),
            ),
            "gene_lists": sorted(
                [
                    {
                        "isgl_id": item.get("isgl_id"),
                        "label": item.get("displayname") or item.get("name") or item.get("isgl_id"),
                        "asp_ids": item.get("asp_ids") or [],
                        "asp_groups": item.get("asp_groups") or [],
                        "diagnosis": item.get("diagnosis") or [],
                        "list_type": item.get("list_type") or [],
                    }
                    for item in gene_lists
                    if isinstance(item, dict) and item.get("isgl_id")
                ],
                key=lambda item: str(item["label"]).casefold(),
            ),
        }

    def workspace(self) -> dict[str, Any]:
        """Assemble catalog content, governance history, source choices, and editor presets.

        Returns:
            Workspace payload including publication existence and eligible assignees.
        """
        return {
            "catalog": self.get(),
            "has_published": self.repository.get_default() is not None,
            "sources": self.source_options(),
            "items": self.versions.list(),
            "reviewers": self.eligible("catalog:review"),
            "publishers": self.eligible("catalog:publish"),
            "presets": {
                "analysis": list(ALL_ANALYSIS_TYPE_OPTIONS),
                "analysis_by_omics": {
                    "dna": list(DNA_ANALYSIS_TYPE_OPTIONS),
                    "rna": list(RNA_ANALYSIS_TYPE_OPTIONS),
                },
                "input_material": [
                    "DNA",
                    "RNA",
                    "Fresh",
                    "Fresh Frozen",
                    "FFPE",
                    "Blood",
                    "Bone marrow",
                    "Neoplastic Tissue",
                ],
                "sample_modes": ["Tumor-only", "Tumor-normal"],
            },
        }

    def eligible(self, permission: str) -> list[dict[str, str]]:
        """Find active users with an active qualifying role or superuser role.

        Args:
            permission: Catalog capability required of non-superuser roles.

        Returns:
            Username and display-name choices, or no choices without matching roles.
        """
        roles = [
            r["role_id"]
            for r in self.roles.get_all_roles_plus_permissions()
            if r.get("is_active", True)
            and (permission in (r.get("permissions") or []) or r.get("role_id") == "superuser")
        ]
        if not roles:
            return []
        return [
            {"username": u["username"], "name": u.get("fullname") or u["username"]}
            for u in self.users.list_active_users_for_notifications(role_ids=roles)
        ]

    def document(self, oid: str) -> dict[str, Any]:
        """Read one governed catalog version.

        Args:
            oid: Version document identifier.

        Returns:
            Stored version document.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        doc = self.versions.get(oid)
        if doc is None:
            raise api_error(404, "Catalog version not found")
        return doc

    def preview(
        self,
        content: dict[str, Any],
        *,
        actor: str,
        mod: str | None = None,
        cat: str | None = None,
        isgl_key: str | None = None,
    ) -> dict[str, Any]:
        """Resolve public metadata using the same renderer as the published catalog."""
        return publication_context(self.preview_offerings(content, actor=actor), mod, cat, isgl_key)

    def revisions(self, oid: str) -> dict[str, Any]:
        """Read revision snapshots after checking that the version exists.

        Args:
            oid: Catalog version identifier.

        Returns:
            Revision rows under items.

        Raises:
            AppError: With status 404 when the version is absent.
        """
        self.document(oid)
        return {"items": self.versions.revisions(oid)}

    def preview_matrix(
        self,
        content: dict[str, Any],
        *,
        actor: str,
        page: int = 1,
        per_page: int = 100,
        gene: str | None = None,
    ) -> dict[str, Any]:
        """Build a gene-assay matrix from validated, unpersisted catalog content.

        Args:
            content: Proposed catalog document.
            actor: Login stamped on the temporary normalized content.
            page: Requested matrix page, defaulting to one.
            per_page: Requested page size, defaulting to 100.
            gene: Optional gene filter passed to the public catalog service.

        Returns:
            Public catalog service's matrix payload for this preview.

        Raises:
            AppError: With status 422 for invalid content or duplicate entry identifiers.
        """
        return publication_matrix(
            self.preview_offerings(content, actor=actor),
            page=page,
            per_page=per_page,
            gene=gene,
        )

    def _content(self, raw: dict[str, Any], *, actor: str) -> dict[str, Any]:
        """Copy and validate catalog content, assigning missing public entry identifiers.

        Args:
            raw: Proposed document; its _id is removed from the copy.
            actor: Login recorded with the current UTC update timestamp.

        Returns:
            Collection-normalized content without mutating the input.

        Raises:
            AppError: With status 422 for invalid schema or duplicate catalog IDs.
        """
        candidate = deepcopy(raw)
        candidate["published_offerings"] = []
        candidate["resource_revisions"] = {}
        candidate.pop("_id", None)
        try:
            candidate = PublicAssayCatalogDoc.model_validate(candidate).model_dump(by_alias=True)
        except ValueError as exc:
            raise api_error(422, "Invalid catalog content", str(exc)) from exc
        identifiers: set[str] = set()
        for modality in (candidate.get("modalities") or {}).values():
            for category in (modality.get("categories") or {}).values():
                category["catalog_id"] = category.get("catalog_id") or f"entry_{uuid4().hex}"
                if category["catalog_id"] in identifiers:
                    raise api_error(422, "Public entry identifiers must be unique")
                identifiers.add(category["catalog_id"])
        candidate["updated_by"] = actor
        candidate["updated_at"] = datetime.now(timezone.utc)
        try:
            return normalize_collection_document("public_assay_catalog", candidate)
        except ValueError as exc:
            raise api_error(422, "Invalid catalog content", str(exc)) from exc

    def create(self, *, actor: str, imported: dict[str, Any] | None = None) -> dict[str, Any]:
        """Insert a draft based on the live catalog, starter content, or an import.

        Args:
            actor: Initial content editor and lifecycle actor.
            imported: Full catalog or modality envelope; None copies live/starter content.

        Returns:
            Inserted draft at revision one, bound to the current publication version.

        Raises:
            AppError: With status 422 for invalid import/content or duplicate entry IDs.
        """
        live = self.repository.get_default()
        content = deepcopy(live) if live else self._new_document().model_dump(by_alias=True)
        if imported is not None:
            if imported.get("kind") == "coyote3.public_assay_catalog_modality":
                try:
                    envelope = PublicCatalogModalityExport.model_validate(imported)
                except ValueError as exc:
                    raise api_error(422, "Invalid modality export", str(exc)) from exc
                content["modalities"][envelope.modality] = envelope.definition.model_dump()
                if envelope.modality not in content["layout"]["order"]:
                    content["layout"]["order"].append(envelope.modality)
            else:
                content = imported
        now = datetime.now(timezone.utc)
        doc = PublicAssayCatalogVersionDoc(
            revision=1,
            base_version=int((live or {}).get("version", 0)),
            status="draft",
            catalog=self._content(content, actor=actor),
            content_editors=[actor],
            created_at=now,
            created_by=actor,
            updated_at=now,
            updated_by=actor,
            lifecycle=[
                {
                    "action": "imported" if imported else "created",
                    "actor": actor,
                    "occurred_at": now,
                }
            ],
        )
        return self.versions.insert(doc.model_dump(by_alias=True, mode="python"))

    def _checked(self, oid: str, revision: int, status: str) -> dict[str, Any]:
        """Require an existing version at the caller's expected revision and status.

        Args:
            oid: Version identifier.
            revision: Expected revision number.
            status: Required lifecycle state.

        Returns:
            Stored version when both expectations match.

        Raises:
            AppError: With status 404 for absence or 409 for stale revision/state.
        """
        doc = self.document(oid)
        reject_system_managed_change(doc, resource="public assay catalog")
        if doc["revision"] != revision or doc["status"] != status:
            raise api_error(409, "Catalog state changed. Reload this version before continuing.")
        return doc

    def _save(
        self,
        previous: dict[str, Any],
        changes: dict[str, Any],
        *,
        actor: str,
        action: str,
        reason: str = "",
        publish: bool = False,
    ) -> dict[str, Any]:
        """Validate and conditionally replace a version with a new lifecycle revision.

        Args:
            previous: Stored version used as the conditional replacement baseline.
            changes: Fields merged over a deep copy of the baseline.
            actor: Updater and lifecycle actor.
            action: Lifecycle event name.
            reason: Event explanation, defaulting to an empty string.
            publish: Ask the repository to update the live catalog as well when True.

        Returns:
            Saved version with an incremented revision and UTC update timestamp.

        Raises:
            ValidationError: The candidate version violates its schema.
            AppError: With status 409 when replacement/publication conflicts.
        """
        now = datetime.now(timezone.utc)
        candidate = {
            **deepcopy(previous),
            **changes,
            "revision": previous["revision"] + 1,
            "updated_at": now,
            "updated_by": actor,
        }
        candidate["lifecycle"].append(
            {"action": action, "actor": actor, "occurred_at": now, "reason": reason}
        )
        candidate = PublicAssayCatalogVersionDoc.model_validate(candidate).model_dump(by_alias=True)
        saved = self.versions.replace(previous, candidate, publish=publish)
        if saved is None:
            raise api_error(
                409,
                "Catalog changed or a newer catalog was published. Reload and create a draft from the current publication.",
            )
        return saved

    def update(
        self, oid: str, revision: int, content: dict[str, Any], *, actor: str
    ) -> dict[str, Any]:
        """Save draft content while preserving catalog creation metadata and version.

        Args:
            oid: Draft identifier.
            revision: Expected current revision.
            content: Proposed complete catalog content.
            actor: Editor added to the draft's content-editor set.

        Returns:
            Updated draft revision.

        Raises:
            AppError: With status 404 for absence, 409 for state/revision conflicts,
                or 422 for invalid catalog content.
        """
        previous = self._checked(oid, revision, "draft")
        content = self._content(content, actor=actor)
        for key in ("version", "created_by", "created_at"):
            content[key] = previous["catalog"][key]
        return self._save(
            previous,
            {
                "catalog": content,
                "content_editors": sorted(set(previous["content_editors"]) | {actor}),
            },
            actor=actor,
            action="draft_saved",
        )

    def _assignee(self, username: str, permission: str, editors: list[str]) -> str:
        """Require an eligible assignee independent of every listed editor.

        Args:
            username: Exact login to check; this method does not normalize it.
            permission: Required catalog capability.
            editors: Logins excluded from assignment.

        Returns:
            The accepted login unchanged.

        Raises:
            AppError: With status 409 for an editor or an ineligible user.
        """
        if username in editors:
            raise api_error(
                409, "Review and publication must be independent of every content editor"
            )
        if username not in {u["username"] for u in self.eligible(permission)}:
            raise api_error(409, "Select an active user with the required catalog permission")
        return username

    def _notify(
        self, doc: dict[str, Any], recipient: str, actor: str, title: str, reason: str = ""
    ) -> None:
        """Send a linked catalog notification when a notification service is assigned.

        Args:
            doc: Catalog version supplying its header and link identifier.
            recipient: Recipient login.
            actor: Notification creator login.
            title: Notification heading and fallback body text.
            reason: Body explanation; blank uses the title.
        """
        if self.notification_service is not None:
            self.notification_service.create_notification(
                audience="users",
                recipients=[recipient],
                tone="info",
                category="application",
                title=title,
                message=f"{doc['catalog']['header']}: {reason or title}",
                source="Public assay catalog",
                created_by=actor,
                resource={
                    "type": "public_assay_catalog_version",
                    "id": str(doc["_id"]),
                    "name": doc["catalog"]["header"],
                    "uri": f"/admin/assay-catalog?version={doc['_id']}",
                },
            )

    def submit(self, oid: str, revision: int, reviewer: str, *, actor: str) -> dict[str, Any]:
        """Validate draft links and submit to an independent eligible reviewer.

        Args:
            oid: Draft identifier.
            revision: Expected draft revision.
            reviewer: Reviewer login, excluded if an editor or the submitting actor.
            actor: Submitting login recorded in review provenance.

        Returns:
            Submitted revision after optional reviewer notification.

        Raises:
            AppError: With status 404 for absence, 409 for state/assignment conflicts,
                or 422 for invalid catalog links or presentation fields.
        """
        doc = self._checked(oid, revision, "draft")
        reviewer = self._assignee(reviewer, "catalog:review", doc["content_editors"] + [actor])
        self.validate_links(doc["catalog"])
        snapshot = self.offering_snapshot(doc["catalog"])
        review = {
            "submitted_by": actor,
            "submitted_at": datetime.now(timezone.utc),
            "reviewer": reviewer,
        }
        saved = self._save(
            doc,
            {"status": "submitted", "review": review, "catalog": snapshot},
            actor=actor,
            action="submitted",
        )
        self._notify(saved, reviewer, actor, "Catalog review requested")
        return saved

    def decide(
        self, oid: str, revision: int, *, actor: str, approve: bool, publisher: str, reason: str
    ) -> dict[str, Any]:
        """Record the assigned reviewer's decision with optional outcome notifications.

        Args:
            oid: Submitted version identifier.
            revision: Expected revision number.
            actor: Assigned reviewer, required to remain eligible and independent.
            approve: True approves; False rejects.
            publisher: Eligible independent publisher required only for approval.
            reason: Decision explanation; rejection requires nonblank text.

        Returns:
            Approved or rejected version revision.

        Raises:
            AppError: With status 404 for absence, 409 for state/eligibility conflicts,
                403 for another reviewer, or 422 for a missing rejection reason.

        Notes:
            When a notification service is assigned, both outcomes notify the creator;
            only approval also sends a publication request to the selected publisher.
        """
        doc = self._checked(oid, revision, "submitted")
        self._assignee(actor, "catalog:review", doc["content_editors"])
        if doc["review"]["reviewer"] != actor:
            raise api_error(403, "This review is assigned to another user")
        if not approve and not reason.strip():
            raise api_error(422, "Give a reason for rejection")
        selected = (
            self._assignee(publisher, "catalog:publish", doc["content_editors"])
            if approve
            else None
        )
        review = {
            **doc["review"],
            "reviewer_decision_at": datetime.now(timezone.utc),
            "reviewer_reason": reason,
            "publisher": selected,
        }
        saved = self._save(
            doc,
            {"status": "approved" if approve else "rejected", "review": review},
            actor=actor,
            action="approved" if approve else "rejected",
            reason=reason,
        )
        self._notify(
            saved,
            doc["created_by"],
            actor,
            "Catalog approved" if approve else "Catalog rejected",
            reason,
        )
        if selected:
            self._notify(saved, selected, actor, "Catalog publication requested")
        return saved

    def publish(self, oid: str, revision: int, *, actor: str) -> dict[str, Any]:
        """Recheck governance and source links before publishing an approved catalog.

        Args:
            oid: Approved version identifier.
            revision: Expected revision number.
            actor: Assigned publisher, required to remain eligible and independent.

        Returns:
            Published revision after optional creator notification.

        Raises:
            AppError: With status 404 for absence, 403 for another publisher,
                409 for governance/concurrent publication conflicts, or 422 for bad links.
        """
        doc = self._checked(oid, revision, "approved")
        self._assignee(actor, "catalog:publish", doc["content_editors"])
        if doc["review"]["publisher"] != actor:
            raise api_error(403, "This publication is assigned to another user")
        self._assignee(doc["review"]["reviewer"], "catalog:review", doc["content_editors"])
        self.validate_links(doc["catalog"])
        current = self.offering_snapshot(doc["catalog"])
        if any(
            current[key] != doc["catalog"].get(key)
            for key in ("published_offerings", "resource_revisions")
        ):
            raise api_error(409, "Offering sources changed after review; submit an updated draft")
        saved = self._save(
            doc,
            {
                "status": "published",
                "published_by": actor,
                "published_at": datetime.now(timezone.utc),
            },
            actor=actor,
            action="published",
            publish=True,
        )
        self._notify(saved, doc["created_by"], actor, "Catalog published")
        return saved

    def offering_snapshot(self, catalog: dict) -> dict:
        """Resolve a review snapshot using the authoritative resource repositories."""
        return build_offering_snapshot(
            catalog,
            panels=self.assay_panel_repository,
            configurations=self.assay_configuration_repository,
            gene_lists=self.gene_list_repository,
            groups=self.groups,
            diagnoses=self.diagnoses,
        )

    def preview_offerings(self, content: dict, *, actor: str) -> dict:
        """Preview reviewed snapshots or resolve draft services without persistence.

        Args:
            content: Draft content or a saved review/publication snapshot.
            actor: Authenticated operator requesting this private preview.

        Returns:
            Allowlisted service details. Supplied snapshots are preview-only; saving
            and submission discard and rebuild all derived fields from resources.
        """
        if content.get("resource_revisions") and content.get("published_offerings"):
            try:
                return CatalogDiscoveryDoc(
                    version=content.get("version", 0),
                    header=content.get("header", "Genomic test catalog"),
                    description=content.get("description", ""),
                    offerings=content["published_offerings"],
                ).model_dump(mode="json")
            except ValueError as exc:
                raise api_error(422, "Invalid offering preview snapshot") from exc
        document = self._content(content, actor=actor)
        self.validate_links(document)
        snapshot = self.offering_snapshot(document)
        return {
            "version": document["version"],
            "header": document["header"],
            "description": document["description"],
            "offerings": snapshot["published_offerings"],
        }

    def delete_unpublished(self, identifier: str, revision: int, *, actor: str) -> dict:
        """Discard a pre-publication catalog version without touching the live publication.

        Args:
            identifier: Version identifier selected by the operator.
            revision: Expected current revision.
            actor: Authenticated operator authorized to author catalog drafts.

        Returns:
            Deleted version for the audit response.

        Raises:
            AppError: The version was published, changed, or does not exist.
        """
        reject_system_managed_change(self.document(identifier), resource="public assay catalog")
        deleted = self.versions.delete_unpublished(identifier, revision, actor)
        if deleted is None:
            raise api_error(409, "Only an unchanged unpublished catalog version can be deleted")
        return deleted

    def validate_links(self, catalog: dict[str, Any]) -> None:
        """Check catalog entries against currently available public source choices.

        Args:
            catalog: Catalog content containing modality categories and gene-list entries.

        Raises:
            AppError: With status 422 for empty sections/labels, inactive assays,
                missing or mismatched production configurations, unavailable or duplicate
                gene lists within an entry, unsupported analysis badges, ineligible assay/group
                links, or incomplete or contradictory per-analysis gene-list assignments.
        """
        options = self.source_options()
        asps = {a["asp_id"]: a for a in options["asps"]}
        configs = {a["aspc_id"]: a for a in options["aspcs"]}
        lists = {a["isgl_id"]: a for a in options["gene_lists"]}
        if not catalog.get("modalities"):
            raise api_error(422, "Add at least one catalog section")
        for modality in catalog["modalities"].values():
            if not modality.get("label") or not modality.get("categories"):
                raise api_error(422, "Each section needs a display name and an entry")
            for category in resolve_catalog_categories(modality).values():
                section_analyses = {
                    "dna": DNA_ANALYSIS_TYPE_OPTIONS,
                    "rna": RNA_ANALYSIS_TYPE_OPTIONS,
                }.get(modality.get("omics"), ALL_ANALYSIS_TYPE_OPTIONS)
                if set(category.get("analysis") or []) - set(section_analyses):
                    raise api_error(422, "Choose supported DNA/RNA analysis types")
                if category.get("node_kind") == "folder":
                    if not category.get("label"):
                        raise api_error(422, "Each folder needs a display name")
                    if not category.get("asp_id"):
                        if category.get("gene_lists"):
                            raise api_error(422, "Link an assay before assigning gene lists")
                        continue
                if not category.get("label") or category.get("asp_id") not in asps:
                    raise api_error(422, "Each entry needs a display name and an active assay")
                refs = list((category.get("aspc_ids") or {}).values())
                if set(category.get("aspc_ids") or {}) - {"production"}:
                    raise api_error(422, "Public catalog configurations must be production only")
                if category.get("aspc_id"):
                    refs.append(category["aspc_id"])
                if not refs:
                    raise api_error(422, "Choose a production configuration for each entry")
                for ref in refs:
                    if ref not in configs or configs[ref]["asp_id"] != category["asp_id"]:
                        raise api_error(
                            422, "Choose an active production configuration for the selected assay"
                        )
                    if (category.get("diagnosis_id") or "base") != (
                        configs[ref].get("diagnosis_id") or "base"
                    ):
                        raise api_error(422, "The configuration must match the selected diagnosis")
                selected_lists: set[str] = set()
                analyses = set(category.get("analysis") or [])
                omics = modality.get("omics") or asps[category["asp_id"]].get("category")
                supported = {
                    "dna": DNA_ANALYSIS_TYPE_OPTIONS,
                    "rna": RNA_ANALYSIS_TYPE_OPTIONS,
                }.get(omics, ALL_ANALYSIS_TYPE_OPTIONS)
                if modality.get("omics") and asps[category["asp_id"]].get("category") != omics:
                    raise api_error(422, "The assay must match the section's DNA/RNA category")
                if analyses - set(supported):
                    raise api_error(
                        422, "Choose analyses supported by the assay's DNA/RNA category"
                    )
                no_gene_list = set(category.get("no_gene_list") or [])
                assigned: set[str] = set()
                if no_gene_list - analyses:
                    raise api_error(422, "Select analyses before assigning gene lists")
                for item in category.get("gene_lists", []):
                    list_id = item.get("isgl_id") or item.get("key")
                    if list_id not in lists:
                        raise api_error(422, "Choose an active public gene list")
                    if list_id in selected_lists:
                        raise api_error(422, "Each gene list can appear only once within an entry")
                    selected_lists.add(list_id)
                    source = lists[list_id]
                    if category["asp_id"] not in source["asp_ids"] or (
                        source.get("asp_groups")
                        and asps[category["asp_id"]].get("group") not in source["asp_groups"]
                    ):
                        raise api_error(
                            422, "Gene lists must belong to the selected assay and group"
                        )
                    linked_analyses = set(item.get("analysis") or [])
                    if (analyses and not linked_analyses) or linked_analyses - analyses:
                        raise api_error(422, "Assign each gene list to selected analyses")
                    if {a.lower() for a in linked_analyses} - set(source.get("list_type") or []):
                        raise api_error(422, "Gene-list types must support their selected analyses")
                    if (
                        source.get("diagnosis")
                        and category.get("diagnosis_id") not in source["diagnosis"]
                    ):
                        raise api_error(422, "Gene lists must support the selected diagnosis")
                    assigned.update(linked_analyses)
                if assigned & no_gene_list:
                    raise api_error(422, "An analysis cannot have gene lists and No gene list")
                if analyses - assigned - no_gene_list:
                    raise api_error(422, "Select gene lists or No gene list for every analysis")
                for presentation in [category, *category.get("gene_lists", [])]:
                    if set(presentation.get("analysis") or []) - set(ALL_ANALYSIS_TYPE_OPTIONS):
                        raise api_error(422, "Choose supported analysis badges")

    @staticmethod
    def _new_document() -> PublicAssayCatalogDoc:
        """Construct an unpersisted DNA/RNA catalog with editable family folders.

        Returns:
            Catalog with DNA and RNA roots and optional sequencing-family folders.
        """
        return PublicAssayCatalogDoc(
            header="Assay Catalog",
            layout={"order": ["dna", "rna"]},
            modalities={
                "dna": {
                    "label": "DNA",
                    "omics": "dna",
                    "categories": {
                        "wgs": {"label": "WGS", "node_kind": "folder"},
                        "wes": {"label": "WES", "node_kind": "folder"},
                        "panels": {"label": "Panels", "node_kind": "folder"},
                    },
                },
                "rna": {
                    "label": "RNA",
                    "omics": "rna",
                    "categories": {
                        "wts": {"label": "WTS", "node_kind": "folder"},
                        "panels": {"label": "Panels", "node_kind": "folder"},
                    },
                },
            },
        )
