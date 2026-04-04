"""Admin assay-configuration and query-profile resource-management workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category
from api.extensions import store
from api.http import api_error
from api.runtime_state import app as runtime_app
from api.services.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    current_actor,
    inject_version_history,
    mutation_payload,
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

    def __init__(self, repository: Any | None = None) -> None:
        """Build the service with an admin repository."""
        self.repository = repository or store.get_admin_repository()

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
        docs = self.repository.list_genelists()
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

    def _resolve_query_profile_options(
        self, *, assay_name: str | None, environment: str | None = None
    ) -> dict[str, list[str]]:
        assay = str(assay_name or "").strip()
        env = str(environment or "").strip().lower()
        profiles = self.repository.list_query_profiles(is_active=True)
        by_type: dict[str, list[str]] = {
            "snv": [],
            "cnv": [],
            "fusion": [],
            "transloc": [],
        }
        for doc in profiles:
            profile_id = str(doc.get("query_profile_id") or "").strip()
            if not profile_id:
                continue
            if assay and str(doc.get("assay_name") or "").strip() not in {"", assay}:
                continue
            if env and str(doc.get("environment") or "").strip().lower() not in {"", env}:
                continue
            resource_type = str(doc.get("resource_type") or "").strip().lower()
            if resource_type in by_type:
                by_type[resource_type].append(profile_id)
        return {k: list(dict.fromkeys(v)) for k, v in by_type.items()}

    def _attach_query_profile_refs(self, config: dict[str, Any]) -> None:
        """Move UI helper fields into query.profiles persistent shape."""
        snv = str(config.pop("snv_query_profile_id", "") or "").strip()
        cnv = str(config.pop("cnv_query_profile_id", "") or "").strip()
        fusion = str(config.pop("fusion_query_profile_id", "") or "").strip()
        transloc = str(config.pop("transloc_query_profile_id", "") or "").strip()
        query_payload = config.get("query")
        if not isinstance(query_payload, dict):
            query_payload = {}
        profiles = query_payload.get("profiles")
        if not isinstance(profiles, dict):
            profiles = {}
        if snv:
            profiles["snv"] = snv
            query_payload.pop("snv", None)
        else:
            profiles.pop("snv", None)
        if cnv:
            profiles["cnv"] = cnv
            query_payload.pop("cnv", None)
        else:
            profiles.pop("cnv", None)
        if fusion:
            profiles["fusion"] = fusion
            query_payload.pop("fusion", None)
        else:
            profiles.pop("fusion", None)
        if transloc:
            profiles["transloc"] = transloc
            query_payload.pop("transloc", None)
        else:
            profiles.pop("transloc", None)
        if profiles:
            query_payload["profiles"] = profiles
        else:
            query_payload.pop("profiles", None)
        config["query"] = query_payload

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
        query_profile_options = self._resolve_query_profile_options(assay_name=assay_name)
        if "snv_query_profile_id" in form.get("fields", {}):
            form["fields"]["snv_query_profile_id"]["options"] = query_profile_options["snv"]
        if "cnv_query_profile_id" in form.get("fields", {}):
            form["fields"]["cnv_query_profile_id"]["options"] = query_profile_options["cnv"]
        if "fusion_query_profile_id" in form.get("fields", {}):
            form["fields"]["fusion_query_profile_id"]["options"] = query_profile_options["fusion"]
        if "transloc_query_profile_id" in form.get("fields", {}):
            form["fields"]["transloc_query_profile_id"]["options"] = query_profile_options[
                "transloc"
            ]

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """List payload.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_configs, total = self.repository.search_assay_configs(
            q=q,
            page=page,
            per_page=per_page,
        )
        return {
            "assay_configs": assay_configs,
            "pagination": admin_list_pagination(q=q, page=page, per_page=per_page, total=total),
        }

    def create_context_payload(self, *, category: str, actor_username: str) -> dict[str, Any]:
        """Create context payload.

        Args:
            category (str): Value for ``category``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        form_category = str(category or "DNA").upper()
        spec = aspc_spec_for_category(form_category)
        form = build_managed_form(spec, actor_username=actor_username)
        assay_panels = self.repository.list_panels(is_active=True)
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
                envs = self.repository.get_available_assay_envs(assay_id, env_options)
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
        query_profile_options = self._resolve_query_profile_options(assay_name=None)
        return {
            "category": form_category,
            "form": form,
            "prefill_map": prefill_map,
            "query_profile_options": query_profile_options,
        }

    def context_payload(self, *, assay_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            assay_id (str): Value for ``assay_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        assay_config = deepcopy(assay_config)
        query_payload = assay_config.get("query")
        profile_refs = query_payload.get("profiles", {}) if isinstance(query_payload, dict) else {}
        if isinstance(profile_refs, dict):
            assay_config["snv_query_profile_id"] = profile_refs.get("snv", "")
            assay_config["cnv_query_profile_id"] = profile_refs.get("cnv", "")
            assay_config["fusion_query_profile_id"] = profile_refs.get("fusion", "")
            assay_config["transloc_query_profile_id"] = profile_refs.get("transloc", "")
        panel = self.repository.get_panel(str(assay_config.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        form = build_managed_form(spec)
        self._decorate_form_options(
            form=form,
            form_category=category,
            assay_name=str(assay_config.get("assay_name", "") or ""),
        )
        query_profile_options = self._resolve_query_profile_options(
            assay_name=str(assay_config.get("assay_name", "") or ""),
            environment=str(assay_config.get("environment", "") or ""),
        )
        return {
            "assay_config": assay_config,
            "form": form,
            "query_profile_options": query_profile_options,
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
            raise api_error(400, "Missing assay config payload")
        _sanitize_aspc_filters(config)
        self._attach_query_profile_refs(config)
        config.setdefault("is_active", True)
        config["asp_category"] = _normalize_asp_category_doc(config.get("asp_category"))
        config["aspc_id"] = (
            config.get("aspc_id")
            or f"{str(config.get('assay_name', '')).strip()}:{str(config.get('environment', '')).strip().lower()}"
        )
        if not config.get("aspc_id"):
            raise api_error(400, "Missing aspc_id")
        existing_config = self.repository.get_assay_config(config.get("aspc_id"))
        if existing_config:
            raise api_error(409, "Assay config already exists")
        panel = self.repository.get_panel(str(config.get("assay_name", "")))
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
        self.repository.create_assay_config(config)
        return mutation_payload(
            resource="aspc", resource_id=str(config.get("aspc_id", "unknown")), action="create"
        )

    def update(
        self, *, assay_id: str, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Update.

        Args:
            assay_id (str): Value for ``assay_id``.
            payload (dict[str, Any]): Value for ``payload``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        updated_config = payload.get("config", {})
        if not updated_config:
            raise api_error(400, "Missing assay config payload")
        updated_doc = {**assay_config, **updated_config}
        _sanitize_aspc_filters(updated_doc)
        self._attach_query_profile_refs(updated_doc)
        updated_doc["asp_category"] = _normalize_asp_category_doc(updated_doc.get("asp_category"))
        updated_doc["aspc_id"] = assay_config.get("aspc_id", assay_id)
        updated_doc["_id"] = assay_config.get("_id")
        actor = current_actor(actor_username)
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(assay_config.get("version", 1) or 1) + 1
        panel = self.repository.get_panel(str(updated_doc.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        updated_doc = inject_version_history(
            actor_username=actor,
            new_config=updated_doc,
            old_config=assay_config,
            is_new=False,
        )
        updated_doc = _validated_doc(spec.collection, updated_doc)
        self.repository.update_assay_config(assay_id, updated_doc)
        return mutation_payload(resource="aspc", resource_id=assay_id, action="update")

    def toggle(self, *, assay_id: str) -> dict[str, Any]:
        """Toggle.

        Args:
            assay_id (str): Value for ``assay_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        new_status = not bool(assay_config.get("is_active"))
        self.repository.set_assay_config_active(assay_id, new_status)
        payload = mutation_payload(resource="aspc", resource_id=assay_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, assay_id: str) -> dict[str, Any]:
        """Delete.

        Args:
            assay_id (str): Value for ``assay_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        self.repository.delete_assay_config(assay_id)
        return mutation_payload(resource="aspc", resource_id=assay_id, action="delete")

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
        doc = self.repository.get_assay_config(resolved_id)
        return bool(isinstance(doc, dict) and (doc.get("aspc_id") or doc.get("_id")))

    def _resolve_query_profile_options(
        self,
        *,
        assay_name: str | None = None,
        assay_group: str | None = None,
        environment: str | None = None,
    ) -> dict[str, list[str]]:
        assay = str(assay_name or "").strip()
        group = str(assay_group or "").strip()
        env = str(environment or "").strip().lower()
        profiles = self.repository.list_query_profiles(is_active=True)
        assay_group_map = self.repository.get_assay_group_map()
        assay_to_groups: dict[str, set[str]] = {}
        for group_name, assays in assay_group_map.items():
            normalized_group = str(group_name or "").strip()
            if not normalized_group:
                continue
            for assay_doc in assays or []:
                assay_name_value = str(
                    (assay_doc or {}).get("assay_name") or (assay_doc or {}).get("asp_id") or ""
                ).strip()
                if not assay_name_value:
                    continue
                assay_to_groups.setdefault(assay_name_value, set()).add(normalized_group)
        by_type: dict[str, list[str]] = {"snv": [], "cnv": [], "fusion": [], "transloc": []}
        for doc in profiles:
            profile_id = str(doc.get("query_profile_id") or "").strip()
            if not profile_id:
                continue
            assay_groups = {
                str(v).strip() for v in (doc.get("assay_groups") or []) if str(v).strip()
            }
            assays = {str(v).strip() for v in (doc.get("assays") or []) if str(v).strip()}
            selected_groups = set()
            if assay:
                selected_groups.update(assay_to_groups.get(assay, set()))
            if group:
                selected_groups.add(group)
            if assay or selected_groups:
                matches_assays = bool(assays and assay and assay in assays)
                matches_groups = bool(
                    assay_groups and selected_groups and assay_groups.intersection(selected_groups)
                )
                if not matches_assays and not matches_groups and (assays or assay_groups):
                    continue
            if env and str(doc.get("environment") or "").strip().lower() not in {"", env}:
                continue
            resource_type = str(doc.get("resource_type") or "").strip().lower()
            if resource_type in by_type:
                by_type[resource_type].append(profile_id)
        return {k: list(dict.fromkeys(v)) for k, v in by_type.items()}


class QueryProfileService:
    """Query-profile option lookups for ASPC forms."""

    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository or store.get_admin_repository()
        self._aspc_service = AspcService(repository=self.repository)

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
