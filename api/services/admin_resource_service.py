"""Admin resource workflow services for panels, genelists, assay configs, samples, and schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category, managed_resource_spec
from api.contracts.managed_ui_schemas import build_managed_schema, build_managed_schema_bundle
from api.contracts.schemas import normalize_collection_document
from api.core.admin.sample_deletion import SampleDeletionService, delete_all_sample_traces
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository, AdminSampleDeletionRepository
from api.runtime import app as runtime_app
from api.services.management_common import (
    admin_list_pagination,
    current_actor,
    inject_version_history,
    mutation_payload,
    utc_now,
)


def _normalize_asp_category(value: Any) -> str:
    """Normalize ASP category labels to managed DNA/RNA categories."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "DNA",
        "somatic": "DNA",
        "rna": "RNA",
    }
    return mapping.get(raw, str(value or "").strip().upper() or "DNA")


def _normalize_asp_category_doc(value: Any) -> str:
    """Normalize ASP category labels for persisted document payloads."""
    raw = str(value or "").strip().lower()
    mapping = {
        "dna": "dna",
        "somatic": "dna",
        "rna": "rna",
    }
    return mapping.get(raw, raw or "dna")


_DEPRECATED_SNV_FILTER_KEYS: tuple[str, ...] = (
    "snv_mode",
    "snv_require_case_gt_type",
    "snv_enable_control_guard",
    "snv_enable_popfreq_guard",
    "snv_enable_consequence_guard",
    "snv_allow_germline_escape",
    "snv_allow_cebpa_germline_escape",
    "snv_allow_flt3_large_indel_escape",
    "snv_allow_tert_nfkbie_regulatory_escape",
    "snv_gene_region_allow",
    "snv_gene_consequence_allow",
    "cnv_mode",
    "cnv_enable_normal_guard",
    "cnv_enable_ratio_guard",
    "cnv_enable_size_guard",
    "cnv_enable_panel_gene_guard",
    "fusion_mode",
    "fusion_enable_callers_guard",
    "fusion_enable_effects_guard",
    "fusion_enable_spanning_guard",
    "fusion_enable_gene_scope_guard",
    "fusion_enable_desc_guard",
)


def _sanitize_aspc_filters(config: dict[str, Any]) -> None:
    filters = config.get("filters")
    if not isinstance(filters, dict):
        return
    for key in _DEPRECATED_SNV_FILTER_KEYS:
        filters.pop(key, None)


