"""Admin genelist resource-management workflows."""

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


class AdminGenelistService:
    """Own genelist resource-management workflows."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()
        self._spec = managed_resource_spec("isgl")

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """List payload.

        Returns:
            dict[str, Any]: The function result.
        """
        genelists, total = self.repository.search_genelists(q=q, page=page, per_page=per_page)
        return {
            "genelists": genelists,
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
            raise api_error(404, "Genelist schema not found")
        schema = self.repository.clone_schema(selected_schema)
        schema["fields"]["assay_groups"]["options"] = self.repository.get_asp_groups()
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()
        return {
            "schemas": schemas,
            "selected_schema": selected_schema,
            "schema": schema,
            "assay_group_map": self.repository.get_assay_group_map(),
        }

    def context_payload(self, *, genelist_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            genelist_id (str): Value for ``genelist_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        schema = self.repository.clone_schema(build_managed_schema(self._spec))
        schema["fields"]["assay_groups"]["options"] = self.repository.get_asp_groups()
        schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
        schema["fields"]["assays"]["default"] = genelist.get("assays", [])
        return {
            "genelist": genelist,
            "schema": schema,
            "assay_group_map": self.repository.get_assay_group_map(),
        }

    def view_context_payload(self, *, genelist_id: str, assay: str | None) -> dict[str, Any]:
        """Render the context payload view.

        Args:
            genelist_id (str): Value for ``genelist_id``.
            assay (str | None): Value for ``assay``.

        Returns:
            dict[str, Any]: The function result.
        """
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        all_genes = genelist.get("genes", [])
        assays = genelist.get("assays", [])
        filtered_genes = all_genes
        panel_germline_genes: list[str] = []
        if assay and assay in assays:
            panel = self.repository.get_panel(assay)
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
        """Create.

        Args:
            payload (dict[str, Any]): Value for ``payload``.

        Returns:
            dict[str, Any]: The function result.
        """
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing genelist config payload")
        config.setdefault("is_active", True)
        config["isgl_id"] = config.get("isgl_id") or config.get("name")
        if not config.get("isgl_id"):
            raise api_error(400, "Missing isgl_id")
        existing_genelist = self.repository.get_genelist(str(config["isgl_id"]))
        if isinstance(existing_genelist, dict) and (
            existing_genelist.get("isgl_id") or existing_genelist.get("_id")
        ):
            raise api_error(409, "Genelist already exists")
        selected_schema_id = payload.get("schema_id")
        if selected_schema_id and selected_schema_id != self._spec.schema_id:
            raise api_error(404, "Genelist schema not found")
        now = utc_now()
        config.setdefault("created_by", current_actor(actor_username))
        config.setdefault("created_on", now)
        config["updated_by"] = current_actor(actor_username)
        config["updated_on"] = now
        config = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=config,
            is_new=True,
        )
        config = _validated_doc(self._spec.collection, config)
        self.repository.create_genelist(config)
        return mutation_payload(
            resource="genelist", resource_id=str(config.get("isgl_id", "unknown")), action="create"
        )

    def update(
        self, *, genelist_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update.

        Args:
            genelist_id (str): Value for ``genelist_id``.
            payload (dict[str, Any]): Value for ``payload``.

        Returns:
            dict[str, Any]: The function result.
        """
        genelist = self.repository.get_genelist(genelist_id)
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
        updated_doc["updated_by"] = current_actor(actor_username)
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(genelist.get("version", 1) or 1) + 1
        updated_doc = inject_version_history(
            actor_username=current_actor(actor_username),
            new_config=updated_doc,
            old_config=genelist,
            is_new=False,
        )
        updated_doc = _validated_doc(self._spec.collection, updated_doc)
        self.repository.update_genelist(genelist_id, updated_doc)
        return mutation_payload(resource="genelist", resource_id=genelist_id, action="update")

    def toggle(self, *, genelist_id: str) -> dict[str, Any]:
        """Toggle.

        Args:
            genelist_id (str): Value for ``genelist_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        new_status = not bool(genelist.get("is_active"))
        self.repository.set_genelist_active(genelist_id, new_status)
        payload = mutation_payload(resource="genelist", resource_id=genelist_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, genelist_id: str) -> dict[str, Any]:
        """Delete.

        Args:
            genelist_id (str): Value for ``genelist_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        self.repository.delete_genelist(genelist_id)
        return mutation_payload(resource="genelist", resource_id=genelist_id, action="delete")

    def genelist_exists(self, *, isgl_id: str) -> bool:
        """Return whether a genelist business key already exists."""
        normalized = str(isgl_id or "").strip()
        if not normalized:
            return False
        genelist = self.repository.get_genelist(normalized)
        return bool(isinstance(genelist, dict) and (genelist.get("isgl_id") or genelist.get("_id")))
