"""Admin resource workflow services for panels, genelists, assay configs, samples, and schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.admin.sample_deletion import SampleDeletionService, delete_all_sample_traces
from api.extensions import util
from api.http import api_error
from api.repositories.admin_repository import AdminRepository, AdminSampleDeletionRepository
from api.runtime import app as runtime_app
from api.services.admin_common import current_actor, mutation_payload, utc_now


class AdminPanelService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_payload(self) -> dict[str, Any]:
        return {"panels": self.repository.list_panels()}

    def create_context_payload(self, *, schema_id: str | None, actor_username: str) -> dict[str, Any]:
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="asp_schema",
            schema_category="ASP",
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, "No active panel schemas found")
        if not selected_schema:
            raise api_error(404, "Selected schema not found")
        schema = self.repository.clone_schema(selected_schema)
        schema["fields"]["created_by"]["default"] = current_actor(actor_username)
        schema["fields"]["created_on"]["default"] = utc_now()
        schema["fields"]["updated_by"]["default"] = current_actor(actor_username)
        schema["fields"]["updated_on"]["default"] = utc_now()
        return {"schemas": schemas, "selected_schema": selected_schema, "schema": schema}

    def context_payload(self, *, panel_id: str) -> dict[str, Any]:
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        schema = self.repository.get_schema(panel.get("schema_name", "ASP-Schema"))
        if not schema:
            raise api_error(404, "Schema not found for panel")
        return {"panel": panel, "schema": schema}

    def create(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing panel config payload")
        config.setdefault("is_active", True)
        config["asp_id"] = config.get("asp_id") or config.get("_id") or config.get("assay_name")
        self.repository.create_panel(config)
        return mutation_payload(resource="asp", resource_id=str(config.get("asp_id", "unknown")), action="create")

    def update(self, *, panel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing panel config payload")
        updated["asp_id"] = panel.get("asp_id", panel_id)
        updated["_id"] = panel.get("_id")
        self.repository.update_panel(panel_id, updated)
        return mutation_payload(resource="asp", resource_id=panel_id, action="update")

    def toggle(self, *, panel_id: str) -> dict[str, Any]:
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        new_status = not bool(panel.get("is_active"))
        self.repository.set_panel_active(panel_id, new_status)
        payload = mutation_payload(resource="asp", resource_id=panel_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, panel_id: str) -> dict[str, Any]:
        panel = self.repository.get_panel(panel_id)
        if not panel:
            raise api_error(404, "Panel not found")
        self.repository.delete_panel(panel_id)
        return mutation_payload(resource="asp", resource_id=panel_id, action="delete")


class AdminGenelistService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_payload(self) -> dict[str, Any]:
        return {"genelists": self.repository.list_genelists()}

    def create_context_payload(self, *, schema_id: str | None, actor_username: str) -> dict[str, Any]:
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="isgl_config",
            schema_category="ISGL",
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, "No active genelist schemas found")
        if not selected_schema:
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
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        schema = self.repository.get_schema(genelist.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema not found for genelist")
        schema = self.repository.clone_schema(schema)
        schema["fields"]["assay_groups"]["options"] = self.repository.get_asp_groups()
        schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])
        schema["fields"]["assays"]["default"] = genelist.get("assays", [])
        return {
            "genelist": genelist,
            "schema": schema,
            "assay_group_map": self.repository.get_assay_group_map(),
        }

    def view_context_payload(self, *, genelist_id: str, assay: str | None) -> dict[str, Any]:
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

    def create(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing genelist config payload")
        config.setdefault("is_active", True)
        config["isgl_id"] = config.get("isgl_id") or config.get("_id") or config.get("name")
        self.repository.create_genelist(config)
        return mutation_payload(resource="genelist", resource_id=str(config.get("isgl_id", "unknown")), action="create")

    def update(self, *, genelist_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        updated = payload.get("config", {})
        if not updated:
            raise api_error(400, "Missing genelist config payload")
        updated["isgl_id"] = genelist.get("isgl_id", genelist_id)
        updated["_id"] = genelist.get("_id")
        self.repository.update_genelist(genelist_id, updated)
        return mutation_payload(resource="genelist", resource_id=genelist_id, action="update")

    def toggle(self, *, genelist_id: str) -> dict[str, Any]:
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        new_status = not bool(genelist.get("is_active"))
        self.repository.set_genelist_active(genelist_id, new_status)
        payload = mutation_payload(resource="genelist", resource_id=genelist_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, genelist_id: str) -> dict[str, Any]:
        genelist = self.repository.get_genelist(genelist_id)
        if not genelist:
            raise api_error(404, "Genelist not found")
        self.repository.delete_genelist(genelist_id)
        return mutation_payload(resource="genelist", resource_id=genelist_id, action="delete")


class AdminAspcService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_payload(self) -> dict[str, Any]:
        return {"assay_configs": self.repository.list_assay_configs()}

    def create_context_payload(self, *, category: str, schema_id: str | None, actor_username: str) -> dict[str, Any]:
        schema_category = str(category or "DNA").upper()
        schemas, selected_schema = self.repository.get_active_schema(
            schema_type="asp_config",
            schema_category=schema_category,
            schema_id=schema_id,
        )
        if not schemas:
            raise api_error(400, f"No active {schema_category} schemas found")
        if not selected_schema:
            raise api_error(404, "Selected schema not found")
        schema = self.repository.clone_schema(selected_schema)
        assay_panels = self.repository.list_panels(is_active=True)
        prefill_map: dict[str, dict[str, Any]] = {}
        valid_assay_ids: list[str] = []
        env_options = schema.get("fields", {}).get("environment", {}).get("options", [])
        for panel in assay_panels:
            if panel.get("asp_category") == schema_category:
                envs = self.repository.get_available_assay_envs(str(panel["_id"]), env_options)
                if envs:
                    valid_assay_ids.append(panel["_id"])
                    prefill_map[panel["_id"]] = {
                        "display_name": panel.get("display_name"),
                        "asp_group": panel.get("asp_group"),
                        "asp_category": panel.get("asp_category"),
                        "platform": panel.get("platform"),
                        "environment": envs,
                    }
        schema["fields"]["assay_name"]["options"] = valid_assay_ids
        if schema_category == "DNA" and "vep_consequences" in schema.get("fields", {}):
            schema["fields"]["vep_consequences"]["options"] = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
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
        }

    def context_payload(self, *, assay_id: str) -> dict[str, Any]:
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        schema = self.repository.get_schema(assay_config.get("schema_name"))
        if not schema:
            raise api_error(404, "Schema for this assay config is missing")
        schema = self.repository.clone_schema(schema)
        if "vep_consequences" in schema.get("fields", {}):
            schema["fields"]["vep_consequences"]["options"] = list(runtime_app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
        return {"assay_config": assay_config, "schema": schema}

    def create(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        config = payload.get("config", {})
        if not config:
            raise api_error(400, "Missing assay config payload")
        config.setdefault("is_active", True)
        config["aspc_id"] = config.get("aspc_id") or config.get("_id") or f"{str(config.get('assay_name', '')).strip()}:{str(config.get('environment', '')).strip().lower()}"
        config["_id"] = config["aspc_id"]
        existing_config = self.repository.get_assay_config(config.get("aspc_id"))
        if existing_config:
            raise api_error(409, "Assay config already exists")
        self.repository.create_assay_config(config)
        return mutation_payload(resource="aspc", resource_id=str(config.get("aspc_id", "unknown")), action="create")

    def update(self, *, assay_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        updated_config = payload.get("config", {})
        if not updated_config:
            raise api_error(400, "Missing assay config payload")
        updated_config["aspc_id"] = assay_config.get("aspc_id", assay_id)
        updated_config["_id"] = assay_config.get("_id", assay_id)
        self.repository.update_assay_config(assay_id, updated_config)
        return mutation_payload(resource="aspc", resource_id=assay_id, action="update")

    def toggle(self, *, assay_id: str) -> dict[str, Any]:
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        new_status = not bool(assay_config.get("is_active"))
        self.repository.set_assay_config_active(assay_id, new_status)
        payload = mutation_payload(resource="aspc", resource_id=assay_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, assay_id: str) -> dict[str, Any]:
        assay_config = self.repository.get_assay_config(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        self.repository.delete_assay_config(assay_id)
        return mutation_payload(resource="aspc", resource_id=assay_id, action="delete")


class AdminSampleService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()
        if not SampleDeletionService.has_repository():
            SampleDeletionService.set_repository(AdminSampleDeletionRepository())

    def list_payload(self, *, assays: list[str], search: str) -> dict[str, Any]:
        return {"samples": self.repository.list_samples_for_admin(assays=assays, search=search)}

    def context_payload(self, *, sample_id: str) -> dict[str, Any]:
        sample_doc = self.repository.get_sample(sample_id)
        if not sample_doc:
            raise api_error(404, "Sample not found")
        return {"sample": sample_doc}

    def update(self, *, sample_id: str, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
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
        sample_name = self.repository.get_sample_name(sample_id)
        if not sample_name:
            raise api_error(404, "Sample not found")
        deletion_summary = delete_all_sample_traces(sample_id)
        payload = mutation_payload(resource="sample", resource_id=sample_id, action="delete")
        payload["meta"]["sample_name"] = deletion_summary.get("sample_name") or sample_name
        payload["meta"]["results"] = deletion_summary.get("results", [])
        return payload


class AdminSchemaService:
    def __init__(self, repository: AdminRepository | None = None) -> None:
        self.repository = repository or AdminRepository()

    def list_payload(self) -> dict[str, Any]:
        return {"schemas": self.repository.list_schemas()}

    def context_payload(self, *, schema_id: str) -> dict[str, Any]:
        schema_doc = self.repository.get_schema(schema_id)
        if not schema_doc:
            raise api_error(404, "Schema not found")
        return {"schema": schema_doc}

    def create(self, *, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        schema_doc = payload.get("schema", {})
        schema_doc["_id"] = schema_doc.get("schema_name")
        schema_doc["schema_id"] = schema_doc.get("schema_name")
        schema_doc.setdefault("is_active", True)
        schema_doc["created_on"] = utc_now()
        schema_doc["created_by"] = current_actor(actor_username)
        schema_doc["updated_on"] = utc_now()
        schema_doc["updated_by"] = current_actor(actor_username)
        self.repository.create_schema(schema_doc)
        return mutation_payload(resource="schema", resource_id=schema_doc["_id"], action="create")

    def update(self, *, schema_id: str, payload: dict[str, Any], actor_username: str) -> dict[str, Any]:
        schema_doc = self.repository.get_schema(schema_id)
        if not schema_doc:
            raise api_error(404, "Schema not found")
        updated_schema = payload.get("schema", {})
        updated_schema["_id"] = schema_doc["_id"]
        updated_schema["schema_id"] = schema_doc.get("schema_id", schema_id)
        updated_schema["updated_on"] = utc_now()
        updated_schema["updated_by"] = current_actor(actor_username)
        updated_schema["version"] = schema_doc.get("version", 1) + 1
        self.repository.update_schema(schema_id, updated_schema)
        return mutation_payload(resource="schema", resource_id=schema_id, action="update")

    def toggle(self, *, schema_id: str) -> dict[str, Any]:
        schema_doc = self.repository.get_schema(schema_id)
        if not schema_doc:
            raise api_error(404, "Schema not found")
        new_status = not bool(schema_doc.get("is_active"))
        self.repository.set_schema_active(schema_id, new_status)
        payload = mutation_payload(resource="schema", resource_id=schema_id, action="toggle")
        payload["meta"]["is_active"] = new_status
        return payload

    def delete(self, *, schema_id: str) -> dict[str, Any]:
        schema_doc = self.repository.get_schema(schema_id)
        if not schema_doc:
            raise api_error(404, "Schema not found")
        self.repository.delete_schema(schema_id)
        return mutation_payload(resource="schema", resource_id=schema_id, action="delete")
