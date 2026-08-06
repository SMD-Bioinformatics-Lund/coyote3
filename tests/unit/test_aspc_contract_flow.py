"""Focused regressions for ASPC create/edit contract flow."""

from __future__ import annotations

from types import SimpleNamespace


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
                "reporting": {"report_sections": ["SNV"]},
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


def test_aspc_service_uses_static_yaml_scope_validation(monkeypatch) -> None:
    """ASPC validation resolves a matching static ASP/subpanel rule source."""
    from api.application.resources.aspc import AspcService

    service = AspcService(
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(),
        common_util=SimpleNamespace(),
    )

    monkeypatch.setattr(
        "api.application.resources.aspc.ClinicalRuleService.resolve",
        lambda _self, *, context: (
            SimpleNamespace(
                rule_set=SimpleNamespace(rule_set_id="hema_gmsv1__base"),
                analyses={"SNV": SimpleNamespace(enabled=True)},
            ),
            None,
        ),
    )
    service._validate_static_rule_source(
        {
            "is_active": True,
            "asp_id": "hema_gmsv1",
            "asp_category": "dna",
            "subpanel_id": "base",
            "reporting": {"report_sections": ["SNV"]},
        }
    )
