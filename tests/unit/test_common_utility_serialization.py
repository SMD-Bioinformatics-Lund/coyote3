from __future__ import annotations

from bson import ObjectId
from pydantic import BaseModel

from api.app.utilities.common import convert_to_serializable, nl_join


class _PayloadModel(BaseModel):
    payload: dict


class _DynamicGetAttr:
    def __getattr__(self, _name):
        return self


def test_convert_to_serializable_converts_object_ids_in_model_dump():
    oid = ObjectId()
    model = _PayloadModel(payload={"_id": oid, "items": [{"ref": oid}]})

    converted = convert_to_serializable(model)

    assert converted["payload"]["_id"] == str(oid)
    assert converted["payload"]["items"][0]["ref"] == str(oid)


def test_convert_to_serializable_converts_object_ids_in_nested_mapping():
    oid = ObjectId()
    payload = {"value": {"_id": oid, "nested": [oid]}}

    converted = convert_to_serializable(payload)

    assert converted["value"]["_id"] == str(oid)
    assert converted["value"]["nested"] == [str(oid)]


def test_convert_to_serializable_ignores_dynamic_fake_model_dump_attributes():
    dynamic = _DynamicGetAttr()
    converted = convert_to_serializable(dynamic)
    assert converted is dynamic


def test_nl_join_does_not_mutate_the_caller_list():
    values = ["A", "B", "C"]

    assert nl_join(values, "och") == "A, B och C"
    assert values == ["A", "B", "C"]
    assert nl_join([], "och") == ""
