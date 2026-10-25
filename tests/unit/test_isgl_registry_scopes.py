"""ISGL scope choices come from associated registry records rather than free text."""

from types import SimpleNamespace

import pytest

from coyote3.application.resources.isgl import IsglService
from coyote3.domain.exceptions import AppError


def test_gene_list_form_places_diagnosis_after_its_scope_prerequisites():
    """An empty gene-list form asks for groups and assays before dependent diagnoses."""
    from coyote3.application.accounts.common import build_managed_form
    from coyote3.contracts.authoring.resources import MANAGED_RESOURCE_SPECS

    form = build_managed_form(MANAGED_RESOURCE_SPECS["isgl"])
    assert "diagnosis" not in form["sections"]["list identity"]
    assert form["sections"]["clinical scope"] == ["asp_groups", "asp_ids", "diagnosis"]


def test_gene_list_ownership_is_not_an_editable_installation_choice():
    """Creation and editing cannot present installer-owned flags as user options."""
    from coyote3.application.accounts.common import build_managed_form
    from coyote3.contracts.authoring.resources import MANAGED_RESOURCE_SPECS

    fields = build_managed_form(MANAGED_RESOURCE_SPECS["isgl"])["fields"]
    for key in ("system_managed", "system_installed"):
        assert fields[key]["readonly"] is True
        assert set(fields[key]["hidden_mode"]) == {"create", "edit"}


@pytest.fixture
def service():
    """Provide arbitrary center-defined group and diagnosis identifiers."""
    return IsglService(
        gene_list_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: ["custom-group"],
            get_all_asps=lambda **_: [
                {"asp_id": "panel-a", "asp_group": "custom-group", "display_name": "Panel A"}
            ],
        ),
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda asp_id, **_: (
                [{"diagnosis_id": "custom-scope", "display_name": "Custom scope"}]
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
    service._validate_diagnoses({"asp_ids": ["panel-a"], "diagnosis": diagnosis})


@pytest.mark.parametrize("assay,scope", [("panel-a", "unknown"), ("panel-b", "custom-scope")])
def test_unregistered_or_unassociated_scopes_are_rejected(service, assay, scope):
    with pytest.raises(AppError) as error:
        service._validate_diagnoses({"asp_ids": [assay], "diagnosis": [scope]})
    assert error.value.status_code == 422


def test_unchanged_historical_assignments_are_preserved(service):
    existing = {"asp_ids": ["panel-a"], "diagnosis": ["retired"]}
    service._validate_diagnoses(existing, previous=existing)
    with pytest.raises(AppError):
        service._validate_diagnoses({**existing, "asp_ids": ["panel-b"]}, previous=existing)
