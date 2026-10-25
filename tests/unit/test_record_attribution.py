"""Record actors are server-owned and independent of administrative permissions."""

import pytest

from coyote3.application.common.protected_records import (
    reject_system_managed_change,
    reject_system_managed_delete,
)
from coyote3.application.common.record_attribution import attribute_record
from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from coyote3.domain.exceptions import AppError


def test_every_collection_exposes_creation_and_update_actors():
    for name, adapter in COLLECTION_MODEL_ADAPTERS.items():
        assert {"created_by", "updated_by"} <= adapter.json_schema()["properties"].keys(), name


def test_import_does_not_trust_submitted_actors_or_installation_flags():
    proposed = {
        "created_by": "forged",
        "updated_by": "forged",
        "system_installed": True,
        "system_managed": True,
    }
    result = attribute_record(proposed, actor="authenticated.author")
    assert result == {
        "created_by": "authenticated.author",
        "updated_by": "authenticated.author",
        "system_installed": False,
        "system_managed": False,
    }
    assert proposed["created_by"] == "forged"


def test_edit_preserves_creator_and_records_new_actor():
    previous = {"created_by": "first.author", "updated_by": "previous.editor"}
    result = attribute_record({"created_by": "spoofed"}, actor="next.editor", previous=previous)
    assert result["created_by"] == "first.author"
    assert result["updated_by"] == "next.editor"


def test_unknown_historical_creator_is_not_replaced_with_editor():
    result = attribute_record({}, actor="editor", previous={})
    assert result["created_by"] is None
    assert result["updated_by"] == "editor"


def test_installed_catalog_is_attributed_to_system_not_operator():
    result = attribute_record({}, actor="installation.operator", system_installation=True)
    assert result["created_by"] == result["updated_by"] == "system"
    assert result["system_installed"] is True


@pytest.mark.parametrize("flag", ["system_managed", "system_installed"])
@pytest.mark.parametrize("operation", [reject_system_managed_change, reject_system_managed_delete])
def test_both_installed_flags_block_administrative_writes(flag, operation):
    with pytest.raises(AppError) as error:
        operation({flag: True}, resource="test resource")
    assert error.value.status_code == 409


def test_automated_creation_alone_does_not_disable_normal_sample_workflows():
    reject_system_managed_change(
        {"created_by": "system", "system_installed": False}, resource="sample"
    )
