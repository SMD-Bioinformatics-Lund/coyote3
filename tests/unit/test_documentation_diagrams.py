"""Documentation diagrams keep accessible labels, valid artwork and one shared theme."""

from pathlib import Path
from xml.etree import ElementTree

import pytest

from scripts.docs.collection_diagram_style import STYLE

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "docs/assets/diagrams"
SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize(
    "path", sorted(DIAGRAMS.rglob("*.svg")), ids=lambda path: str(path.relative_to(DIAGRAMS))
)
def test_diagrams_are_accessible_self_contained_and_share_the_approved_theme(path):
    """Catch broken symbol references, missing descriptions and divergent diagram styling."""
    root = ElementTree.parse(path).getroot()
    assert root.tag == SVG + "svg"
    assert root.findtext(SVG + "title")
    assert root.findtext(SVG + "desc")
    assert root.findtext(f"{SVG}defs/{SVG}style").strip() == STYLE
    elements = list(root.iter())
    identifiers = [element.attrib["id"] for element in elements if "id" in element.attrib]
    assert len(identifiers) == len(set(identifiers))
    for identifier in root.attrib["aria-labelledby"].split():
        assert identifier in identifiers
    for element in elements:
        assert element.tag not in {SVG + "script", SVG + "foreignObject", SVG + "image"}
        href = element.attrib.get("href")
        if href:
            assert href.startswith("#") and href[1:] in identifiers
        for marker in ("marker-start", "marker-end"):
            value = element.attrib.get(marker)
            if value:
                assert value.startswith("url(#") and value[5:-1] in identifiers
    # The document background supplies the light/dark surface.
    assert not root.findall(SVG + "rect")
