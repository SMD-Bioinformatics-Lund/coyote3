"""Admin assay-configuration and query-profile resource-management workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    utc_now,
)
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.application.resources.helpers import (
    _normalize_asp_category,
    _normalize_asp_category_doc,
    _validated_doc,
)
from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.config.constants import SUBPANEL_BASE_ID, normalize_analysis_type
from api.contracts.managed_resources import aspc_spec_for_category
from api.domain.common.errors import api_error
from api.domain.common.sample_filters import normalize_sample_filters
from api.domain.core.filter_capabilities import filter_section_for_analysis, select_filter_values


class AspcService:
    """Assay-configuration resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        common_util: Any,
    ) -> "AspcService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            gene_list_repository=store.gene_list_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            common_util=common_util,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        gene_list_repository: Any,
        vep_metadata_repository: Any,
        common_util: Any,
    ) -> None:
        """Create the service for assay-configuration resource workflows."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.gene_list_repository = gene_list_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.common_util = common_util

    @staticmethod
    def _set_group_field_options(
        schema: dict[str, Any], *, top_field: str, subfield_key: str, options: list[str]
    ) -> None:
        top = schema.get("fields", {}).get(top_field, {})
        for group in top.get("groups", []) or []:
            for subfield in group.get("fields", []) or []:
                if str(subfield.get("key") or "").rsplit(".", 1)[-1] == subfield_key:
                    subfield["options"] = list(dict.fromkeys([str(o) for o in options if str(o)]))

    def _decorate_form_options(
        self, *, form: dict[str, Any], form_category: str, assay_name: str | None
    ) -> None:
        _ = assay_name
        if form_category == "DNA":
            conseq_options = list(self.vep_metadata_repository.get_consequence_group_options())
            self._set_group_field_options(
                form, top_field="filters", subfield_key="vep_consequences", options=conseq_options
            )

    def _subpanel_options_for_asp(self, asp_id: str) -> list[str]:
        """Return the ASPC subpanel identities declared by linked ISGL diagnoses."""
        panel = self.assay_panel_repository.get_asp(asp_id) or {}
        assay_group = str(panel.get("asp_group") or "").strip() or None
        diagnoses = {
            str(diagnosis).strip()
            for genelist in (
                self.gene_list_repository.get_isgl_for_scope(
                    asp_name=asp_id,
                    assay_group=assay_group,
                    is_active=True,
                )
                or []
            )
            if isinstance(genelist, dict)
            for diagnosis in (genelist.get("diagnosis") or [])
            if str(diagnosis).strip()
        }
        return [SUBPANEL_BASE_ID, *sorted(diagnoses, key=str.casefold)]

    def _set_subpanel_options(self, form: dict[str, Any], asp_ids: list[str]) -> None:
        """Attach ASP-dependent subpanel choices to an ASPC managed form."""
        form["fields"]["subpanel_id"]["options_by_field"] = {
            "field": "asp_id",
            "values": {
                asp_id.lower(): self._subpanel_options_for_asp(asp_id) for asp_id in asp_ids
            },
        }

    @staticmethod
    def _build_filter_profiles(config: dict[str, Any], *, category: str) -> None:
        """Build the only accepted persisted filter shape from the ASPC form.

        The managed form chooses analysis types first. Its fields are then
        placed in the corresponding frozen intent/analysis group; no submitted
        field is allowed to select its own storage path.
        """
        intents = config.get("analysis_intents") or ["somatic"]
        raw = config.get("filters") or {}
        if any(key in raw for key in ("somatic", "germline")):
            config["filters"] = normalize_sample_filters(
                raw,
                omics_layer=category.lower(),
                analysis_intents=intents,
                canonical=True,
            )
            return
        layer = category.lower()
        selected = {normalize_analysis_type(value) for value in config.get("analysis_types") or []}
        somatic: dict[str, Any] = {}
        for analysis_type in selected:
            section = filter_section_for_analysis(omics_layer=layer, analysis_type=analysis_type)
            if section:
                somatic[section] = select_filter_values(
                    raw, omics_layer=layer, intent="somatic", section=section
                )
        profiles: dict[str, Any] = {"somatic": somatic}
        if "germline" in intents:
            profiles["germline"] = {
                "snv": select_filter_values(
                    raw, omics_layer="dna", intent="germline", section="snv"
                )
            }
        config["filters"] = normalize_sample_filters(
            profiles,
            omics_layer=category.lower(),
            analysis_intents=intents,
            canonical=True,
        )

    @staticmethod
    def _validate_analysis_types_for_panel(config: dict[str, Any], panel: dict[str, Any]) -> None:
        """Require ASPC analysis selections to be valid for the ASP sequencing family."""
        family = str(panel.get("asp_family") or "").strip().lower()
        if not family:
            return
        allowed = CLINICAL_VOCABULARY.analysis_types_by_family.get(family)
        if allowed is None:
            raise api_error(400, f"Unsupported ASP family: {family}")
        selected = {normalize_analysis_type(value) for value in config.get("analysis_types") or []}
        invalid = sorted(selected - set(allowed))
        if invalid:
            raise api_error(
                400,
                f"Analysis type(s) not available for ASP family '{family}': " + ", ".join(invalid),
            )

    @staticmethod
    def _analysis_types_for_panel(panel: dict[str, Any], *, category: str) -> list[str]:
        """Return the selectable analysis types for one ASP.

        ASP category establishes the DNA/RNA boundary. The sequencing family
        then narrows that category, for example separating panel RNA from WTS.
        Older ASP records without a family retain the category-level options.
        """
        family = str(panel.get("asp_family") or "").strip().lower()
        if family:
            allowed = CLINICAL_VOCABULARY.analysis_types_by_family.get(family)
            if allowed is not None:
                return list(allowed)
        return list(
            CLINICAL_VOCABULARY.analysis_file_keys_by_omics.get(category.lower(), {}).keys()
        )

    def list_payload(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the admin list payload for assay configurations.

        Returns:
            dict[str, Any]: Assay-config rows and pagination metadata.
        """
        rows, total = self.assay_configuration_repository.search_aspcs(
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
            for item in (self.assay_panel_repository.get_all_asps(is_active=True) or [])
            if isinstance(item, dict)
        ]
        prefill_map: dict[str, dict[str, Any]] = {}
        analysis_options_by_asp: dict[str, list[str]] = {}
        valid_assay_ids: list[str] = []
        env_options = form.get("fields", {}).get("environment", {}).get("options", [])
        for panel in assay_panels:
            panel_category = _normalize_asp_category(panel.get("asp_category"))
            if panel_category == form_category:
                assay_id = str(panel.get("asp_id") or panel.get("_id") or "")
                if not assay_id:
                    continue
                envs = list(
                    self.assay_configuration_repository.get_available_assay_envs(
                        assay_id, env_options
                    )
                    or []
                )
                if envs:
                    valid_assay_ids.append(assay_id)
                    prefill_map[assay_id] = {
                        "display_name": panel.get("display_name"),
                        "asp_group": panel.get("asp_group"),
                        "asp_category": panel_category,
                        "platform": panel.get("platform"),
                        "subpanel_id": SUBPANEL_BASE_ID,
                        "environment": envs,
                    }
                    analysis_options_by_asp[assay_id.lower()] = self._analysis_types_for_panel(
                        panel,
                        category=form_category,
                    )
        form["fields"]["asp_id"]["options"] = valid_assay_ids
        form["fields"]["analysis_types"]["options_by_field"] = {
            "field": "asp_id",
            "values": analysis_options_by_asp,
        }
        self._set_subpanel_options(form, valid_assay_ids)
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
        assay_config = self.assay_configuration_repository.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        assay_config = deepcopy(assay_config)
        panel = self.assay_panel_repository.get_asp(str(assay_config.get("asp_id", "")))
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        spec = aspc_spec_for_category(category)
        form = build_managed_form(spec)
        form["fields"]["analysis_types"]["options_by_field"] = {
            "field": "asp_id",
            "values": {
                str(assay_config.get("asp_id") or "").lower(): self._analysis_types_for_panel(
                    panel or {},
                    category=category,
                )
            },
        }
        self._set_subpanel_options(form, [str(assay_config.get("asp_id") or "")])
        self._decorate_form_options(
            form=form,
            form_category=category,
            assay_name=str(assay_config.get("asp_id", "") or ""),
        )
        return {
            "assay_config": assay_config,
            "form": form,
        }

    @staticmethod
    def _validate_static_rule_source(config: dict[str, Any]) -> None:
        """Require each active reporting ASPC to resolve to a repository YAML file."""
        reporting = config.get("reporting") or {}
        report_sections = {
            normalize_analysis_type(value)
            for value in reporting.get("report_sections", [])
            if str(value or "").strip()
        }
        if not config.get("is_active") or not report_sections:
            return
        context = type(
            "RuleScope",
            (),
            {
                "asp": type("Asp", (), {"asp_id": config.get("asp_id")})(),
                "sample": type(
                    "Sample",
                    (),
                    {
                        "asp_id": config.get("asp_id"),
                        "omics_layer": str(config.get("asp_category") or "").lower(),
                    },
                )(),
                "aspc": type("Aspc", (), {"subpanel_id": config.get("subpanel_id")})(),
            },
        )()
        try:
            source, _source_path = ClinicalRuleService().resolve(context=context)
        except ValueError as exc:
            raise api_error(409, str(exc)) from exc
        undeclared = sorted(report_sections - set(source.analyses))
        if undeclared:
            raise api_error(
                409,
                "Clinical rule source does not declare every selected report section: "
                + ", ".join(undeclared),
            )

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
        asp_id = str(config.get("asp_id", "")).strip()
        panel = self.assay_panel_repository.get_asp(asp_id)
        if not panel:
            raise api_error(400, "Selected ASP does not exist")
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        config.setdefault("is_active", True)
        config["asp_id"] = asp_id
        config["subpanel_id"] = str(config.get("subpanel_id") or SUBPANEL_BASE_ID).strip()
        config["asp_group"] = panel.get("asp_group")
        config["asp_category"] = _normalize_asp_category_doc(panel.get("asp_category"))
        config["platform"] = panel.get("platform")
        self._validate_analysis_types_for_panel(config, panel)
        if isinstance(config.get("reporting"), dict):
            config["reporting"].pop("analysis", None)
        self._build_filter_profiles(config, category=category)
        config["aspc_id"] = config.get(
            "aspc_id"
        ) or self.assay_configuration_repository.build_aspc_id(
            config["asp_id"],
            str(config.get("environment", "")),
            config["subpanel_id"],
        )
        if not config.get("aspc_id"):
            raise api_error(400, "Missing aspc_id")
        existing_config = self.assay_configuration_repository.get_aspc_with_id(
            config.get("aspc_id")
        )
        if existing_config:
            raise api_error(409, "Assay config already exists")
        spec = aspc_spec_for_category(category)
        actor = current_actor(actor_username)
        now = utc_now()
        config.setdefault("created_by", actor)
        config.setdefault("created_on", now)
        config["updated_by"] = actor
        config["updated_on"] = now
        config["version"] = 1
        self._validate_static_rule_source(config)
        config = _validated_doc(spec.collection, config)
        self.assay_configuration_repository.create_assay_config(config)
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
        assay_config = self.assay_configuration_repository.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        updated_config = payload.get("config", {})
        if not updated_config:
            raise api_error(400, "Missing assay config payload")
        updated_doc = {**assay_config, **updated_config}
        updated_doc["aspc_id"] = assay_config.get("aspc_id", assay_id)
        updated_doc.pop("_id", None)
        updated_doc["subpanel_id"] = str(updated_doc.get("subpanel_id") or SUBPANEL_BASE_ID).strip()
        actor = current_actor(actor_username)
        now = utc_now()
        updated_doc["created_by"] = assay_config.get("created_by") or actor
        updated_doc["created_on"] = assay_config.get("created_on") or now
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = now
        updated_doc["is_active"] = True
        updated_doc["version"] = 1
        panel = self.assay_panel_repository.get_asp(str(updated_doc.get("asp_id", "")))
        if not panel:
            raise api_error(400, "Selected ASP does not exist")
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        updated_doc["asp_group"] = panel.get("asp_group")
        updated_doc["asp_category"] = _normalize_asp_category_doc(panel.get("asp_category"))
        updated_doc["platform"] = panel.get("platform")
        self._validate_analysis_types_for_panel(updated_doc, panel)
        if isinstance(updated_doc.get("reporting"), dict):
            updated_doc["reporting"].pop("analysis", None)
        self._build_filter_profiles(updated_doc, category=category)
        spec = aspc_spec_for_category(category)
        updated_doc.pop("retired_by", None)
        updated_doc.pop("retired_on", None)
        updated_doc.pop("retired_reason", None)
        self._validate_static_rule_source(updated_doc)
        updated_doc = _validated_doc(spec.collection, updated_doc)
        self.assay_configuration_repository.update_aspc(assay_id, updated_doc)
        return change_payload(resource="aspc", resource_id=assay_id, action="update")

    def toggle(self, *, assay_id: str) -> dict[str, Any]:
        """Toggle whether an assay configuration is active.

        Args:
            assay_id: Assay-config identifier to toggle.

        Returns:
            dict[str, Any]: Normalized change response payload.
        """
        assay_config = self.assay_configuration_repository.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        new_status = not bool(assay_config.get("is_active"))
        self.assay_configuration_repository.toggle_aspc_active(assay_id, new_status)
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
        assay_config = self.assay_configuration_repository.get_aspc_with_id(assay_id)
        if not assay_config:
            raise api_error(404, "Assay config not found")
        self.assay_configuration_repository.delete_assay_config(assay_id)
        return change_payload(resource="aspc", resource_id=assay_id, action="delete")

    def assay_config_exists(
        self,
        *,
        aspc_id: str | None = None,
        asp_id: str | None = None,
        subpanel_id: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Return whether an assay config business key already exists."""
        resolved_id = str(aspc_id or "").strip()
        if not resolved_id:
            assay = str(asp_id or "").strip()
            env = str(environment or "").strip()
            if assay and env:
                resolved_id = self.assay_configuration_repository.build_aspc_id(
                    assay,
                    env,
                    str(subpanel_id or SUBPANEL_BASE_ID),
                )
        if not resolved_id:
            return False
        doc = self.assay_configuration_repository.get_aspc_with_id(resolved_id)
        return bool(isinstance(doc, dict) and (doc.get("aspc_id") or doc.get("_id")))
