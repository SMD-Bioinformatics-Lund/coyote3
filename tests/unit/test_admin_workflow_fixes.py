"""Regression checks for managed forms, ingestion diagnostics, and email control wiring."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.application.accounts.users import UserManagementService
from api.application.ingest.json_resources import read_ingest_json
from api.contracts.managed_resources import managed_resource_spec
from api.contracts.managed_ui_schemas import build_form_spec
from api.domain.common.assay_filters import create_assay_group_map


def test_user_assay_options_follow_active_groups():
    service = object.__new__(UserManagementService)
    service._common_util = SimpleNamespace(create_assay_group_map=create_assay_group_map)
    service.assay_panel_repository = Mock()
    service.assay_panel_repository.get_all_asps.return_value = [
        {"asp_id": "heme_a", "asp_group": "hematology", "display_name": "Heme A"},
        {"asp_id": "solid_a", "asp_group": "solid", "display_name": "Solid A"},
    ]
    form = build_form_spec(managed_resource_spec("user"))
    service._configure_assay_choices(form)
    field = form["fields"]["asp_ids"]
    assert field["display_type"] == "checkbox-group"
    assert field["options_by_field"]["field"] == "asp_groups"
    assert field["options_by_field"]["values"]["hematology"][0]["value"] == "heme_a"
    assert field["options_by_field"]["values"]["solid"][0]["value"] == "solid_a"
    service.assay_panel_repository.get_all_asps.assert_called_once_with(is_active=True)


@pytest.mark.parametrize("content,reason", [("", "is empty"), ("{broken", "line 1, column 2")])
def test_json_error_identifies_resource_and_filename(tmp_path, content, reason):
    source = tmp_path / "synthetic.cnv.json"
    source.write_text(content)
    with pytest.raises(ValueError) as caught:
        read_ingest_json(str(source), "CNV")
    message = str(caught.value)
    assert "CNV" in message and "synthetic.cnv.json" in message and reason in message
    assert str(tmp_path) not in message


def test_valid_empty_json_is_distinct_from_empty_file(tmp_path):
    source = tmp_path / "synthetic.cnv.json"
    source.write_text("{}")
    assert read_ingest_json(str(source), "CNV") == {}


def test_email_config_reads_current_control(monkeypatch):
    from api.app.deps import services

    controls = SimpleNamespace(email=SimpleNamespace(enabled=False))
    service = Mock()
    service.get_controls.return_value = controls
    monkeypatch.setattr(services, "get_app_controls_service", lambda: service)
    assert services.get_email_config()["EMAIL_ENABLED"] is False
    controls.email.enabled = True
    assert services.get_email_config()["EMAIL_ENABLED"] is True
