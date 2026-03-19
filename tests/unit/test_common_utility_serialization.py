from __future__ import annotations

from bson import ObjectId
from pydantic import BaseModel

from api.utils.common_utility import CommonUtility


class _PayloadModel(BaseModel):
    payload: dict


class _DynamicGetAttr:
    def __getattr__(self, _name):
        return self


def test_convert_to_serializable_converts_object_ids_in_model_dump():
    oid = ObjectId()
    model = _PayloadModel(payload={"_id": oid, "items": [{"ref": oid}]})

    converted = CommonUtility.convert_to_serializable(model)

    assert converted["payload"]["_id"] == str(oid)
    assert converted["payload"]["items"][0]["ref"] == str(oid)


def test_convert_to_serializable_converts_object_ids_in_nested_mapping():
    oid = ObjectId()
    payload = {"value": {"_id": oid, "nested": [oid]}}

    converted = CommonUtility.convert_to_serializable(payload)

    assert converted["value"]["_id"] == str(oid)
    assert converted["value"]["nested"] == [str(oid)]


def test_convert_to_serializable_ignores_dynamic_fake_model_dump_attributes():
    dynamic = _DynamicGetAttr()
    converted = CommonUtility.convert_to_serializable(dynamic)
    assert converted is dynamic
