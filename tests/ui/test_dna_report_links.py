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
