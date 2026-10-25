"""Focused regressions for ASPC create/edit contract flow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_rna_configuration_exposes_configured_caller_annotations():
    """RNA filter choices match sidebar metadata and do not expose DNA exclusion flags."""
    from coyote3.application.accounts.common import build_managed_form
    from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
    from coyote3.contracts.authoring.resources import aspc_spec_for_category

    form = build_managed_form(aspc_spec_for_category("RNA"))
    fields = {
        field["key"]: field
        for group in form["fields"]["filters"]["groups"]
        for field in group["fields"]
    }
    annotations = fields["somatic.fusion.fusion_descriptions"]
    assert annotations["type"] == "checkbox-group"
    assert set(annotations["options"]) == {
        term
        for terms in CLINICAL_VOCABULARY.fusion_annotation_metadata().values()
        for term in terms
    }
    assert not any(key.endswith("exclude_flags") for key in fields)


def test_aspc_language_entry_is_independent_of_rule_publications() -> None:
    """ASPC authors can set a language before any rules exist for that assay."""
    from coyote3.application.accounts.common import build_managed_form
    from coyote3.contracts.authoring.resources import aspc_spec_for_category

    form = build_managed_form(aspc_spec_for_category("DNA"))
    fields = [field for group in form["fields"]["reporting"]["groups"] for field in group["fields"]]
    language = next(field for field in fields if field["key"] == "language")
    assert language["type"] == "text"
    assert language["default"] == "sv"
    assert "options_by_field" not in language


def test_business_identifiers_allow_clinical_diagnosis_hyphens() -> None:
    """Clinical diagnosis identifiers may contain hyphens, e.g. hem-snabb."""
    from coyote3.config.constants import validate_identifier

    assert validate_identifier("hem-snabb", label="diagnosis_id") == "hem-snabb"


def test_aspc_service_create_inherits_scope_fields_from_selected_asp(monkeypatch) -> None:
    """ASPC create should trust the selected ASP for scope and platform metadata."""
    import coyote3.application.resources.aspc as aspc_module
    from coyote3.application.resources.aspc import AspcService

    created: list[dict] = []
    service = AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, diagnosis_id="base": (
                f"{asp_id}_{diagnosis_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: ["hematology"],
            get_asp=lambda assay: {
                "asp_id": assay,
                "expected_files": ["vcf_files"],
                "asp_group": "hematology",
                "asp_category": "dna",
                "asp_family": "panel-dna",
                "platform": "illumina",
            },
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda *a, **k: []),
    )

    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda collection, payload: payload)

    service.create(
        payload={
            "config": {
                "asp_id": "hema_gmsv1",
                "diagnosis_id": "base",
                "environment": "production",
                "display_name": "Demo ASPC",
                "created_by": "forged-author",
                "created_on": "forged-time",
                "aspc_id": "copied_source_id",
                "analysis_types": ["SNV"],
                "reporting": {
                    "report_sections": ["SNV"],
                    "language": "sv",
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
    assert created[0]["created_by"] == "actor"
    assert created[0]["created_on"] == "now"
    assert created[0]["filters"]["somatic"]["snv"]["min_alt_reads"] == 5
    assert created[0]["version"] == 1
    assert "version_history" not in created[0]
    assert "query_policy_release" not in created[0]
    assert "clinical_rule_release" not in created[0]


def test_aspc_service_allows_empty_gene_list_selection(monkeypatch) -> None:
    """An ASPC may use thresholds without selecting any ISGLs."""
    import coyote3.application.resources.aspc as aspc_module
    from coyote3.application.resources.aspc import AspcService

    created: list[dict] = []
    panel = {
        "asp_id": "hema_gmsv1",
        "expected_files": ["vcf_files"],
        "asp_group": "hematology",
        "asp_category": "dna",
        "asp_family": "panel-dna",
        "platform": "illumina",
    }
    service = AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, diagnosis_id="base": (
                f"{asp_id}_{diagnosis_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(
            get_asp=lambda _asp_id: panel, group_options=lambda: [panel["asp_group"]]
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
    )
    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda _collection, payload: payload)

    service.create(
        payload={
            "config": {
                "asp_id": "hema_gmsv1",
                "diagnosis_id": "base",
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
    import coyote3.application.resources.aspc as aspc_module
    from coyote3.application.resources.aspc import AspcService

    created: list[dict] = []
    panel = {
        "asp_id": "demo-solid_gmsv3",
        "expected_files": ["vcf_files", "transloc"],
        "asp_group": "solid",
        "asp_category": "dna",
        "asp_family": "panel-dna",
        "platform": "illumina",
    }
    service = AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
            build_aspc_id=lambda asp_id, environment, diagnosis_id="base": (
                f"{asp_id}_{diagnosis_id}_{environment}"
            ),
        ),
        assay_panel_repository=SimpleNamespace(
            get_asp=lambda _asp_id: panel, group_options=lambda: [panel["asp_group"]]
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
    )
    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda _collection, payload: payload)

    service.create(
        payload={
            "config": {
                "asp_id": "demo-solid_gmsv3",
                "diagnosis_id": "base",
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
    """Existing ASPCs must not hide an ASP from a new diagnosis configuration."""
    from coyote3.application.resources.aspc import AspcService

    panel = {
        "asp_id": "hema_gmsv1",
        "display_name": "Hematology GMSv1",
        "asp_group": "hematology",
        "asp_category": "dna",
        "asp_family": "panel-dna",
        "expected_files": ["vcf_files"],
        "platform": "illumina",
    }
    service = AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda is_active=True: [panel],
            group_options=lambda: ["hematology"],
            get_asp=lambda _asp_id: panel,
        ),
        gene_list_repository=SimpleNamespace(get_isgl_for_scope=lambda **_kwargs: []),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
    )

    payload = service.create_context_payload(category="DNA", actor_username="actor")
    form = payload["form"]

    assert form["fields"]["asp_id"]["options"] == ["hema_gmsv1"]
    assert form["fields"]["analysis_types"]["options_by_field"]["values"]["hema_gmsv1"]
    assert form["fields"]["diagnosis_id"]["options_by_field"]["values"]["hema_gmsv1"] == [
        {"value": "base", "label": "Base"},
        {"value": "aml", "label": "AML"},
    ]
    service.assay_configuration_repository.get_aspc_with_id = lambda _identity: {
        "asp_id": "hema_gmsv1",
        "diagnosis_id": "aml",
        "environment": "testing",
    }
    edit_form = service.context_payload(assay_id="configuration")["form"]
    assert edit_form["fields"]["asp_id"]["options"] == [
        {"value": "hema_gmsv1", "label": "Hematology GMSv1"}
    ]
    for field in ("asp_id", "diagnosis_id", "environment"):
        assert edit_form["fields"][field]["readonly_mode"] == ["edit"]


@pytest.mark.parametrize("field", ["asp_id", "diagnosis_id", "environment"])
def test_aspc_update_rejects_scope_changes(field):
    """Direct API edits cannot move an existing configuration to another scope."""
    from coyote3.application.resources.aspc import AspcService
    from coyote3.domain.exceptions import AppError

    service = AspcService.__new__(AspcService)
    service.assay_configuration_repository = SimpleNamespace(
        get_aspc_with_id=lambda _identity: {
            "asp_id": "demo-hema",
            "diagnosis_id": "mpn",
            "environment": "testing",
        }
    )
    with pytest.raises(AppError, match="cannot be changed"):
        service.update(assay_id="configuration", payload={"config": {field: "other"}})


def test_gene_list_germline_fact_uses_pinned_assay_scope():
    """Report facts derive germline membership from the assay and selected list."""
    from coyote3.application.reporting.clinical_rules.preparation import _gene_list_fact

    fact = _gene_list_fact({"genes": ["TP53", "NPM1"]}, {"germline_genes": ["TP53", "BRCA1"]})
    assert fact["germline_genes"] == ["TP53"]


def test_aspc_service_rejects_gene_lists_outside_asp_scope() -> None:
    """Imported ASPC JSON cannot attach an unrelated active ISGL."""
    from coyote3.application.resources.aspc import AspcService
    from coyote3.domain.common.errors import AppError

    panel = {"asp_id": "hema_gmsv1", "asp_group": "hematology"}
    service = AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(get_asp=lambda _asp_id: panel),
        gene_list_repository=SimpleNamespace(
            get_isgl_for_scope=lambda **_kwargs: [
                {"isgl_id": "hema_snv", "displayname": "Hematology SNV", "list_type": ["snv"]}
            ]
        ),
        vep_metadata_repository=SimpleNamespace(),
    )

    with pytest.raises(AppError, match="not active for ASP"):
        service._validate_filter_gene_lists(
            {"asp_id": "hema_gmsv1", "filters": {"somatic": {"snv": {"snvlists": ["other"]}}}},
            panel,
        )
