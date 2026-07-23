"""Focused regressions for ASPC create/edit contract flow."""

from __future__ import annotations

from types import SimpleNamespace

from bson import ObjectId


def test_business_identifiers_allow_clinical_subpanel_hyphens() -> None:
    """Clinical subpanel identifiers may contain hyphens, e.g. Hem-Snabb."""
    from api.config.constants import validate_identifier

    assert validate_identifier("Hem-Snabb", label="subpanel_id") == "Hem-Snabb"


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
                "assay_name": assay,
                "asp_group": "hematology",
                "asp_category": "dna",
                "platform": "illumina",
            }
        ),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda *a, **k: []),
        clinical_rule_set_repository=SimpleNamespace(),
        common_util=SimpleNamespace(),
    )

    monkeypatch.setattr(aspc_module, "current_actor", lambda username="admin-ui": username)
    monkeypatch.setattr(aspc_module, "utc_now", lambda: "now")
    monkeypatch.setattr(
        aspc_module,
        "inject_version_history",
        lambda actor_username, new_config, old_config=None, is_new=True: new_config,
    )
    monkeypatch.setattr(aspc_module, "_validated_doc", lambda collection, payload: payload)

    service.create(
        payload={
            "config": {
                "asp_id": "hema_GMSv1",
                "subpanel_id": "base",
                "environment": "production",
                "display_name": "Demo ASPC",
                "analysis_types": ["SNV"],
                "reporting": {"report_sections": ["SNV"]},
                "filters": {"min_alt_reads": 5},
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
    assert created[0]["aspc_id"] == "hema_GMSv1_base_production"
    assert created[0]["filters"] == {"min_alt_reads": 5}


def test_aspc_rule_binding_uses_verified_release_and_rotation(monkeypatch) -> None:
    """Binding a rule release delegates to the existing immutable ASPC rotation."""
    from api.application.resources.aspc import AspcService

    release_id = ObjectId()
    release = SimpleNamespace(
        id_=release_id,
        rule_set_id="generic_dna_reporting",
        version="1.0.0",
        content_hash="a" * 64,
        status="active",
        source=SimpleNamespace(
            rule_set=SimpleNamespace(
                scope=SimpleNamespace(
                    analyte="dna",
                    assay_ids=[],
                    assay_groups=[],
                    subpanel_ids=[],
                    environments=[],
                )
            )
        ),
    )
    service = AspcService(
        assay_configuration_repository=SimpleNamespace(
            get_aspc_with_id=lambda _id: {
                "aspc_id": "seed_assay_base_production",
                "asp_id": "seed_assay",
                "asp_group": "hematology",
                "asp_category": "dna",
                "subpanel_id": "base",
                "environment": "production",
                "reporting": {"report_header": "Seed"},
            }
        ),
        assay_panel_repository=SimpleNamespace(),
        vep_metadata_repository=SimpleNamespace(),
        clinical_rule_set_repository=SimpleNamespace(
            get_release=lambda requested_id: release if requested_id == str(release_id) else None
        ),
        common_util=SimpleNamespace(),
    )
    updates = []
    monkeypatch.setattr(
        service,
        "update",
        lambda **kwargs: updates.append(kwargs)
        or {
            "status": "ok",
            "sample_id": "",
            "resource": "aspc",
            "resource_id": kwargs["assay_id"],
            "action": "rotate",
            "meta": {},
        },
    )

    result = service.bind_clinical_rule_release(
        assay_id="seed_assay_base_production",
        release_id=str(release_id),
        actor_username="clinical.admin",
    )

    reference = updates[0]["payload"]["config"]["reporting"]["clinical_rule_release"]
    assert reference["release_id"] == release_id
    assert reference["content_hash"] == "a" * 64
    assert updates[0]["actor_username"] == "clinical.admin"
    assert result["action"] == "rotate"
