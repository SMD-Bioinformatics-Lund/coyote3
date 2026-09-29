"""ISGL scope choices come from associated registry records rather than free text."""

from types import SimpleNamespace

import pytest

from api.application.resources.isgl import IsglService
from api.domain.core.exceptions import AppError


@pytest.fixture
def service():
    """Provide arbitrary center-defined group and subpanel identifiers."""
    return IsglService(
        gene_list_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: ["custom-group"],
            get_all_asps=lambda **_: [
                {"asp_id": "panel-a", "asp_group": "custom-group", "display_name": "Panel A"}
            ],
        ),
        assay_subpanel_repository=SimpleNamespace(
            list_for_assay=lambda asp_id, **_: (
                [{"subpanel_id": "custom-scope", "display_name": "Custom scope"}]
                if asp_id == "panel-a"
                else []
            )
        ),
    )


def test_form_uses_registry_choices_and_implicit_base(service):
    fields = service.create_context_payload(actor_username="test")["form"]["fields"]
    assert fields["asp_groups"]["options"] == ["custom-group"]
    assert fields["diagnosis"]["display_type"] == "checkbox-group"
    assert fields["diagnosis"]["default"] == ["base"]
    assert fields["diagnosis"]["options_by_field"] == {
        "field": "asp_ids",
        "values": {
            "panel-a": [
                {"value": "base", "label": "Base"},
                {"value": "custom-scope", "label": "Custom scope"},
            ]
        },
    }


@pytest.mark.parametrize("diagnosis", [[], ["base"], ["custom-scope"], ["base", "custom-scope"]])
def test_registered_scopes_and_base_are_accepted(service, diagnosis):
    service._validate_subpanels({"asp_ids": ["panel-a"], "diagnosis": diagnosis})


@pytest.mark.parametrize("assay,scope", [("panel-a", "unknown"), ("panel-b", "custom-scope")])
def test_unregistered_or_unassociated_scopes_are_rejected(service, assay, scope):
    with pytest.raises(AppError) as error:
        service._validate_subpanels({"asp_ids": [assay], "diagnosis": [scope]})
    assert error.value.status_code == 422


def test_unchanged_historical_assignments_are_preserved(service):
    existing = {"asp_ids": ["panel-a"], "diagnosis": ["retired"]}
    service._validate_subpanels(existing, previous=existing)
    with pytest.raises(AppError):
        service._validate_subpanels({**existing, "asp_ids": ["panel-b"]}, previous=existing)
