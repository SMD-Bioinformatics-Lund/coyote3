"""Report reconciliation is read-only and distinguishes unreferenced from missing files."""

from api.application.reporting.artifact_inventory import inspect_report_artifacts


def test_inventory_preserves_every_artifact_and_reports_missing_references(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    (root / "saved.html").write_text("synthetic")
    (root / "unreferenced.pdf").write_bytes(b"synthetic")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"synthetic")
    (root / "symlink.pdf").symlink_to(outside)
    result = inspect_report_artifacts(
        root,
        [
            {
                "_id": "saved",
                "filepath": str(root / "saved.html"),
                "pdf_filepath": str(root / "missing.pdf"),
            },
            {"_id": "outside", "filepath": str(outside)},
        ],
        minimum_age_seconds=0,
    )
    assert result["unreferenced"] == ["unreferenced.pdf"]
    assert result["missing"][0]["field"] == "pdf_filepath"
    assert result["outside_root"] == [{"report_oid": "outside", "field": "filepath"}]
    assert (root / "unreferenced.pdf").exists()
    assert (root / "saved.html").read_text() == "synthetic"
    assert outside.exists()


def test_fresh_files_are_not_classified_as_unreferenced(tmp_path):
    (tmp_path / "in-flight.html").write_text("synthetic")
    assert inspect_report_artifacts(tmp_path, [])["unreferenced"] == []
