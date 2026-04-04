"""Unit tests for persistence bootstrap wiring."""

from __future__ import annotations

from api.config import get_enabled_knowledgebase_plugins


def test_knowledgebase_plugins_default_to_all():
    assert get_enabled_knowledgebase_plugins({}) == ["all"]
    assert get_enabled_knowledgebase_plugins({"KNOWLEDGEBASE_PLUGINS": "civic, oncokb"}) == [
        "civic",
        "oncokb",
    ]
    assert get_enabled_knowledgebase_plugins({"KNOWLEDGEBASE_PLUGINS": ["civic", " OncoKB "]}) == [
        "civic",
        "oncokb",
    ]
    assert get_enabled_knowledgebase_plugins({"KNOWLEDGEBASE_PLUGINS": []}) == ["all"]
    assert get_enabled_knowledgebase_plugins({"KNOWLEDGEBASE_PLUGINS": ""}) == ["all"]
