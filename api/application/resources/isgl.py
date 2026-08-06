"""Admin genelist resource-management workflows."""

from __future__ import annotations

from typing import Any

from api.application.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    utc_now,
)
from api.application.resources.helpers import _validated_doc
from api.contracts.managed_resources import managed_resource_spec
from api.domain.common.assay_filters import create_assay_group_map
from api.domain.common.errors import api_error


class IsglService:
    """Genelist resource workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "IsglService":
        """Build the service from the runtime store."""
        return cls(
            gene_list_repository=store.gene_list_repository,
            assay_panel_repository=store.assay_panel_repository,
        )

    def __init__(self, *, gene_list_repository: Any, assay_panel_repository: Any) -> None:
        """Create the service for genelist resource workflows."""
        self._spec = managed_resource_spec("isgl")
        self.gene_list_repository = gene_list_repository
        self.assay_panel_repository = assay_panel_repository

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the admin list payload for genelists.

        Returns:
            dict[str, Any]: Genelist rows and pagination metadata.
        """
        rows, total = self.gene_list_repository.search_isgls(q=q, page=page, per_page=per_page)
        genelists = [dict(item) for item in rows if isinstance(item, dict)]
        total = int(total or 0)
        return {
            "genelists": genelists,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        """Return form context for creating a genelist.

        Args:
            actor_username: Username used for default form metadata.

        Returns:
            dict[str, Any]: Form payload for the create view.
        """
        form = build_managed_form(self._spec, actor_username=actor_username)
        assay_group_map = self._configure_asp_scope(form)
        return {
            "form": form,
            "assay_group_map": assay_group_map,
        }

    def context_payload(self, *, genelist_id: str) -> dict[str, Any]:
        """Return form context for editing a genelist.

        Args:
            genelist_id: Genelist identifier to load.

        Returns:
            dict[str, Any]: Existing genelist data and edit form payload.
        """
        genelist = self.gene_list_repository.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        form = build_managed_form(self._spec)
        assay_group_map = self._configure_asp_scope(form)
        form["fields"]["asp_groups"]["default"] = genelist.get("asp_groups", [])
        form["fields"]["asp_ids"]["default"] = genelist.get("asp_ids", [])
        return {
            "genelist": genelist,
            "form": form,
            "assay_group_map": assay_group_map,
        }

    def _configure_asp_scope(self, form: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Limit ASP choices to the assay groups selected in the ISGL form."""
        assay_group_map = create_assay_group_map(
            self.assay_panel_repository.get_all_asps(is_active=True)
        )
        option_map: dict[str, list[dict[str, Any]]] = {}
        for group, panels in assay_group_map.items():
            if not group:
                continue
            option_map[str(group).lower()] = [
                {
                    "value": panel.get("asp_id"),
                    "label": panel.get("display_name") or panel.get("asp_id"),
                    "category": str(group),
                }
                for panel in panels
                if panel.get("asp_id")
            ]
        form["fields"]["asp_ids"]["options_by_field"] = {
            "field": "asp_groups",
            "values": option_map,
        }
        return assay_group_map

    def _validate_asp_scope(self, config: dict[str, Any]) -> None:
        """Reject ASP selections outside the ISGL's selected assay groups."""
        panels = {
            str(panel.get("asp_id") or "").strip().lower(): panel
            for panel in (self.assay_panel_repository.get_all_asps(is_active=True) or [])
            if isinstance(panel, dict) and panel.get("asp_id")
        }
        selected_groups = {str(value).strip().lower() for value in config.get("asp_groups", [])}
        unknown: list[str] = []
        mismatched: list[str] = []
        for asp_id in config.get("asp_ids", []):
            key = str(asp_id).strip().lower()
            panel = panels.get(key)
            if panel is None:
                unknown.append(str(asp_id))
                continue
            panel_group = str(panel.get("asp_group") or "").strip().lower()
            if panel_group not in selected_groups:
                mismatched.append(str(asp_id))
        if unknown:
            raise api_error(400, "Unknown or inactive ASP IDs: " + ", ".join(sorted(unknown)))
        if mismatched:
            raise api_error(
                400,
                "ASP IDs must belong to the selected assay groups: "
                + ", ".join(sorted(mismatched)),
            )

    def view_context_payload(self, *, genelist_id: str, assay: str | None) -> dict[str, Any]:
        """Return the read-only view payload for a genelist.

        Args:
            genelist_id: Genelist identifier to load.
            assay: Optional assay used to scope visible genes.

        Returns:
            dict[str, Any]: Genelist details and filtered genes.
        """
        genelist = self.gene_list_repository.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        all_genes = genelist.get("genes", [])
        asp_ids = genelist.get("asp_ids", [])
        filtered_genes = all_genes
        panel_germline_genes: list[str] = []
        if assay and assay in asp_ids:
            panel = self.assay_panel_repository.get_asp(assay)
            panel_genes = panel.get("covered_genes", []) if panel else []
            panel_germline_genes = panel.get("germline_genes", []) if panel else []
            filtered_genes = sorted(set(all_genes).intersection(panel_genes))
        return {
            "genelist": genelist,
            "selected_assay": assay,
            "filtered_genes": filtered_genes,
            "panel_germline_genes": panel_germline_genes,
        }

    def create(
        self, *, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Create a new genelist from submitted config data.

        Args:
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing genelist config payload")
        config.setdefault("is_active", True)
        config.pop("subpanel_id", None)
        config["isgl_id"] = config.get("isgl_id") or config.get("name")
        if not config.get("isgl_id"):
            raise api_error(400, "Missing isgl_id")
        existing_genelist = self.gene_list_repository.get_isgl(str(config["isgl_id"]))
        if isinstance(existing_genelist, dict) and (
            existing_genelist.get("isgl_id") or existing_genelist.get("_id")
        ):
            raise api_error(409, "Genelist already exists")
        actor = current_actor(actor_username)
        now = utc_now()
        config.setdefault("created_by", actor)
        config.setdefault("created_on", now)
        config["updated_by"] = actor
        config["updated_on"] = now
        config["version"] = 1
        config = _validated_doc(self._spec.collection, config)
        self._validate_asp_scope(config)
        self.gene_list_repository.create_genelist(config)
        return change_payload(
            resource="genelist", resource_id=str(config.get("isgl_id", "unknown")), action="create"
        )

    def update(
        self, *, genelist_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update an existing genelist.

        Args:
            genelist_id: Genelist identifier to update.
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        genelist = self.gene_list_repository.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing genelist config payload")
        updated_doc = {**genelist, **updated}
        updated_doc["isgl_id"] = genelist.get("isgl_id", genelist_id)
        updated_doc.pop("_id", None)
        updated_doc.pop("gene_count", None)
        updated_doc.pop("subpanel_id", None)
        # Required contract fields should not be unintentionally blanked by partial form submits.
        if not updated_doc.get("asp_ids"):
            updated_doc["asp_ids"] = list(genelist.get("asp_ids", []))
        if not updated_doc.get("asp_groups"):
            updated_doc["asp_groups"] = list(genelist.get("asp_groups", []))
        actor = current_actor(actor_username)
        now = utc_now()
        updated_doc["created_by"] = genelist.get("created_by") or actor
        updated_doc["created_on"] = genelist.get("created_on") or now
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = now
        updated_doc["is_active"] = True
        updated_doc["version"] = 1
        updated_doc.pop("retired_by", None)
        updated_doc.pop("retired_on", None)
        updated_doc.pop("retired_reason", None)
        updated_doc = _validated_doc(self._spec.collection, updated_doc)
        self._validate_asp_scope(updated_doc)
        self.gene_list_repository.update_isgl(genelist_id, updated_doc)
        return change_payload(resource="genelist", resource_id=genelist_id, action="update")

    def toggle(self, *, genelist_id: str) -> dict[str, Any]:
        """Toggle whether a genelist is active.

        Args:
            genelist_id: Genelist identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        genelist = self.gene_list_repository.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        new_status = not bool(genelist.get("is_active"))
        self.gene_list_repository.toggle_isgl_active(genelist_id, new_status)
        payload = change_payload(resource="genelist", resource_id=genelist_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, genelist_id: str) -> dict[str, Any]:
        """Delete an existing genelist.

        Args:
            genelist_id: Genelist identifier to delete.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        genelist = self.gene_list_repository.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        self.gene_list_repository.delete_genelist(genelist_id)
        return change_payload(resource="genelist", resource_id=genelist_id, action="delete")

    def genelist_exists(self, *, isgl_id: str) -> bool:
        """Return whether a genelist business key already exists."""
        normalized = str(isgl_id or "").strip()
        if not normalized:
            return False
        genelist = self.gene_list_repository.get_isgl(normalized)
        return bool(isinstance(genelist, dict) and (genelist.get("isgl_id") or genelist.get("_id")))
