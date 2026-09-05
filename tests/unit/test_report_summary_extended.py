from __future__ import annotations

import pytest

from api.application.interpretation import report_summary


def test_process_annotations_groups_class_and_text_by_required_context() -> None:
    grouped = report_summary.process_gene_annotations(
        [
            {"class": 1, "assay": "hema", "subpanel": "hem", "variant": "v1"},
            {"text": "one", "assay": "hema", "subpanel": "hem", "variant": "v1"},
            {"class": 2, "assay": "solid", "subpanel": "colon", "variant": "v2"},
        ]
    )
    assert grouped["hema:hem"]["v1"]["latest_class"]["class"] == 1
    assert grouped["hema:hem"]["v1"]["latest_text"]["text"] == "one"
    assert grouped["solid:colon"]["v2"]["latest_class"]["class"] == 2


def test_process_annotations_rejects_rows_without_required_context() -> None:
    with pytest.raises(KeyError, match="assay"):
        report_summary.process_gene_annotations([{"class": 2, "variant": "v2"}])


def test_global_structural_comment_shapes(monkeypatch) -> None:
    monkeypatch.setattr(report_summary, "current_username", lambda: "tester")
    monkeypatch.setattr(report_summary, "utc_now", lambda: "now")
    fusion = report_summary.create_comment_doc(
        {
            "global": "global",
            "comment": "fusion",
            "gene1": "KMT2A",
            "gene2": "AFF1",
        },
        nomenclature="f",
        variant="KMT2A_AFF1",
        key="comment",
    )
    cnv = report_summary.create_comment_doc(
        {"global": "global", "text": "gain", "gene": "EGFR"},
        nomenclature="cn",
        variant="7_gain",
    )
    assert fusion["gene1"] == "KMT2A" and fusion["gene2"] == "AFF1"
    assert "gene" not in fusion and "gene" not in cnv
    assert "transcript" not in cnv


def test_tier_classification_uses_last_selected_tier_and_defaults_zero() -> None:
    assert report_summary.get_tier_classification({}) == 0
    assert report_summary.get_tier_classification({"tier1": True, "tier4": False}) == 4


def test_enrichment_empty_and_missing_related_documents() -> None:
    class EmptySamples:
        def get_samples_by_oids(self, _oids):
            return [None]

    class EmptyAnnotations:
        def get_annotations_by_oids(self, _oids):
            return [None]

    assert (
        report_summary.enrich_reported_variant_docs(
            [], sample_repository=EmptySamples(), annotation_repository=EmptyAnnotations()
        )
        == []
    )
    enriched = report_summary.enrich_reported_variant_docs(
        [{"tier": 1}],
        sample_repository=EmptySamples(),
        annotation_repository=EmptyAnnotations(),
    )
    assert enriched[0]["sample"]["sample_name"] is None
    assert enriched[0]["annotation"] == {}
