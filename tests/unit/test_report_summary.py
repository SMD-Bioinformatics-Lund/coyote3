from __future__ import annotations

from api.application.interpretation import report_summary


def test_create_comment_doc_sample_specific_shape(monkeypatch):
    """Sample-specific comments are stored as direct comment entries."""
    monkeypatch.setattr(report_summary, "current_username", lambda: "tester")
    monkeypatch.setattr(report_summary, "utc_now", lambda: "2026-03-17T00:00:00Z")
    monkeypatch.setattr(report_summary, "new_object_id", lambda: "cid-1")

    doc = report_summary.create_comment_doc({"text": "hello"})

    assert doc == {
        "_id": "cid-1",
        "hidden": 0,
        "text": "hello",
        "author": "tester",
        "time_created": "2026-03-17T00:00:00Z",
    }


def test_create_comment_doc_global_annotation_has_flat_variant_identities(monkeypatch):
    monkeypatch.setattr(report_summary, "current_username", lambda: "tester")
    monkeypatch.setattr(report_summary, "utc_now", lambda: "2026-03-17T00:00:00Z")

    doc = report_summary.create_comment_doc(
        {
            "text": "reviewed",
            "global": "global",
            "assay_group": "hematology",
            "subpanel": "base",
            "gene": "SRSF2",
            "transcript": "NM_003016.4",
            "var_p": "p.Met89Val",
            "var_c": "c.265A>G",
            "var_g": "17:76736896:T/C",
        },
        nomenclature="p",
        variant="p.Met89Val",
    )

    assert doc["hgvsp"] == "p.Met89Val"
    assert doc["hgvsc"] == "c.265A>G"
    assert doc["genomic"] == "17_76736896_T_C"
    assert "genomic_hash" in doc


def test_summarize_bio_uses_current_msi_percentage_key():
    """Biomarker report text uses the current `per` field from the DB contract."""
    text = report_summary.summarize_bio([{"MSIS": {"tot": 10, "som": 2, "per": 20.0}}])

    assert "20.0% mikrosatellitinstabilitet" in text


def test_summarize_bio_accepts_historical_percentage_key():
    """Existing rows with the historical `perc` field should not break sample loading."""
    text = report_summary.summarize_bio([{"MSIP": {"tot": 10, "som": 2, "perc": 21.5}}])

    assert "21.5% mikrosatellitinstabilitet" in text
