"""Client metadata cannot impersonate the creator of a managed resource."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from coyote3.application.resources import asp, aspc, isgl
from coyote3.domain.exceptions import AppError


@pytest.mark.parametrize("resource", ["asp", "isgl"])
def test_creation_overrides_submitted_provenance(monkeypatch, resource):
    """Each creation path stamps actor and time before schema validation/storage."""
    module = asp if resource == "asp" else isgl
    monkeypatch.setattr(module, "current_actor", lambda username: "authenticated_actor")
    monkeypatch.setattr(module, "utc_now", lambda: "server_time")
    monkeypatch.setattr(module, "_validated_doc", lambda collection, config: config)
    create = Mock()
    if resource == "asp":
        service = asp.AspService(
            assay_panel_repository=SimpleNamespace(
                get_asp=lambda identifier: None,
                group_options=lambda: ["demo"],
                create_panel=create,
            )
        )
        config = {"asp_id": "demo_assay", "asp_group": "demo", "asp_family": "panel-rna"}
    else:
        service = isgl.IsglService(
            gene_list_repository=SimpleNamespace(
                get_isgl=lambda identifier: None, create_genelist=create
            ),
            assay_panel_repository=SimpleNamespace(),
            assay_diagnosis_repository=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "_validate_asp_scope", lambda config: None)
        monkeypatch.setattr(service, "_validate_diagnoses", lambda config: None)
        config = {"isgl_id": "demo_genes"}
    config.update(
        _id="imported-identifier",
        version=99,
        revision=99,
        status="published",
        created_by="forged_actor",
        created_on="forged_time",
        system_managed=True,
        system_installed=True,
    )
    service.create(payload={"config": config}, actor_username="request_actor")
    stored = create.call_args.args[0]
    assert stored["created_by"] == "authenticated_actor"
    assert stored["created_on"] == "server_time"
    assert stored["system_managed"] is False
    assert stored["system_installed"] is False
    assert "_id" not in stored and "revision" not in stored and "status" not in stored
    assert stored["version"] == 1
    if resource == "asp":
        assert stored["asp_category"] == "rna"


@pytest.mark.parametrize("resource", ["asp", "aspc", "isgl"])
def test_installed_resource_status_cannot_be_changed(resource):
    """Direct service calls cannot bypass the UI's installed-record lock."""
    record = {"system_installed": True, "is_active": True}
    repository = Mock()
    if resource == "asp":
        repository.get_asp.return_value = record
        service = asp.AspService(assay_panel_repository=repository)
        arguments = {"panel_id": "synthetic"}
    elif resource == "aspc":
        repository.get_aspc_with_id.return_value = record
        service = aspc.AspcService(
            assay_configuration_repository=repository,
            assay_panel_repository=Mock(),
            gene_list_repository=Mock(),
            vep_metadata_repository=Mock(),
            assay_diagnosis_repository=Mock(),
        )
        arguments = {"assay_id": "synthetic"}
    else:
        repository.get_isgl.return_value = record
        service = isgl.IsglService(
            gene_list_repository=repository,
            assay_panel_repository=Mock(),
            assay_diagnosis_repository=Mock(),
        )
        arguments = {"genelist_id": "synthetic"}
    with pytest.raises(AppError) as error:
        service.toggle(**arguments)
    assert error.value.status_code == 409
    assert len(repository.method_calls) == 1
