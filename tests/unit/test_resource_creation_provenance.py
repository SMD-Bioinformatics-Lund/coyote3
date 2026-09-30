"""Client metadata cannot impersonate the creator of a managed resource."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.application.resources import asp, isgl


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
        config = {"asp_id": "demo_assay", "asp_group": "demo"}
    else:
        service = isgl.IsglService(
            gene_list_repository=SimpleNamespace(
                get_isgl=lambda identifier: None, create_genelist=create
            ),
            assay_panel_repository=SimpleNamespace(),
            assay_subpanel_repository=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "_validate_asp_scope", lambda config: None)
        monkeypatch.setattr(service, "_validate_subpanels", lambda config: None)
        config = {"isgl_id": "demo_genes"}
    config.update(created_by="forged_actor", created_on="forged_time", system_managed=True)
    service.create(payload={"config": config}, actor_username="request_actor")
    stored = create.call_args.args[0]
    assert stored["created_by"] == "authenticated_actor"
    assert stored["created_on"] == "server_time"
    assert stored["system_managed"] is False
