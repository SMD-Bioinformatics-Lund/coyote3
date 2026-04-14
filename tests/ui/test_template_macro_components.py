"""Template macro regression tests for shared UI components."""

from __future__ import annotations

from pathlib import Path


def test_macro_library_files_exist():
    """Shared badge and action macro files should exist."""
    assert Path("coyote/templates/macros/badges.html").exists()
    assert Path("coyote/templates/macros/actions.html").exists()


def test_templates_import_shared_macro_components():
    """Key templates should use the shared macros instead of duplicating markup."""
    dna_findings = Path("coyote/blueprints/dna/templates/list_dna_findings.html").read_text()
    fusion_list = Path("coyote/blueprints/rna/templates/list_fusions.html").read_text()
    tiered_info = Path("coyote/blueprints/dna/templates/tiered_variant_info.html").read_text()

    assert '{% from "macros/badges.html" import tier_badge %}' in dna_findings
    assert "{{ tier_badge(" in dna_findings
    assert '{% from "macros/badges.html" import tier_badge %}' in fusion_list
    assert "{{ tier_badge(" in fusion_list
    assert '{% from "macros/actions.html" import link_button %}' in tiered_info
    assert (
        '{% from "macros/badges.html" import meta_chip, status_badge, tier_badge %}' in tiered_info
    )
