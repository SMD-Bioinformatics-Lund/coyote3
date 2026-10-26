"""Check dependency documentation coverage and rejection of stale source mappings."""

import json
from copy import deepcopy
from xml.etree import ElementTree

import pytest

from scripts.docs import export_collection_dependencies as exporter


@pytest.fixture
def catalog():
    """Load the reviewed relationship metadata used by the documentation generator."""
    return json.loads(exporter.CATALOG.read_text())


def test_every_namespace_has_diagram_and_incoming_and_outgoing_tables(catalog):
    """Cover physical namespaces separately, including the two different samples collections."""
    collections = exporter.inventory()
    edges = exporter.relationships(catalog, collections)
    output = exporter.render(catalog, collections, edges)
    assert "primary.samples" in collections
    assert "bam.samples" in collections
    for namespace in collections:
        group = exporter.group_for(namespace, catalog["groups"])
        page = output[exporter.DESTINATION / f"{group}.md"]
        section = page.split(f"## {namespace}\n", 1)[1].split("\n## ", 1)[0]
        assert "### Outgoing dependencies" in section
        assert "### Incoming references and migration impact" in section
        svg = output[exporter.ASSETS / f"{exporter.slug(namespace)}.svg"]
        root = ElementTree.fromstring(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
        for edge in edges:
            if namespace in (edge["source"], edge["target"]):
                assert f"`{edge['field']}`" in section
                assert f"`{edge['target_field']}`" in section


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "primary.does_not_exist", "Unknown namespace"),
        ("target", "identity.does_not_exist", "Unknown namespace"),
        ("evidence", "does-not-exist.py", "Missing evidence"),
        ("field", "does_not_exist", "Unknown source field"),
    ],
)
def test_invalid_reviewed_reference_is_rejected(catalog, field, value, message):
    """Reject unknown namespaces, evidence files and typed source fields before rendering."""
    catalog = deepcopy(catalog)
    catalog["edges"][0][field] = value
    with pytest.raises(ValueError, match=message):
        exporter.relationships(catalog, exporter.inventory())


def test_generated_reference_matches_reviewed_source(catalog):
    """Require checked-in pages and diagrams to match current bindings and reviewed mappings."""
    collections = exporter.inventory()
    edges = exporter.relationships(catalog, collections)
    for path, content in exporter.render(catalog, collections, edges).items():
        assert path.read_text() == content, str(path)
