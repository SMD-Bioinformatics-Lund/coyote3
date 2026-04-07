"""Regression tests for coverage navigation links."""

from __future__ import annotations

from pathlib import Path


def test_findings_templates_open_coverage_in_new_tab():
    """DNA and RNA findings pages should open coverage in a new tab."""
    dna_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/dna/templates/list_dna_findings.html"
    ).read_text(encoding="utf-8")
    rna_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/rna/templates/list_fusions.html"
    ).read_text(encoding="utf-8")

    assert 'target="_blank"' in dna_template
    assert 'rel="noopener"' in dna_template
    assert "url_for('cov_bp.get_cov', sample_id=sample.name)" in dna_template

    assert 'target="_blank"' in rna_template
    assert 'rel="noopener"' in rna_template
    assert "url_for('cov_bp.get_cov', sample_id=sample.name)" in rna_template
