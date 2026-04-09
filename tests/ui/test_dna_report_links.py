"""Regression tests for DNA report link generation."""

from __future__ import annotations

from pathlib import Path


def test_dna_report_templates_use_sample_name_for_preview_and_save_routes():
    """Preview and finalize links should use the public sample name, not the DB id."""
    findings_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/dna/templates/list_dna_findings.html"
    ).read_text(encoding="utf-8")
    report_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/dna/templates/dna_report.html"
    ).read_text(encoding="utf-8")

    assert "url_for('dna_bp.generate_dna_report', sample_id=sample.name)" in findings_template
    assert "url_for('dna_bp.generate_dna_report', sample_id=sample._id)" not in findings_template
    assert (
        "summary_preview_url = url_for('dna_bp.generate_dna_report', sample_id=sample.name)"
        in findings_template
    )
    assert (
        "summary_preview_url = url_for('dna_bp.generate_dna_report', sample_id=sample._id)"
        not in findings_template
    )
    assert "url_for('dna_bp.save_dna_report', sample_id=sample.name)" in report_template
    assert "url_for('dna_bp.save_dna_report', sample_id=sample._id)" not in report_template
    assert (
        "url_for('common_bp.get_sample_genelists', sample_id=sample.name, _external=True)"
        in report_template
    )
    assert "url_for('common_bp.get_sample_genelists', sample_id=sample._id" not in report_template


def test_dna_report_config_link_posts_to_report_configuration_anchor():
    """Report config link should open the rendered config page at the config section."""
    report_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/dna/templates/dna_report.html"
    ).read_text(encoding="utf-8")
    sample_genes_template = Path(
        "/home/ram/dev/projects/coyote3/coyote/blueprints/common/templates/sample_genes.html"
    ).read_text(encoding="utf-8")

    assert '}#config" method="POST" target="_blank"' in report_template
    assert 'name="report_genelists"' in report_template
    assert 'name="panel_doc"' in report_template
    assert 'name="report_sample_filters"' in report_template
    assert 'id="report-genelists"' in report_template
    assert 'JSON.parse(document.getElementById("report-genelists").textContent)' in report_template
    assert 'section id="config"' in sample_genes_template
