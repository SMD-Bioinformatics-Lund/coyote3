"""Admin assay-panel resource-management workflows."""

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
from api.domain.common.errors import api_error


class AspService:
    """Assay-panel resource workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "AspService":
        """Build the service from the runtime store."""
        return cls(assay_panel_repository=store.assay_panel_repository)

    def __init__(self, *, assay_panel_repository: Any) -> None:
        """Create the service for assay-panel resource workflows."""
        self._spec = managed_resource_spec("asp")
        self.assay_panel_repository = assay_panel_repository

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the admin list payload for assay panels.

        Returns:
            dict[str, Any]: Panel rows and pagination metadata.
        """
        rows, total = self.assay_panel_repository.search_asps(q=q, page=page, per_page=per_page)
        panels = [dict(item) for item in rows if isinstance(item, dict)]
        total = int(total or 0)
        return {
            "panels": panels,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(self, *, actor_username: str) -> dict[str, Any]:
        """Return form context for creating an assay panel.

        Args:
            actor_username: Username used for default form metadata.

        Returns:
            dict[str, Any]: Form payload for the create view.
        """
        return {"form": build_managed_form(self._spec, actor_username=actor_username)}

    def context_payload(self, *, panel_id: str) -> dict[str, Any]:
        """Return form context for editing an assay panel.

        Args:
            panel_id: Panel identifier to load.

        Returns:
            dict[str, Any]: Existing panel data and edit form payload.
        """
        panel = self.assay_panel_repository.get_asp(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        form = build_managed_form(self._spec)
        if form.get("fields", {}).get("asp_group"):
            form["fields"]["asp_group"]["default"] = panel.get("asp_group", "")
        return {"panel": panel, "form": form}

    def create(
        self, *, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Create a new assay panel from submitted config data.

        Args:
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing panel config payload")
        config.setdefault("is_active", True)
        config["asp_id"] = config.get("asp_id")
        if not config.get("asp_id"):
            raise api_error(400, "Missing asp_id")
        existing_panel = self.assay_panel_repository.get_asp(str(config["asp_id"]))
        if isinstance(existing_panel, dict) and (
            existing_panel.get("asp_id") or existing_panel.get("_id")
        ):
            raise api_error(409, "Assay panel already exists")
        actor = current_actor(actor_username)
        now = utc_now()
        config.setdefault("created_by", actor)
        config.setdefault("created_on", now)
        config["updated_by"] = actor
        config["updated_on"] = now
        config.pop("gene_count", None)
        config["version"] = 1
        config.pop("version_history", None)
        config = _validated_doc(self._spec.collection, config)
        self.assay_panel_repository.create_panel(config)
        return change_payload(
            resource="asp", resource_id=str(config.get("asp_id", "unknown")), action="create"
        )

    def update(
        self, *, panel_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update an existing assay panel.

        Args:
            panel_id: Panel identifier to update.
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        panel = self.assay_panel_repository.get_asp(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing panel config payload")
        updated_doc = {**panel, **updated}
        updated_doc["asp_id"] = panel.get("asp_id", panel_id)
        updated_doc.pop("_id", None)
        actor = current_actor(actor_username)
        now = utc_now()
        updated_doc["created_by"] = panel.get("created_by") or actor
        updated_doc["created_on"] = panel.get("created_on") or now
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = now
        updated_doc["is_active"] = True
        updated_doc["version"] = 1
        updated_doc.pop("version_history", None)
        updated_doc.pop("retired_by", None)
        updated_doc.pop("retired_on", None)
        updated_doc.pop("retired_reason", None)
        updated_doc = _validated_doc(self._spec.collection, updated_doc)
        self.assay_panel_repository.update_asp(panel_id, updated_doc)
        return change_payload(resource="asp", resource_id=panel_id, action="update")

    def toggle(self, *, panel_id: str) -> dict[str, Any]:
        """Toggle whether an assay panel is active.

        Args:
            panel_id: Panel identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        panel = self.assay_panel_repository.get_asp(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        new_status = not bool(panel.get("is_active"))
        self.assay_panel_repository.toggle_asp_active(panel_id, new_status)
        payload = change_payload(resource="asp", resource_id=panel_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, panel_id: str) -> dict[str, Any]:
        """Delete an existing assay panel.

        Args:
            panel_id: Panel identifier to delete.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        panel = self.assay_panel_repository.get_asp(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        self.assay_panel_repository.delete_panel(panel_id)
        return change_payload(resource="asp", resource_id=panel_id, action="delete")

    def panel_exists(self, *, asp_id: str) -> bool:
        """Return whether an assay panel business key already exists."""
        normalized = str(asp_id or "").strip()
        if not normalized:
            return False
        panel = self.assay_panel_repository.get_asp(normalized)
        return bool(isinstance(panel, dict) and (panel.get("asp_id") or panel.get("_id")))
