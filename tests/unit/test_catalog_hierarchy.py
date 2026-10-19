"""Catalog navigation and inheritance remain independent of clinical query rules."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from api.contracts.schemas.public_catalog import PublicCatalogModalityDoc
from api.domain.catalog_hierarchy import resolve_catalog_categories


def test_nearest_parent_inheritance_preserves_local_identity_and_explicit_empty():
    """Nested children replace complete fields and can suppress inherited wording."""
    section = {
        "tat": "20 days",
        "categories": {
            "panels": {"label": "Panels", "node_kind": "folder", "tat": "10 days"},
            "solid": {
                "label": "Solid",
                "parent_key": "panels",
                "analysis": ["SNV"],
                "gene_lists": [{"isgl_id": "solid", "analysis": ["SNV"]}],
            },
            "breast": {"label": "Breast", "parent_key": "solid"},
            "colon": {
                "label": "Colon",
                "parent_key": "solid",
                "tat": "",
                "clear_fields": ["tat"],
                "analysis": ["CNV"],
                "no_gene_list": ["CNV"],
            },
        },
    }
    original = deepcopy(section)
    result = resolve_catalog_categories(section)
    assert result["breast"]["label"] == "Breast"
    assert result["breast"]["tat"] == "10 days"
    assert result["breast"]["analysis"] == ["SNV"]
    assert result["breast"]["gene_lists"] == section["categories"]["solid"]["gene_lists"]
    assert result["colon"]["tat"] == ""
    assert result["colon"]["analysis"] == ["CNV"]
    assert section == original


@pytest.mark.parametrize(
    "categories",
    [
        {"a": {"parent_key": "missing"}},
        {"a": {"parent_key": "a"}},
        {"a": {"parent_key": "b"}, "b": {"parent_key": "a"}},
    ],
)
def test_contract_rejects_invalid_parent_relationships(categories):
    """Draft save rejects missing parents and cyclic navigation."""
    with pytest.raises(ValidationError):
        PublicCatalogModalityDoc.model_validate({"categories": categories})


def test_defaulted_contract_fields_still_inherit():
    """Pydantic's empty defaults must not erase parent presentation values."""
    section = PublicCatalogModalityDoc.model_validate(
        {
            "categories": {
                "group": {"node_kind": "folder", "analysis": ["SNV"], "tat": "10 days"},
                "child": {"parent_key": "group"},
            }
        }
    )
    result = resolve_catalog_categories(section.model_dump())
    assert result["child"]["analysis"] == ["SNV"]
    assert result["child"]["tat"] == "10 days"
