"""Focused regressions for ASPC create/edit contract flow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _clinical_rule_repository(
    *, rule_set_id: str = "hema_gmsv1__base__sv", analyte: str = "dna"
) -> SimpleNamespace:
    def get_active(requested_id: str):
        if requested_id != rule_set_id:
            return None
        return {
            "rule_set_id": rule_set_id,
            "content_version": 1,
            "revision": 1,
            "scope": {
                "asp_id": rule_set_id.split("__", 1)[0],
                "subpanel_id": "base",
                "analyte": analyte,
                "language": "sv",
            },
            "name": "Test rules",
            "status": "published",
            "active": True,
            "analysis_declarations": {"SNV": {"narrative": "enabled"}},
            "blocks": [],
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
            "updated_at": "2026-01-01T00:00:00Z",
            "updated_by": "test",
            "published_at": "2026-01-01T00:00:00Z",
            "published_by": "test",
        }

    def list_active_for_assay(asp_id: str):
        document = get_active(rule_set_id)
        return [document] if document and document["scope"]["asp_id"] == asp_id else []

    return SimpleNamespace(
        get_active=get_active,
        list_active_for_assay=list_active_for_assay,
    )


def test_aspc_form_lists_published_rules_for_selected_assay() -> None:
    """The managed ASPC form exposes assay-scoped rule releases as a selector."""
    from api.application.accounts.common import build_managed_form
    from api.application.resources.aspc import AspcService
    from api.contracts.managed_resources import aspc_spec_for_category

    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )
    form = build_managed_form(aspc_spec_for_category("DNA"))

    service._set_clinical_rule_options(form, ["hema_gmsv1"])

    reporting_fields = [
        field for group in form["fields"]["reporting"]["groups"] for field in group["fields"]
    ]
    selector = next(field for field in reporting_fields if field["key"] == "clinical_rule_set_id")
    options = selector["options_by_field"]["values"]["hema_gmsv1"]
    assert selector["type"] == "select"
    assert options[0]["value"] == "hema_gmsv1__base__sv"
    assert options[0]["subpanel_id"] == "base"
    assert selector["auto_select"]["field"] == "subpanel_id"


def test_business_identifiers_allow_clinical_subpanel_hyphens() -> None:
    """Clinical subpanel identifiers may contain hyphens, e.g. hem-snabb."""
    from api.config.constants import validate_identifier

    assert validate_identifier("hem-snabb", label="subpanel_id") == "hem-snabb"


def test_aspc_service_create_inherits_scope_fields_from_selected_asp(monkeypatch) -> None:
    """ASPC create should trust the selected ASP for scope and platform metadata."""
    import api.application.resources.aspc as aspc_module
    from api.application.resources.aspc import AspcService

    created: list[dict] = []
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, subpanel_id="base": (
                f"{asp_id}_{subpanel_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(
            get_asp=lambda assay: {
                "asp_id": assay,
                "asp_group": "hematology",
                "asp_category": "dna",
                "platform": "illumina",
            }
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda *a, **k: []),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )

    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda collection, payload: payload)

    service.create(
        payload={
            "config": {
                "asp_id": "hema_gmsv1",
                "subpanel_id": "base",
                "environment": "production",
                "display_name": "Demo ASPC",
                "analysis_types": ["SNV"],
                "reporting": {
                    "report_sections": ["SNV"],
                    "clinical_rule_set_id": "hema_gmsv1__base__sv",
                },
                "filters": {"somatic": {"snv": {"min_alt_reads": 5}}},
                "asp_group": "wrong",
                "asp_category": "rna",
                "platform": "nanopore",
            }
        },
        actor_username="actor",
    )

    assert created[0]["asp_group"] == "hematology"
    assert created[0]["asp_category"] == "dna"
    assert created[0]["platform"] == "illumina"
    assert created[0]["aspc_id"] == "hema_gmsv1_base_production"
    assert created[0]["filters"]["somatic"]["snv"]["min_alt_reads"] == 5
    assert created[0]["version"] == 1
    assert "version_history" not in created[0]


def test_aspc_service_requires_compatible_published_rule_binding() -> None:
    """ASPC validation resolves the explicitly bound published rule set."""
    from api.application.resources.aspc import AspcService

    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )
    service._validate_clinical_rule_binding(
        {
            "is_active": True,
            "asp_id": "hema_gmsv1",
            "asp_category": "dna",
            "subpanel_id": "base",
            "reporting": {
                "report_sections": ["SNV"],
                "clinical_rule_set_id": "hema_gmsv1__base__sv",
            },
        }
    )


def test_aspc_service_rejects_rule_binding_from_another_assay() -> None:
    """Direct API writes cannot bypass the assay-scoped rule selector."""
    from api.application.resources.aspc import AspcService
    from api.domain.common.errors import AppError

    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )

    with pytest.raises(AppError, match="rule-set assay does not match"):
        service._validate_clinical_rule_binding(
            {
                "is_active": True,
                "asp_id": "solid_gmsv3",
                "asp_category": "dna",
                "subpanel_id": "base",
                "reporting": {
                    "report_sections": ["SNV"],
                    "clinical_rule_set_id": "hema_gmsv1__base__sv",
                },
            }
        )


def test_aspc_service_allows_empty_gene_list_selection(monkeypatch) -> None:
    """An ASPC may use thresholds without selecting any ISGLs."""
    import api.application.resources.aspc as aspc_module
    from api.application.resources.aspc import AspcService

    created: list[dict] = []
    panel = {
        "asp_id": "hema_gmsv1",
        "asp_group": "hematology",
        "asp_category": "dna",
        "platform": "illumina",
    }
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, subpanel_id="base": (
                f"{asp_id}_{subpanel_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(get_asp=lambda _asp_id: panel),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )
    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda _collection, payload: payload)
    monkeypatch.setattr(service, "_validate_clinical_rule_binding", lambda _config: None)

    service.create(
        payload={
            "config": {
                "asp_id": "hema_gmsv1",
                "subpanel_id": "base",
                "environment": "production",
                "display_name": "Hematology configuration",
                "analysis_types": ["SNV"],
                "reporting": {"report_sections": []},
                "filters": {"somatic": {"snv": {"snvlists": []}}},
            }
        }
    )

    assert created[0]["filters"]["somatic"]["snv"]["snvlists"] == []


def test_aspc_service_materializes_translocation_filters_when_enabled(monkeypatch) -> None:
    """Enabling DNA translocations creates its required canonical filter profile."""
    import api.application.resources.aspc as aspc_module
    from api.application.resources.aspc import AspcService

    created: list[dict] = []
    panel = {
        "asp_id": "solid_gmsv3",
        "asp_group": "solid",
        "asp_category": "dna",
        "platform": "illumina",
    }
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, subpanel_id="base": (
                f"{asp_id}_{subpanel_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(get_asp=lambda _asp_id: panel),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
        clinical_rule_set_repository=_clinical_rule_repository(rule_set_id="solid_gmsv3__base__sv"),
        common_util=SimpleNamespace(),
    )
    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda _collection, payload: payload)
    monkeypatch.setattr(service, "_validate_clinical_rule_binding", lambda _config: None)

    service.create(
        payload={
            "config": {
                "asp_id": "solid_gmsv3",
                "subpanel_id": "base",
                "environment": "production",
                "display_name": "Solid configuration",
                "analysis_types": ["SNV", "TRANSLOCATION"],
                "reporting": {"report_sections": []},
                "filters": {"somatic": {"snv": {"min_alt_reads": 5}}},
            }
        }
    )

    assert created[0]["filters"]["somatic"]["translocation"] == {
        "fusionlists": [],
        "adhoc_genes": {},
    }


def test_aspc_create_context_keeps_configured_asps_selectable() -> None:
    """Existing ASPCs must not hide an ASP from a new subpanel configuration."""
    from api.application.resources.aspc import AspcService

    panel = {
        "asp_id": "hema_gmsv1",
        "display_name": "Hematology GMSv1",
        "asp_group": "hematology",
        "asp_category": "dna",
        "asp_family": "panel-dna",
        "platform": "illumina",
    }
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda is_active=True: [panel],
            get_asp=lambda _asp_id: panel,
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )

    payload = service.create_context_payload(category="DNA", actor_username="actor")
    form = payload["form"]

    assert form["fields"]["asp_id"]["options"] == ["hema_gmsv1"]
    assert form["fields"]["analysis_types"]["options_by_field"]["values"]["hema_gmsv1"]
    assert form["fields"]["subpanel_id"]["options_by_field"]["values"]["hema_gmsv1"] == ["base"]


def test_aspc_service_rejects_gene_lists_outside_asp_scope() -> None:
    """Imported ASPC JSON cannot attach an unrelated active ISGL."""
    from api.application.resources.aspc import AspcService
    from api.domain.common.errors import AppError

    panel = {"asp_id": "hema_gmsv1", "asp_group": "hematology"}
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(get_asp=lambda _asp_id: panel),
        gene_list_repository=SimpleNamespace(
            get_isgl_for_scope=lambda **_kwargs: [
                {"isgl_id": "hema_snv", "displayname": "Hematology SNV", "list_type": ["snv"]}
            ]
        ),
        vep_metadata_repository=SimpleNamespace(),
        clinical_rule_set_repository=_clinical_rule_repository(),
        common_util=SimpleNamespace(),
    )

    with pytest.raises(AppError, match="not active for ASP"):
        service._validate_filter_gene_lists(
            {"asp_id": "hema_gmsv1", "filters": {"somatic": {"snv": {"snvlists": ["other"]}}}},
            panel,
        )
