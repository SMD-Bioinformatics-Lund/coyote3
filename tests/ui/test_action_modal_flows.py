"""UI regression tests for the shared action modal flow."""

from __future__ import annotations

from pathlib import Path


def test_layout_action_modal_supports_form_and_callback_actions():
    """The shared modal helper should support URL, form, and callback actions."""
    script = Path("coyote/static/js/layout.js").read_text()

    assert "onConfirm" in script
    assert "data-action-modal-form" in script
    assert "requestSubmit" in script
    assert "window.location.assign" in script


def test_variant_and_fusion_templates_mark_destructive_forms_for_modal():
    """Destructive DNA/RNA detail actions should delegate to the shared modal."""
    variant_template = Path(
        "coyote/blueprints/dna/templates/show_small_variant_vep.html"
    ).read_text()
    fusion_template = Path("coyote/blueprints/rna/templates/show_fusion.html").read_text()

    assert variant_template.count("data-action-modal-form") >= 4
    assert 'data-action-modal-title="Override Blacklist"' in variant_template
    assert 'data-action-modal-title="Remove Blacklist Override"' in variant_template
    assert fusion_template.count("data-action-modal-form") >= 1
    assert 'data-action-modal-title="Remove Tier"' in fusion_template
