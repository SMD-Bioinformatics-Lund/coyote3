"""Focused regressions for ASPC create/edit contract flow."""

from __future__ import annotations

from types import SimpleNamespace

from coyote.util.admin_utility import AdminUtility


def test_admin_utility_process_form_to_config_keeps_structured_aspc_fields_as_dicts() -> None:
    """Structured ASPC form fields should stay as dict payloads."""
    schema = {
        "fields": {
            "filters": {"data_type": "json", "display_type": "filters-structured"},
            "reporting": {"data_type": "json", "display_type": "reporting-structured"},
            "query": {"data_type": "json", "display_type": "jsoneditor"},
        }
    }
    form = {
        "filters": {"min_alt_reads": 5},
        "reporting": {"report_sections": ["SNV"]},
        "query": {"snv": {"flag": True}},
    }

    config = AdminUtility.process_form_to_config(form, schema)

    assert config["filters"] == {"min_alt_reads": 5}
    assert config["reporting"] == {"report_sections": ["SNV"]}
    assert config["query"] == {"snv": {"flag": True}}


def test_aspc_service_create_inherits_scope_fields_from_selected_asp(monkeypatch) -> None:
    """ASPC create should trust the selected ASP for scope and platform metadata."""
    import api.services.resources.aspc as aspc_module
    from api.services.resources.aspc import AspcService

    created: list[dict] = []
    service = AspcService(
        assay_configuration_handler=SimpleNamespace(
            get_aspc_with_id=lambda _id: None,
            create_assay_config=lambda config: created.append(config),
        ),
        assay_panel_handler=SimpleNamespace(
            get_asp=lambda assay: {
                "asp_id": assay,
                "assay_name": assay,
                "asp_group": "hematology",
                "asp_category": "dna",
                "platform": "illumina",
            }
        ),
        vep_metadata_handler=SimpleNamespace(get_consequence_group_options=lambda *a, **k: []),
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
                "assay_name": "hema_GMSv1",
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
    assert created[0]["filters"] == {"min_alt_reads": 5}
