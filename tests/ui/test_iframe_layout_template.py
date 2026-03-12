"""Responsive iframe layout template checks."""

from __future__ import annotations


def test_contact_iframe_uses_viewport_fitting_classes():
    template_path = "coyote/blueprints/public/templates/contact.html"
    with open(template_path, encoding="utf-8") as handle:
        html = handle.read()

    assert "grid grid-cols-1 xl:grid-cols-3" in html
    assert "flex flex-col min-h-[60vh]" in html
    assert "relative flex-1 min-h-[22rem]" in html
    assert "absolute inset-0 h-full w-full rounded-2xl" in html
