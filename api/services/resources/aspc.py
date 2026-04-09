"""Admin assay-configuration and query-profile resource-management workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category
from api.http import api_error
from api.runtime_state import app as runtime_app
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    inject_version_history,
    utc_now,
)
from api.services.resources.helpers import (
    _normalize_asp_category,
    _normalize_asp_category_doc,
    _sanitize_aspc_filters,
    _validated_doc,
)


class AspcService:
    """Assay-configuration resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        common_util: Any,
    ) -> "AspcService":
        """Build the service from the shared store."""
        return cls(
            assay_configuration_handler=store.assay_configuration_handler,
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            common_util=common_util,
        )

    def __init__(
        self,
        *,
        assay_configuration_handler: Any,
        assay_panel_handler: Any,
        gene_list_handler: Any,
        common_util: Any,
    ) -> None:
        """Create the service for assay-configuration resource workflows."""
        self.assay_configuration_handler = assay_configuration_handler
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.common_util = common_util

    @staticmethod
    def _set_group_field_options(
        schema: dict[str, Any], *, top_field: str, subfield_key: str, options: list[str]
    ) -> None:
        top = schema.get("fields", {}).get(top_field, {})
        for group in top.get("groups", []) or []:
            for subfield in group.get("fields", []) or []:
                if subfield.get("key") == subfield_key:
                    subfield["options"] = list(dict.fromkeys([str(o) for o in options if str(o)]))
                    return

    def _resolve_isgl_options(self, *, assay_name: str | None) -> dict[str, list[str]]:
        docs = [
            dict(item)
            for item in (self.gene_list_handler.get_all_isgl() or [])
            if isinstance(item, dict)
        ]
        assay = str(assay_name or "").strip()
        result: dict[str, list[str]] = {
            "genelists": [],
            "cnv_genelists": [],
            "fusion_genelists": [],
        }
        for doc in docs:
            if not doc.get("is_active", True):
                continue
            doc_assays = [str(v) for v in (doc.get("assays") or []) if str(v)]
            if assay and doc_assays and assay not in doc_assays:
                continue
            isgl_id = str(doc.get("isgl_id") or "").strip()
            if not isgl_id:
                continue
            list_types = {str(v).strip().lower() for v in (doc.get("list_type") or []) if str(v)}
            if "small_variants_genelist" in list_types:
                result["genelists"].append(isgl_id)
            if "cnv_genelist" in list_types:
                result["cnv_genelists"].append(isgl_id)
            if "fusion_genelist" in list_types or "fusionlist" in list_types:
                result["fusion_genelists"].append(isgl_id)
        return {k: list(dict.fromkeys(v)) for k, v in result.items()}

    def _decorate_form_options(
        self, *, form: dict[str, Any], form_category: str, assay_name: str | None
    ) -> None:
        if form_category == "DNA":
            conseq_options = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
            self._set_group_field_options(
                form, top_field="filters", subfield_key="vep_consequences", options=conseq_options
            )
            isgl_options = self._resolve_isgl_options(assay_name=assay_name)
            self._set_group_field_options(
                form,
                top_field="filters",
                subfield_key="genelists",
                options=isgl_options.get("genelists", []),
            )
            self._set_group_field_options(
                form,
                top_field="filters",
                subfield_key="cnv_genelists",
                options=isgl_options.get("cnv_genelists", []),
            )
        else:
            isgl_options = self._resolve_isgl_options(assay_name=assay_name)
            self._set_group_field_options(
                form,
                top_field="filters",
                subfield_key="fusion_genelists",
                options=isgl_options.get("fusion_genelists", []),
            )

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the admin list payload for assay configurations.

        Returns:
            dict[str, Any]: Assay-config rows and pagination metadata.
        """
        rows, total = self.assay_configuration_handler.search_aspcs(
            q=q,
            page=page,
            per_page=per_page,
        )
        assay_configs = [dict(item) for item in rows if isinstance(item, dict)]
        total = int(total or 0)
        return {
            "assay_configs": assay_configs,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(self, *, category: str, actor_username: str) -> dict[str, Any]:
        """Return form context for creating an assay configuration.

        Args:
            category: Requested assay category.
            actor_username: Username used for default form metadata.

        Returns:
            dict[str, Any]: Form payload and prefill map.
        """
        form_category = str(category or "DNA").upper()
        spec = aspc_spec_for_category(form_category)
        form = build_managed_form(spec, actor_username=actor_username)
        assay_panels = [
            dict(item)
            for item in (self.assay_panel_handler.get_all_asps(is_active=True) or [])
            if isinstance(item, dict)
        ]
        prefill_map: dict[str, dict[str, Any]] = {}
        valid_assay_ids: list[str] = []
        env_options = form.get("fields", {}).get("environment", {}).get("options", [])
        for panel in assay_panels:
            panel_category = _normalize_asp_category(panel.get("asp_category"))
            if panel_category == form_category:
                assay_id = str(
                    panel.get("asp_id") or panel.get("assay_name") or panel.get("_id") or ""
                )
                if not assay_id:
                    continue
                envs = list(
                    self.assay_configuration_handler.get_available_assay_envs(assay_id, env_options)
                    or []
                )
                if envs:
                    isgl_options = self._resolve_isgl_options(assay_name=assay_id)
                    valid_assay_ids.append(assay_id)
                    prefill_map[assay_id] = {
                        "display_name": panel.get("display_name"),
                        "asp_group": panel.get("asp_group"),
                        "asp_category": panel_category,
                        "platform": panel.get("platform"),
                        "environment": envs,
                        "genelists": isgl_options.get("genelists", []),
                        "cnv_genelists": isgl_options.get("cnv_genelists", []),
                        "fusion_genelists": isgl_options.get("fusion_genelists", []),
                    }
        form["fields"]["assay_name"]["options"] = valid_assay_ids
        self._decorate_form_options(
            form=form,
            form_category=form_category,
            assay_name=None,
        )
        return {
            "category": form_category,
            "form": form,
            "prefill_map": prefill_map,
        }

    def context_payload(self, *, assay_id: str) -> dict[str, Any]:
        """Return form context for editing an assay configuration.

        Args:
            assay_id: Assay-config identifier to load.

        Returns:
            dict[str, Any]: Existing config data and edit form payload.
        """
        assay_config = self.assay_configuration_handler.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        assay_config = deepcopy(assay_config)
        panel = self.assay_panel_handler.get_asp(str(assay_config.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        form = build_managed_form(spec)
        self._decorate_form_options(
            form=form,
            form_category=category,
            assay_name=str(assay_config.get("assay_name", "") or ""),
        )
        return {
            "assay_config": assay_config,
            "form": form,
        }

    def create(
        self, *, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Create a new assay configuration from submitted config data.

        Args:
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing assay config payload")
        _sanitize_aspc_filters(config)
        config.setdefault("is_active", True)
        config["asp_category"] = _normalize_asp_category_doc(config.get("asp_category"))
        config["aspc_id"] = (
            config.get("aspc_id")
            or f"{str(config.get('assay_name', '')).strip()}:{str(config.get('environment', '')).strip().lower()}"
        )
        if not config.get("aspc_id"):
            raise api_error(400, "Missing aspc_id")
        existing_config = self.assay_configuration_handler.get_aspc_with_id(config.get("aspc_id"))
        if existing_config:
            raise api_error(409, "Assay config already exists")
        panel = self.assay_panel_handler.get_asp(str(config.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
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
        config = _validated_doc(spec.collection, config)
        self.assay_configuration_handler.create_aspc(config)
        return change_payload(
            resource="aspc", resource_id=str(config.get("aspc_id", "unknown")), action="create"
        )

    def update(
        self, *, assay_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update an existing assay configuration.

        Args:
            assay_id: Assay-config identifier to update.
            payload: Submitted config payload.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        assay_config = self.assay_configuration_handler.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        updated_config = payload.get("config", {})
        if not updated_config:
            raise api_error(400, "Missing assay config payload")
        updated_doc = {**assay_config, **updated_config}
        _sanitize_aspc_filters(updated_doc)
        updated_doc["asp_category"] = _normalize_asp_category_doc(updated_doc.get("asp_category"))
        updated_doc["aspc_id"] = assay_config.get("aspc_id", assay_id)
        updated_doc["_id"] = assay_config.get("_id")
        actor = current_actor(actor_username)
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(assay_config.get("version", 1) or 1) + 1
        panel = self.assay_panel_handler.get_asp(str(updated_doc.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        updated_doc = inject_version_history(
            actor_username=actor,
            new_config=updated_doc,
            old_config=assay_config,
            is_new=False,
        )
        updated_doc = _validated_doc(spec.collection, updated_doc)
        self.assay_configuration_handler.update_aspc(assay_id, updated_doc)
        return change_payload(resource="aspc", resource_id=assay_id, action="update")

    def toggle(self, *, assay_id: str) -> dict[str, Any]:
        """Toggle whether an assay configuration is active.

        Args:
            assay_id: Assay-config identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        assay_config = self.assay_configuration_handler.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        new_status = not bool(assay_config.get("is_active"))
        self.assay_configuration_handler.toggle_aspc_active(assay_id, new_status)
        payload = change_payload(resource="aspc", resource_id=assay_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, assay_id: str) -> dict[str, Any]:
        """Delete an existing assay configuration.

        Args:
            assay_id: Assay-config identifier to delete.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        assay_config = self.assay_configuration_handler.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        self.assay_configuration_handler.delete_aspc(assay_id)
        return change_payload(resource="aspc", resource_id=assay_id, action="delete")

    def assay_config_exists(
        self,
        *,
        aspc_id: str | None = None,
        assay_name: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Return whether an assay config business key already exists."""
        resolved_id = str(aspc_id or "").strip()
        if not resolved_id:
            assay = str(assay_name or "").strip()
            env = str(environment or "").strip().lower()
            if assay and env:
                resolved_id = f"{assay}:{env}"
        if not resolved_id:
            return False
        doc = self.assay_configuration_handler.get_aspc_with_id(resolved_id)
        return bool(isinstance(doc, dict) and (doc.get("aspc_id") or doc.get("_id")))

    def _resolve_query_profile_options(
        self,
        *,
        assay_name: str | None = None,
        assay_group: str | None = None,
        environment: str | None = None,
    ) -> dict[str, list[str]]:
        _ = (assay_name, assay_group, environment)
        return {"snv": [], "cnv": [], "fusion": [], "transloc": []}


class QueryProfileService:
    """Query-profile option lookups for ASPC forms."""

    def __init__(self, *, aspc_service: AspcService) -> None:
        self._aspc_service = aspc_service

    def options_payload(
        self,
        *,
        assay_name: str | None = None,
        assay_group: str | None = None,
        environment: str | None = None,
    ) -> dict[str, Any]:
        """Return active query-profile options filtered by assay/group/environment."""
        return {
            "options": self._aspc_service._resolve_query_profile_options(
                assay_name=assay_name,
                assay_group=assay_group,
                environment=environment,
            )
        }
