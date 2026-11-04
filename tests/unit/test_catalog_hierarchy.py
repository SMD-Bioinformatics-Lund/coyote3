"""Catalog navigation and inheritance remain independent of clinical query rules."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from coyote3.application.public.published_catalog_views import catalog_discovery
from coyote3.contracts.schemas.public_catalog import PublicCatalogModalityDoc
from coyote3.domain.catalog_hierarchy import resolve_catalog_categories


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


def test_service_fields_inherit_from_immediate_parent_with_local_overrides():
    """Prices and descriptive service fields follow the same explicit parent precedence."""
    section = PublicCatalogModalityDoc.model_validate(
        {
            "price": {"amount": "900", "currency": "SEK"},
            "categories": {
                "hema": {
                    "node_kind": "folder",
                    "price": {"amount": "450", "currency": "SEK"},
                    "methodology": "Parent method",
                    "tat": "21 days",
                    "input_material": ["Bone marrow"],
                },
                "mpn": {"parent_key": "hema", "tat": "7 days"},
                "cll": {"parent_key": "hema", "clear_fields": ["price", "methodology"]},
            },
        }
    )
    result = resolve_catalog_categories(section.model_dump(mode="json"))
    assert result["mpn"]["price"]["amount"] == "450.00"
    assert result["mpn"]["methodology"] == "Parent method"
    assert result["mpn"]["tat"] == "7 days"
    assert result["mpn"]["input_material"] == ["Bone marrow"]
    assert result["cll"]["price"] is None
    assert result["cll"]["methodology"] == ""


def test_public_navigation_keeps_every_levels_wording_and_excludes_private_fields():
    """Parent content remains selectable without borrowing a child's service information."""
    document = {
        "version": 3,
        "header": "Synthetic catalog",
        "layout": {"order": ["rna", "dna"]},
        "resource_revisions": {"private": {"configuration_id": "private"}},
        "modalities": {
            "dna": {
                "label": "DNA",
                "description": "DNA overview",
                "tat": "10 days",
                "categories": {
                    "panels": {"label": "Panels", "node_kind": "folder"},
                    "hema": {
                        "label": "Hematology",
                        "parent_key": "panels",
                        "description": "Parent hematology information",
                        "node_kind": "folder",
                        "aspc_id": "private",
                        "extra_private": "not public",
                    },
                    "mpn": {
                        "label": "MPN",
                        "parent_key": "hema",
                        "description": "MPN details",
                        "clear_fields": ["tat"],
                        "tat": "",
                        "asp_id": "private",
                    },
                },
            },
            "rna": {"label": "RNA", "categories": {}},
        },
    }
    original = deepcopy(document)
    result = catalog_discovery(document)
    nodes = {node["node_id"]: node for node in result["navigation"]}
    assert list(nodes)[0] == "section:rna"
    assert nodes["entry:dna:hema"]["description"] == "Parent hematology information"
    assert nodes["entry:dna:mpn"]["description"] == "MPN details"
    assert nodes["entry:dna:mpn"]["parent_id"] == "entry:dna:hema"
    assert nodes["entry:dna:panels"]["description"] == "DNA overview"
    assert nodes["entry:dna:hema"]["turnaround"] == "10 days"
    assert nodes["entry:dna:mpn"]["turnaround"] == ""
    assert all(not {"aspc_id", "asp_id", "extra_private"} & node.keys() for node in nodes.values())
    assert "resource_revisions" not in result
    assert document == original
