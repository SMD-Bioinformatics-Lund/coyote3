"""Admin assay-panel resource-management workflows."""

from __future__ import annotations

from typing import Any

from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_managed_schema, build_managed_schema_bundle
from api.http import api_error
from api.repositories.admin_repository import AdminRepository
from api.services.accounts.common import (
    admin_list_pagination,
    current_actor,
    inject_version_history,
    mutation_payload,
    utc_now,
)
from api.services.admin_resource.helpers import _validated_doc


class AdminPanelService:
    """Own assay-panel resource-management workflows."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()
        self._spec = managed_resource_spec("asp")

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """List payload.

        Returns:
            dict[str, Any]: The function result.
        """
        panels, total = self.repository.search_panels(q=q, page=page, per_page=per_page)
        return {
            "panels": panels,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(
        self, *, schema_id: str | None, actor_username: str
    ) -> dict[str, Any]:
        """Create context payload.

        Args:
            schema_id (str | None): Value for ``schema_id``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schemas, selected_schema = build_managed_schema_bundle(self._spec)
        if schema_id and schema_id != selected_schema.get("schema_id"):
            raise api_error(404, "Selected schema not found")
        schema = self.repository.clone_schema(selected_schema)
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()
        return {"schemas": schemas, "selected_schema": selected_schema, "schema": schema}

    def context_payload(self, *, panel_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            panel_id (str): Value for ``panel_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        schema = build_managed_schema(self._spec)
        return {"panel": panel, "schema": schema}

    def create(
        self, *, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Create.

        Args:
            payload (dict[str, Any]): Value for ``payload``.

        Returns:
            dict[str, Any]: The function result.
        """
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing panel config payload")
        config.setdefault("is_active", True)
        config["asp_id"] = config.get("asp_id") or config.get("assay_name")
        if not config.get("asp_id"):
            raise api_error(400, "Missing asp_id")
        existing_panel = self.repository.get_panel(str(config["asp_id"]))
        if isinstance(existing_panel, dict) and (
            existing_panel.get("asp_id") or existing_panel.get("_id")
        ):
            raise api_error(409, "Assay panel already exists")
        selected_schema_id = payload.get("schema_id")
        if selected_schema_id and selected_schema_id != self._spec.schema_id:
            raise api_error(404, "Selected schema not found")
        now = utc_now()
        config.setdefault("created_by", current_actor(actor_username))
        config.setdefault("created_on", now)
        config["updated_by"] = current_actor(actor_username)
        config["updated_on"] = now
        config.pop("gene_count", None)
        config = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=config,
            is_new=True,
        )
        config = _validated_doc(self._spec.collection, config)
        self.repository.create_panel(config)
        return mutation_payload(
            resource="asp", resource_id=str(config.get("asp_id", "unknown")), action="create"
        )

    def update(
        self, *, panel_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update.

        Args:
            panel_id (str): Value for ``panel_id``.
            payload (dict[str, Any]): Value for ``payload``.

        Returns:
            dict[str, Any]: The function result.
        """
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing panel config payload")
        updated_doc = {**panel, **updated}
        updated_doc["asp_id"] = panel.get("asp_id", panel_id)
        updated_doc["_id"] = panel.get("_id")
        updated_doc["updated_by"] = current_actor(actor_username)
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(panel.get("version", 1) or 1) + 1
        updated_doc = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_doc,
            old_config=panel,
            is_new=False,
        )
        updated_doc = _validated_doc(self._spec.collection, updated_doc)
        self.repository.update_panel(panel_id, updated_doc)
        return mutation_payload(resource="asp", resource_id=panel_id, action="update")

    def toggle(self, *, panel_id: str) -> dict[str, Any]:
        """Toggle.

        Args:
            panel_id (str): Value for ``panel_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        new_status = not bool(panel.get("is_active"))
        self.repository.set_panel_active(panel_id, new_status)
        payload = mutation_payload(resource="asp", resource_id=panel_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, panel_id: str) -> dict[str, Any]:
        """Delete.

        Args:
            panel_id (str): Value for ``panel_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        self.repository.delete_panel(panel_id)
        return mutation_payload(resource="asp", resource_id=panel_id, action="delete")

    def panel_exists(self, *, asp_id: str) -> bool:
        """Return whether an assay panel business key already exists."""
        normalized = str(asp_id or "").strip()
        if not normalized:
            return False
        panel = self.repository.get_panel(normalized)
        return bool(isinstance(panel, dict) and (panel.get("asp_id") or panel.get("_id")))
