"""Admin assay-configuration and query-profile resource-management workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from coyote3.application.accounts.common import (
    admin_list_pagination,
    build_managed_form,
    change_payload,
    current_actor,
    utc_now,
)
from coyote3.application.common.protected_records import (
    reject_system_managed_change,
    reject_system_managed_delete,
)
from coyote3.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote3.application.resources.availability import available_panels, require_active_group
from coyote3.application.resources.configuration_profiles import (
    compile_profiles,
    prepare_profile_update,
)
from coyote3.application.resources.helpers import (
    _normalize_asp_category,
    _normalize_asp_category_doc,
    _validated_doc,
)
from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote3.config.constants import (
    DIAGNOSIS_BASE_ID,
    normalize_analysis_type,
    normalize_clinical_identifier,
)
from coyote3.config.loaders.filter_flags import filter_flag_options
from coyote3.contracts.authoring.resources import aspc_spec_for_category
from coyote3.domain.common.assay_capabilities import supported_assay_analyses
from coyote3.domain.common.configuration_transfer import CONFIGURATION_METADATA_FIELDS
from coyote3.domain.common.errors import api_error
from coyote3.domain.common.resource_names import short_resource_name
from coyote3.domain.common.sample_filters import normalize_sample_filters
from coyote3.domain.filtering.capabilities import (
    filter_section_for_analysis,
    select_filter_values,
)

_GENE_LIST_TYPE_BY_FILTER_KEY = {
    "snvlists": "snv",
    "cnvlists": "cnv",
    "fusionlists": "fusion",
}


class AspcService:
    """Assay-configuration resource workflows."""

    @classmethod
    def from_store(
        cls,
        store: Any,
    ) -> "AspcService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_diagnosis_repository=store.assay_diagnosis_repository,
            gene_list_repository=store.gene_list_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            configuration_profile_repository=store.configuration_profile_repository,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        gene_list_repository: Any,
        vep_metadata_repository: Any,
        assay_diagnosis_repository: Any,
        configuration_profile_repository: Any = None,
    ) -> None:
        """Create the service for assay-configuration resource workflows."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_diagnosis_repository = assay_diagnosis_repository
        self.gene_list_repository = gene_list_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.configuration_profile_repository = configuration_profile_repository

    @staticmethod
    def _set_group_field_options(
        schema: dict[str, Any], *, top_field: str, subfield_key: str, options: list[str]
    ) -> None:
        """Replace matching grouped form-field options in place.

        Args:
            schema: Mutable managed-form schema containing fields and groups.
            top_field: Top-level field whose groups are searched.
            subfield_key: Final dotted-key component identifying matching subfields.
            options: Values stringified and deduplicated in order; empty strings are dropped.
        """
        top = schema.get("fields", {}).get(top_field, {})
        for group in top.get("groups", []) or []:
            for subfield in group.get("fields", []) or []:
                if str(subfield.get("key") or "").rsplit(".", 1)[-1] == subfield_key:
                    subfield["options"] = list(dict.fromkeys([str(o) for o in options if str(o)]))

    def _decorate_form_options(
        self, *, form: dict[str, Any], form_category: str, asp_ids: list[str]
    ) -> None:
        """Populate gene-list, DNA consequence, and configured flag choices.

        Args:
            form: Mutable managed form receiving repository-backed options.
            form_category: Exact DNA enables consequence and flag choices.
            asp_ids: Assay IDs used to resolve gene-list choices.
        """
        if form_category == "DNA":
            conseq_options = list(self.vep_metadata_repository.get_consequence_group_options())
            self._set_group_field_options(
                form, top_field="filters", subfield_key="vep_consequences", options=conseq_options
            )
            flags = filter_flag_options("snv")
            self._set_group_field_options(
                form, top_field="filters", subfield_key="exclude_flags", options=flags
            )
        self._set_filter_gene_list_options(form, asp_ids)

    def _gene_list_options_for_asp(self, asp_id: str) -> dict[str, list[dict[str, str]]]:
        """Return active non-ad-hoc ISGL choices, grouped by analytical use."""
        panel = self.assay_panel_repository.get_asp(asp_id) or {}
        assay_group = str(panel.get("asp_group") or "").strip() or None
        options_by_type: dict[str, dict[str, dict[str, str]]] = {
            list_type: {} for list_type in _GENE_LIST_TYPE_BY_FILTER_KEY.values()
        }
        for gene_list in (
            self.gene_list_repository.get_isgl_for_scope(
                asp_name=asp_id,
                assay_group=assay_group,
                is_active=True,
                adhoc=False,
            )
            or []
        ):
            if not isinstance(gene_list, dict):
                continue
            isgl_id = str(gene_list.get("isgl_id") or "").strip()
            if not isgl_id:
                continue
            option = {
                "value": isgl_id,
                "label": str(gene_list.get("name") or gene_list.get("displayname") or isgl_id),
            }
            for list_type in gene_list.get("list_type") or []:
                normalized_type = str(list_type).strip().lower()
                if normalized_type in options_by_type:
                    options_by_type[normalized_type][isgl_id] = option
        return {
            list_type: sorted(options.values(), key=lambda item: item["label"].casefold())
            for list_type, options in options_by_type.items()
        }

    def _set_filter_gene_list_options(self, form: dict[str, Any], asp_ids: list[str]) -> None:
        """Attach ASP-dependent ISGL checkbox options to each filter list field."""
        choices = {
            asp_id.lower(): self._gene_list_options_for_asp(asp_id) for asp_id in asp_ids if asp_id
        }
        for filter_key, list_type in _GENE_LIST_TYPE_BY_FILTER_KEY.items():
            values = {asp_id: options.get(list_type, []) for asp_id, options in choices.items()}
            top = form.get("fields", {}).get("filters", {})
            for group in top.get("groups", []) or []:
                for field in group.get("fields", []) or []:
                    if str(field.get("key") or "").rsplit(".", 1)[-1] == filter_key:
                        field["options_by_field"] = {"field": "asp_id", "values": values}

    def _validate_filter_gene_lists(self, config: dict[str, Any], panel: dict[str, Any]) -> None:
        """Reject selected ISGLs that are not active choices for the selected ASP scope."""
        asp_id = str(panel.get("asp_id") or config.get("asp_id") or "").strip()
        allowed_by_type = {
            list_type: {
                str(option.get("value") or "")
                for option in options
                if str(option.get("value") or "")
            }
            for list_type, options in self._gene_list_options_for_asp(asp_id).items()
        }
        invalid_by_type: dict[str, set[str]] = {}
        filters = config.get("filters") or {}
        for intent in filters.values():
            if not isinstance(intent, dict):
                continue
            for section in intent.values():
                if not isinstance(section, dict):
                    continue
                for filter_key, list_type in _GENE_LIST_TYPE_BY_FILTER_KEY.items():
                    values = section.get(filter_key) or []
                    values = values if isinstance(values, list) else [values]
                    invalid = {
                        str(value).strip()
                        for value in values
                        if str(value).strip()
                        and str(value).strip() not in allowed_by_type[list_type]
                    }
                    if invalid:
                        invalid_by_type.setdefault(list_type, set()).update(invalid)
        if invalid_by_type:
            details = "; ".join(
                f"{list_type.upper()}: {', '.join(sorted(values))}"
                for list_type, values in sorted(invalid_by_type.items())
            )
            raise api_error(
                400,
                f"Selected gene lists are not active for ASP '{asp_id}' or its assay group: {details}",
            )

    def _capture_gene_lists(self, panel: dict[str, Any]) -> dict[str, Any]:
        """Capture selectable list revisions for a newly compiled configuration."""
        return capture_gene_lists(
            list(
                self.gene_list_repository.get_isgl_for_scope(
                    asp_name=panel["asp_id"],
                    assay_group=panel["asp_group"],
                    is_active=True,
                    adhoc=False,
                )
                or []
            )
        )

    def _diagnosis_options_for_asp(self, asp_id: str) -> list[str]:
        """Return registered active scopes, independent of gene-list diagnoses."""
        return [
            DIAGNOSIS_BASE_ID,
            *[
                row["diagnosis_id"]
                for row in self.assay_diagnosis_repository.list_for_assay(asp_id, active_only=True)
                if row["diagnosis_id"] != DIAGNOSIS_BASE_ID
            ],
        ]

    def _validate_diagnosis(self, config: dict, *, previous: dict | None = None) -> None:
        """Reject unregistered or retired scopes for new assignments.

        Existing configurations retain their original scope when edited, including
        retired definitions. They do not acquire new scope through a metadata edit.
        """
        try:
            for key in ("asp_id", "diagnosis_id"):
                config[key] = normalize_clinical_identifier(config[key], label=key)
        except ValueError as exc:
            raise api_error(422, "Invalid assay or diagnosis identifier") from exc
        identity = (config["asp_id"], config["diagnosis_id"])
        if previous is not None:
            if identity != (
                previous.get("asp_id"),
                previous.get("diagnosis_id", DIAGNOSIS_BASE_ID),
            ):
                raise api_error(409, "Create a new ASPC to change its assay or diagnosis")
            return
        if config["diagnosis_id"] not in self._diagnosis_options_for_asp(config["asp_id"]):
            raise api_error(400, "Select an active registered diagnosis for this assay")

    def _set_diagnosis_options(self, form: dict[str, Any], asp_ids: list[str]) -> None:
        """Attach ASP-dependent diagnosis choices to an ASPC managed form."""
        form["fields"]["diagnosis_id"]["options_by_field"] = {
            "field": "asp_id",
            "values": {
                asp_id.lower(): [{"value": DIAGNOSIS_BASE_ID, "label": "Base"}]
                + [
                    {"value": row["diagnosis_id"], "label": row["display_name"]}
                    for row in self.assay_diagnosis_repository.list_for_assay(
                        asp_id, active_only=True
                    )
                    if row["diagnosis_id"] != DIAGNOSIS_BASE_ID
                ]
                for asp_id in asp_ids
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
        layer = category.lower()
        selected = {normalize_analysis_type(value) for value in config.get("analysis_types") or []}
        canonical_profiles = normalize_sample_filters(
            raw,
            asp_category=layer,
            analysis_intents=intents,
            canonical=True,
        )
        somatic: dict[str, Any] = {}
        for analysis_type in selected:
            section = filter_section_for_analysis(asp_category=layer, analysis_type=analysis_type)
            if section:
                somatic[section] = select_filter_values(
                    canonical_profiles.get("somatic", {}).get(section),
                    asp_category=layer,
                    intent="somatic",
                    section=section,
                )
        profiles: dict[str, Any] = {"somatic": somatic}
        if "germline" in intents:
            profiles["germline"] = {
                "snv": select_filter_values(
                    canonical_profiles.get("germline", {}).get("snv"),
                    asp_category="dna",
                    intent="germline",
                    section="snv",
                )
            }
        config["filters"] = normalize_sample_filters(
            profiles,
            asp_category=category.lower(),
            analysis_intents=intents,
            canonical=True,
        )

    @staticmethod
    def _validate_analysis_types_for_panel(config: dict[str, Any], panel: dict[str, Any]) -> None:
        """Reject analyses and report sections without configured ASP input files."""
        family = str(panel.get("asp_family") or "").strip().lower()
        if family and family not in CLINICAL_VOCABULARY.analysis_types_by_family:
            raise api_error(400, f"Unsupported ASP family: {family}")
        allowed = AspcService._analysis_types_for_panel(
            panel, category=str(panel.get("asp_category") or "")
        )
        selected = {normalize_analysis_type(value) for value in config.get("analysis_types") or []}
        invalid = sorted(selected - set(allowed))
        if invalid:
            raise api_error(
                400,
                "Analysis type(s) not available for ASP input files and family: "
                + ", ".join(invalid),
            )
        reporting = config.get("reporting") or {}
        if not isinstance(reporting, dict):
            raise api_error(400, "reporting must be an object")
        report_sections = {
            normalize_analysis_type(value) for value in reporting.get("report_sections") or []
        }
        invalid_reports = sorted(report_sections - selected)
        if invalid_reports:
            raise api_error(
                400, "Report sections must be enabled analyses: " + ", ".join(invalid_reports)
            )

    @staticmethod
    def _analysis_types_for_panel(panel: dict[str, Any], *, category: str) -> list[str]:
        """Return the selectable analysis types for one ASP.

        Intersect category and sequencing-family capabilities with expected file
        keys. Required files control ingestion, not analysis selection.
        """
        family = str(panel.get("asp_family") or "").strip().lower()
        bindings = CLINICAL_VOCABULARY.analysis_file_keys_by_omics.get(category.lower(), {})
        allowed = CLINICAL_VOCABULARY.analysis_types_by_family.get(family, tuple(bindings))
        return supported_assay_analyses(
            family_analyses=allowed,
            file_bindings=bindings,
            expected_files=panel.get("expected_files") or [],
            declared_analyses=panel.get("supported_analyses"),
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
            for item in available_panels(self.assay_panel_repository)
            if isinstance(item, dict)
        ]
        prefill_map: dict[str, dict[str, Any]] = {}
        analysis_options_by_asp: dict[str, list[str]] = {}
        valid_assay_ids: list[str] = []
        for panel in assay_panels:
            panel_category = _normalize_asp_category(panel.get("asp_category"))
            if panel_category == form_category:
                assay_id = str(panel.get("asp_id") or panel.get("_id") or "")
                if not assay_id:
                    continue
                # A configuration identity includes ASP, diagnosis, and environment.
                # Do not hide an ASP merely because one of its configurations already
                # exists: it can still validly receive another diagnosis or environment.
                # The create workflow enforces the exact identity at save time.
                valid_assay_ids.append(assay_id)
                prefill_map[assay_id] = {
                    "display_name": panel.get("display_name"),
                    "asp_group": panel.get("asp_group"),
                    "asp_category": panel_category,
                    "platform": panel.get("platform"),
                    "diagnosis_id": DIAGNOSIS_BASE_ID,
                }
                analysis_options_by_asp[assay_id.lower()] = self._analysis_types_for_panel(
                    panel,
                    category=form_category,
                )
        form["fields"]["asp_id"]["options"] = [
            {
                "value": str(panel["asp_id"]),
                "label": short_resource_name(panel, str(panel["asp_id"])),
            }
            for panel in assay_panels
            if panel.get("asp_id") in valid_assay_ids
        ]
        form["fields"]["analysis_types"]["options_by_field"] = {
            "field": "asp_id",
            "values": analysis_options_by_asp,
        }
        self._set_diagnosis_options(form, valid_assay_ids)
        self._decorate_form_options(
            form=form,
            form_category=form_category,
            asp_ids=valid_assay_ids,
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
        form["fields"]["asp_id"]["options"] = [
            {
                "value": str(assay_config["asp_id"]),
                "label": short_resource_name(panel or {}, str(assay_config["asp_id"])),
            }
        ]
        for field in ("asp_id", "diagnosis_id", "environment"):
            form["fields"][field]["readonly_mode"] = ["edit"]
        form["fields"]["analysis_types"]["options_by_field"] = {
            "field": "asp_id",
            "values": {
                str(assay_config.get("asp_id") or "").lower(): self._analysis_types_for_panel(
                    panel or {},
                    category=category,
                )
            },
        }
        self._set_diagnosis_options(form, [str(assay_config.get("asp_id") or "")])
        choices = form["fields"]["diagnosis_id"]["options_by_field"]["values"]
        existing_scope = str(assay_config.get("diagnosis_id") or DIAGNOSIS_BASE_ID)
        assay_choices = choices[str(assay_config.get("asp_id") or "").lower()]
        if existing_scope not in {option["value"] for option in assay_choices}:
            assay_choices.append({"value": existing_scope, "label": existing_scope})
        self._decorate_form_options(
            form=form,
            form_category=category,
            asp_ids=[str(assay_config.get("asp_id", "") or "")],
        )
        return {
            "assay_config": assay_config,
            "form": form,
        }

    @staticmethod
    def _remove_rule_snapshots(config: dict[str, Any]) -> None:
        """Exclude historical rule captures from newly written assay configuration revisions."""
        for key in ("query_policy_release", "clinical_rule_release", "clinical_rule_base"):
            config.pop(key, None)

    def create(
        self, *, payload: dict[str, Any], actor_username: str = "admin-ui"
    ) -> dict[str, Any]:
        """Create a new assay configuration from submitted config data.

        Args:
            payload: Submitted config payload.
            actor_username: Authenticated caller used when no current actor is bound.

        Returns:
            Change response identifying the new assay configuration.

        Notes:
            Creation provenance and system ownership are assigned by the server.
            Imported metadata is discarded and the submitted config is stamped in place.
        """
        config = payload.get("config", {})
        if isinstance(config, dict):
            for field in CONFIGURATION_METADATA_FIELDS:
                config.pop(field, None)
        if not config:
            raise api_error(400, "Missing assay config payload")
        asp_id = str(config.get("asp_id", "")).strip()
        panel = self.assay_panel_repository.get_asp(asp_id)
        if not panel:
            raise api_error(400, "Selected ASP does not exist")
        require_active_group(self.assay_panel_repository, panel["asp_group"])
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        config.setdefault("is_active", True)
        config["system_managed"] = False
        config["system_installed"] = False
        config["asp_id"] = asp_id
        config["diagnosis_id"] = str(config.get("diagnosis_id") or DIAGNOSIS_BASE_ID).strip()
        self._validate_diagnosis(config)
        config["asp_group"] = panel.get("asp_group")
        config["asp_category"] = _normalize_asp_category_doc(panel.get("asp_category"))
        config["platform"] = panel.get("platform")
        self._validate_analysis_types_for_panel(config, panel)
        if isinstance(config.get("reporting"), dict):
            config["reporting"].pop("analysis", None)
        compile_profiles(config, panel, self.configuration_profile_repository)
        self._build_filter_profiles(config, category=category)
        self._validate_filter_gene_lists(config, panel)
        config["aspc_id"] = self.assay_configuration_repository.build_aspc_id(
            config["asp_id"],
            str(config.get("environment", "")),
            config["diagnosis_id"],
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
        config["created_by"] = actor
        config["created_on"] = now
        config["updated_by"] = actor
        config["updated_on"] = now
        config["version"] = 1
        self._remove_rule_snapshots(config)
        config["assay_resource_release"] = capture_assay_resource(panel)
        config["gene_list_release"] = self._capture_gene_lists(panel)
        config = _validated_doc(spec.collection, config)
        self._remove_rule_snapshots(config)
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
        for field in ("asp_id", "diagnosis_id", "environment"):
            if field in updated_config and updated_config[field] != assay_config.get(field):
                raise api_error(
                    400, f"Configuration {field} cannot be changed; create a new configuration"
                )
        updated_doc = {**assay_config, **updated_config}
        updated_doc["aspc_id"] = assay_config.get("aspc_id", assay_id)
        reject_system_managed_change(assay_config, resource="assay configuration")
        updated_doc["system_managed"] = bool(assay_config.get("system_managed"))
        updated_doc["system_installed"] = bool(assay_config.get("system_installed"))
        updated_doc.pop("_id", None)
        updated_doc["diagnosis_id"] = str(
            updated_doc.get("diagnosis_id") or DIAGNOSIS_BASE_ID
        ).strip()
        self._validate_diagnosis(updated_doc, previous=assay_config)
        actor = current_actor(actor_username)
        now = utc_now()
        previous_version = int(assay_config.get("version") or 1)
        updated_doc["created_by"] = assay_config.get("created_by")
        updated_doc["created_on"] = assay_config.get("created_on")
        updated_doc["updated_by"] = actor
        updated_doc["updated_on"] = now
        updated_doc["is_active"] = True
        updated_doc["version"] = previous_version + 1
        updated_doc["supersedes_id"] = assay_config.get("_id")
        panel = self.assay_panel_repository.get_asp(str(updated_doc.get("asp_id", "")))
        if not panel:
            raise api_error(400, "Selected ASP does not exist")
        require_active_group(self.assay_panel_repository, panel["asp_group"])
        category = _normalize_asp_category((panel or {}).get("asp_category"))
        updated_doc["asp_group"] = panel.get("asp_group")
        updated_doc["asp_category"] = _normalize_asp_category_doc(panel.get("asp_category"))
        updated_doc["platform"] = panel.get("platform")
        self._validate_analysis_types_for_panel(updated_doc, panel)
        if isinstance(updated_doc.get("reporting"), dict):
            updated_doc["reporting"].pop("analysis", None)
        prepare_profile_update(assay_config, updated_config, updated_doc)
        compile_profiles(updated_doc, panel, self.configuration_profile_repository)
        self._build_filter_profiles(updated_doc, category=category)
        self._validate_filter_gene_lists(updated_doc, panel)
        spec = aspc_spec_for_category(category)
        updated_doc.pop("retired_by", None)
        updated_doc.pop("retired_on", None)
        updated_doc.pop("retired_reason", None)
        self._remove_rule_snapshots(updated_doc)
        updated_doc["assay_resource_release"] = capture_assay_resource(panel)
        updated_doc["gene_list_release"] = self._capture_gene_lists(panel)
        updated_doc = _validated_doc(spec.collection, updated_doc)
        self._remove_rule_snapshots(updated_doc)
        operation = self.assay_configuration_repository.rotate_aspc(
            assay_id,
            updated_doc,
            expected_version=previous_version,
            retire_fields={
                "retired_by": actor,
                "retired_on": now,
                "retired_reason": "superseded_by_edit",
            },
        )
        result = change_payload(
            resource="aspc", resource_id=assay_id, action="update", operation=operation
        )
        result["meta"]["revision"] = {
            "previous_version": previous_version,
            "new_version": previous_version + 1,
            "previous_document_id": str(assay_config.get("_id") or ""),
            "new_document_id": operation.inserted_id,
        }
        return result

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
        reject_system_managed_change(assay_config, resource="assay configuration")
        new_status = not bool(assay_config.get("is_active"))
        if new_status:
            require_active_group(self.assay_panel_repository, assay_config["asp_group"])
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
        reject_system_managed_delete(assay_config, resource="assay configuration")
        self.assay_configuration_repository.delete_assay_config(assay_id)
        return change_payload(resource="aspc", resource_id=assay_id, action="delete")

    def assay_config_exists(
        self,
        *,
        aspc_id: str | None = None,
        asp_id: str | None = None,
        diagnosis_id: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Return whether an assay config business key already exists."""
        resolved_id = str(aspc_id or "").strip()
        if not resolved_id:
            assay = str(asp_id or "").strip()
            env = str(environment or "").strip()
            if assay and env:
                doc = self.assay_configuration_repository.get_aspc(
                    assay, env, str(diagnosis_id or DIAGNOSIS_BASE_ID)
                )
                return bool(isinstance(doc, dict) and (doc.get("aspc_id") or doc.get("_id")))
        if not resolved_id:
            return False
        doc = self.assay_configuration_repository.get_aspc_with_id(resolved_id)
        return bool(isinstance(doc, dict) and (doc.get("aspc_id") or doc.get("_id")))
