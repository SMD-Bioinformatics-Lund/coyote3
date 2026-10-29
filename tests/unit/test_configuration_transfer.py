"""Configuration audit fields cannot override newly created application records."""

from copy import deepcopy

from coyote3.domain.common.configuration_transfer import configuration_content


def test_record_metadata_is_removed_without_traversing_clinical_content():
    """Nested predicate values and pinned resource versions are authored content."""
    source = {
        "version": 8,
        "created_by": "old.author",
        "panel": {"asp_id": "panel", "version": 4},
        "gene_lists": [{"isgl_id": "genes", "version": 7, "genes": ["TP53"]}],
        "configurations": [
            {"asp_id": "panel", "created_on": "old", "reporting": {"reference": {"version": 3}}}
        ],
        "content": {"condition": {"field": "status", "value": {"version": 2}}},
    }
    before = deepcopy(source)
    assert configuration_content(source) == {
        "panel": {"asp_id": "panel"},
        "gene_lists": [{"isgl_id": "genes", "genes": ["TP53"]}],
        "configurations": [{"asp_id": "panel", "reporting": {"reference": {"version": 3}}}],
        "content": source["content"],
    }
    assert source == before


def test_metadata_free_records_need_no_audit_placeholders():
    """Ordinary records, arrays and invalid shapes retain validation semantics."""
    assert configuration_content([{"name": "Example", "status": "published"}]) == [
        {"name": "Example"}
    ]
    assert configuration_content({"name": "Example"}) == {"name": "Example"}
    assert configuration_content(None) is None
