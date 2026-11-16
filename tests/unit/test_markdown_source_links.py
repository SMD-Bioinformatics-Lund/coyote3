"""Stale documentation links remain detectable when their labels use code formatting."""

from scripts.docs.check_markdown_links import LINK_RE, REFERENCE_LINK_RE, strip_code


def test_code_formatted_labels_and_reference_targets_are_checked():
    source = "[`settings.py`](missing/settings.py)\n[`guide`]: missing/guide.md\n"
    cleaned = strip_code(source)
    assert LINK_RE.findall(cleaned) == ["missing/settings.py"]
    assert REFERENCE_LINK_RE.findall(cleaned) == ["missing/guide.md"]


def test_links_inside_code_examples_are_not_checked():
    source = "`[example](not-a-file)`\n```markdown\n[example](not-a-file)\n```\n"
    cleaned = strip_code(source)
    assert LINK_RE.findall(cleaned) == []
    assert REFERENCE_LINK_RE.findall(cleaned) == []