def _validated_doc(collection: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate + normalize payload using collection Pydantic contract."""
    try:
        return normalize_collection_document(collection, payload)
    except Exception as exc:
        raise api_error(400, f"Invalid {collection} payload: {exc}") from exc


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


class AdminAspcService:
    """Own assay-configuration resource-management workflows."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()

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

    def _decorate_aspc_schema_options(
        self, *, schema: dict[str, Any], schema_category: str, assay_name: str | None
    ) -> None:
        if schema_category == "DNA":
            conseq_options = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
            self._set_group_field_options(
                schema, top_field="filters", subfield_key="vep_consequences", options=conseq_options
            )
            isgl_options = self._resolve_isgl_options(assay_name=assay_name)
            self._set_group_field_options(
                schema,
                top_field="filters",
                subfield_key="genelists",
                options=isgl_options.get("genelists", []),
            )
            self._set_group_field_options(
                schema,
                top_field="filters",
                subfield_key="cnv_genelists",
                options=isgl_options.get("cnv_genelists", []),
            )
        else:
            isgl_options = self._resolve_isgl_options(assay_name=assay_name)
            self._set_group_field_options(
                schema,
                top_field="filters",
                subfield_key="fusion_genelists",
                options=isgl_options.get("fusion_genelists", []),
            )
        query_profile_options = self._resolve_query_profile_options(assay_name=assay_name)
        if "snv_query_profile_id" in schema.get("fields", {}):
            schema["fields"]["snv_query_profile_id"]["options"] = query_profile_options["snv"]
        if "cnv_query_profile_id" in schema.get("fields", {}):
            schema["fields"]["cnv_query_profile_id"]["options"] = query_profile_options["cnv"]
        if "fusion_query_profile_id" in schema.get("fields", {}):
            schema["fields"]["fusion_query_profile_id"]["options"] = query_profile_options["fusion"]
        if "transloc_query_profile_id" in schema.get("fields", {}):
            schema["fields"]["transloc_query_profile_id"]["options"] = query_profile_options[
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

    def create_context_payload(
        self, *, category: str, schema_id: str | None, actor_username: str
    ) -> dict[str, Any]:
        """Create context payload.

        Args:
            category (str): Value for ``category``.
            schema_id (str | None): Value for ``schema_id``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        schema_category = str(category or "DNA").upper()
        spec = aspc_spec_for_category(schema_category)
        schemas, selected_schema = build_managed_schema_bundle(spec)
        if schema_id and schema_id != selected_schema.get("schema_id"):
            raise api_error(404, "Selected schema not found")
        schema = self.repository.clone_schema(selected_schema)
        assay_panels = self.repository.list_panels(is_active=True)
        prefill_map: dict[str, dict[str, Any]] = {}
        valid_assay_ids: list[str] = []
        env_options = schema.get("fields", {}).get("environment", {}).get("options", [])
        for panel in assay_panels:
            panel_category = _normalize_asp_category(panel.get("asp_category"))
            if panel_category == schema_category:
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
        schema["fields"]["assay_name"]["options"] = valid_assay_ids
        self._decorate_aspc_schema_options(
            schema=schema,
            schema_category=schema_category,
            assay_name=None,
        )
        query_profile_options = self._resolve_query_profile_options(assay_name=None)
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()
        return {
            "category": schema_category,
            "schemas": schemas,
            "selected_schema": selected_schema,
            "schema": schema,
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
        schema = self.repository.clone_schema(build_managed_schema(spec))
        self._decorate_aspc_schema_options(
            schema=schema,
            schema_category=category,
            assay_name=str(assay_config.get("assay_name", "") or ""),
        )
        query_profile_options = self._resolve_query_profile_options(
            assay_name=str(assay_config.get("assay_name", "") or ""),
            environment=str(assay_config.get("environment", "") or ""),
        )
        return {
            "assay_config": assay_config,
            "schema": schema,
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
        selected_schema_id = payload.get("schema_id")
        if selected_schema_id and selected_schema_id != spec.schema_id:
            raise api_error(404, "Selected schema not found")
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
        updated_doc["updated_by"] = current_actor(actor_username)
        updated_doc["updated_on"] = utc_now()
        updated_doc["version"] = int(assay_config.get("version", 1) or 1) + 1
        panel = self.repository.get_panel(str(updated_doc.get("assay_name", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        updated_doc = inject_version_history(
            actor_username=current_actor(actor_username),
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


class AdminQueryProfileService:
    """Own query-profile option lookups for ASPC forms."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()
        self._aspc_service = AdminAspcService(repository=self.repository)

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


class AdminSampleService:
    """Own admin sample-management and deletion workflows."""

    def __init__(self, repository: AdminRepository | None = None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or AdminRepository()
        if not SampleDeletionService.has_repository():
            SampleDeletionService.set_repository(AdminSampleDeletionRepository())

    def list_payload(
        self, *, assays: list[str], search: str, page: int = 1, per_page: int = 30
    ) -> dict[str, Any]:
        """List payload.

        Args:
            assays (list[str]): Value for ``assays``.
            search (str): Value for ``search``.

        Returns:
            dict[str, Any]: The function result.
        """
        samples, total = self.repository.list_samples_for_admin(
            assays=assays,
            search=search,
            page=page,
            per_page=per_page,
        )
        return {
            "samples": samples,
            "pagination": admin_list_pagination(
                q=search,
                page=page,
                per_page=per_page,
                total=total,
            ),
        }

    def context_payload(self, *, sample_id: str) -> dict[str, Any]:
        """Context payload.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_doc = self.repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        return {"sample": sample_doc}

    def update(
        self, *, sample_id: str, payload: dict[str, Any], actor_username: str
    ) -> dict[str, Any]:
        """Update.

        Args:
            sample_id (str): Value for ``sample_id``.
            payload (dict[str, Any]): Value for ``payload``.
            actor_username (str): Value for ``actor_username``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_doc = self.repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        sample_obj = sample_doc.get("_id")
        updated_sample = payload.get("sample", {})
        if not updated_sample:
            raise api_error(400, "Missing sample payload")
        updated_sample["updated_on"] = utc_now()
        updated_sample["updated_by"] = current_actor(actor_username)
        updated_sample = util.admin.restore_objectids(deepcopy(updated_sample))
        updated_sample["_id"] = sample_obj
        self.repository.update_sample(sample_obj, updated_sample)
        return mutation_payload(resource="sample", resource_id=str(sample_obj), action="update")

    def delete(self, *, sample_id: str) -> dict[str, Any]:
        """Delete.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_name = self.repository.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = delete_all_sample_traces(sample_id)
        payload = mutation_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload
