"""Admin genelist resource-management workflows."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.extensions import util
from api.http import api_error
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    inject_version_history,
    utc_now,
)
from api.services.resources.helpers import _validated_doc


class IsglService:
    """Genelist resource workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "IsglService":
        """Build the service from the shared store."""
        return cls(
            gene_list_handler=store.gene_list_handler,
            assay_panel_handler=store.assay_panel_handler,
        )

    def __init__(self, *, gene_list_handler: Any, assay_panel_handler: Any) -> None:
        """Create the service for genelist resource workflows."""
        self._spec = managed_resource_spec("isgl")
        self.gene_list_handler = gene_list_handler
        self.assay_panel_handler = assay_panel_handler

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the admin list payload for genelists.

        Returns:
            dict[str, Any]: Genelist rows and pagination metadata.
        """
        rows, total = self.gene_list_handler.search_isgls(q=q, page=page, per_page=per_page)
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
        form["fields"]["assay_groups"]["options"] = list(
            self.assay_panel_handler.get_all_asp_groups() or []
        )
        return {
            "form": form,
            "assay_group_map": util.common.create_assay_group_map(
                self.assay_panel_handler.get_all_asps()
            ),
        }

    def context_payload(self, *, genelist_id: str) -> dict[str, Any]:
        """Return form context for editing a genelist.

        Args:
            genelist_id: Genelist identifier to load.

        Returns:
            dict[str, Any]: Existing genelist data and edit form payload.
        """
        genelist = self.gene_list_handler.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        form = build_managed_form(self._spec)
        form["fields"]["assay_groups"]["options"] = list(
            self.assay_panel_handler.get_all_asp_groups() or []
        )
        form["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
        form["fields"]["assays"]["default"] = genelist.get("assays", [])
        return {
            "genelist": genelist,
            "form": form,
            "assay_group_map": util.common.create_assay_group_map(
                self.assay_panel_handler.get_all_asps()
            ),
        }

    def view_context_payload(self, *, genelist_id: str, assay: str | None) -> dict[str, Any]:
        """Return the read-only view payload for a genelist.

        Args:
            genelist_id: Genelist identifier to load.
            assay: Optional assay used to scope visible genes.

        Returns:
            dict[str, Any]: Genelist details and filtered genes.
        """
        genelist = self.gene_list_handler.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        all_genes = genelist.get("genes", [])
        assays = genelist.get("assays", [])
        filtered_genes = all_genes
        panel_germline_genes: list[str] = []
        if assay and assay in assays:
            panel = self.assay_panel_handler.get_asp(assay)
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
        config["isgl_id"] = config.get("isgl_id") or config.get("name")
        if not config.get("isgl_id"):
            raise api_error(400, "Missing isgl_id")
        existing_genelist = self.gene_list_handler.get_isgl(str(config["isgl_id"]))
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
        config = inject_version_history(
            actor_username=actor,
            new_config=config,
            is_new=True,
        )
        config = _validated_doc(self._spec.collection, config)
        self.gene_list_handler.create_genelist(config)
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
        genelist = self.gene_list_handler.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing genelist config payload")
        updated_doc = {**genelist, **updated}
        updated_doc["isgl_id"] = genelist.get("isgl_id", genelist_id)
        updated_doc["_id"] = genelist.get("_id")
        updated_doc.pop("gene_count", None)
        # Required contract fields should not be unintentionally blanked by partial form submits.
        if not updated_doc.get("assays"):
            updated_doc["assays"] = list(genelist.get("assays", []))
        if not updated_doc.get("assay_groups"):
            updated_doc["assay_groups"] = list(genelist.get("assay_groups", []))
        actor = current_actor(actor_username)
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(genelist.get("version", 1) or 1) + 1
        updated_doc = inject_version_history(
            actor_username=actor,
            new_config=updated_doc,
            old_config=genelist,
            is_new=False,
        )
        updated_doc = _validated_doc(self._spec.collection, updated_doc)
        self.gene_list_handler.update_isgl(genelist_id, updated_doc)
        return change_payload(resource="genelist", resource_id=genelist_id, action="update")

    def toggle(self, *, genelist_id: str) -> dict[str, Any]:
        """Toggle whether a genelist is active.

        Args:
            genelist_id: Genelist identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        genelist = self.gene_list_handler.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        new_status = not bool(genelist.get("is_active"))
        self.gene_list_handler.toggle_isgl_active(genelist_id, new_status)
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
        genelist = self.gene_list_handler.get_isgl(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        self.gene_list_handler.delete_genelist(genelist_id)
        return change_payload(resource="genelist", resource_id=genelist_id, action="delete")

    def genelist_exists(self, *, isgl_id: str) -> bool:
        """Return whether a genelist business key already exists."""
        normalized = str(isgl_id or "").strip()
        if not normalized:
            return False
        genelist = self.gene_list_handler.get_isgl(normalized)
        return bool(isinstance(genelist, dict) and (genelist.get("isgl_id") or genelist.get("_id")))
