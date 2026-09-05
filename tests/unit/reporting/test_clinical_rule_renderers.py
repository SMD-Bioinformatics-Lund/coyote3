"""Exhaustive deterministic-renderer tests for clinical reporting rules."""

from __future__ import annotations

import pytest

from api.application.reporting.clinical_rules.renderers import (
    render_dna_report_intro,
    render_fusion_summary,
    render_named,
    render_tier_summary,
)
from api.application.reporting.clinical_rules.terminology_defaults import (
    DNA_TERMINOLOGY,
    FUSION_TERMINOLOGY,
)
from api.domain.common.reporting import STANDARD_TIER_SUMMARY_PHRASES


def _terms() -> dict:
    return {
        "tier_summary": STANDARD_TIER_SUMMARY_PHRASES,
        "dna_report_intro": {**DNA_TERMINOLOGY, "base_text": "Bas. "},
        "fusion_summary": FUSION_TERMINOLOGY,
    }


def test_required_terminology_is_never_silently_defaulted() -> None:
    with pytest.raises(ValueError, match="terminology is missing 'tier_summary'"):
        render_tier_summary([], {})


def test_tier_summary_covers_single_multiple_and_three_tier_connectors() -> None:
    groups = [
        {
            "tier": 1,
            "finding_count": 1,
            "genes": [{"gene": "TP53", "vaf_percentages": ["22%"]}],
        },
        {
            "tier": 2,
            "finding_count": 2,
            "genes": [
                {"gene": "DNMT3A", "vaf_percentages": ["12%"]},
                {"gene": "FLT3", "vaf_percentages": ["8%"]},
            ],
        },
        {"tier": 3, "finding_count": 1, "genes": []},
    ]

    text = render_tier_summary(groups, _terms())

    assert "Vid analysen finner man" in text
    assert "Vidare ses" in text
    assert "Slutligen ses" in text
    assert "TP53" in text
    assert "DNMT3A" in text
    assert "FLT3" in text


def test_tier_summary_uses_middle_connector_for_two_groups() -> None:
    groups = [
        {"tier": 1, "finding_count": 1, "genes": []},
        {"tier": 2, "finding_count": 1, "genes": []},
    ]
    assert "Vidare ses" in render_tier_summary(groups, _terms())


def test_tier_summary_covers_context_suppression_branches() -> None:
    terms = _terms()
    terms["tier_summary"] = dict(terms["tier_summary"])
    terms["tier_summary"]["single_gene_always_read_context"] = False
    groups = [
        {
            "tier": 1,
            "finding_count": 2,
            "genes": [
                {"gene": "A", "vaf_percentages": ["10%"]},
                {"gene": "B", "vaf_percentages": ["9%"]},
            ],
        },
        {
            "tier": 2,
            "finding_count": 1,
            "genes": [{"gene": "C", "vaf_percentages": ["8%"]}],
        },
        {
            "tier": 3,
            "finding_count": 2,
            "genes": [
                {"gene": "D", "vaf_percentages": ["7%"]},
                {"gene": "E", "vaf_percentages": ["6%"]},
            ],
        },
    ]
    assert "A" in render_tier_summary(groups, terms)


@pytest.mark.parametrize(
    ("scope", "expected", "unexpected"),
    [
        (
            {"sample": {"paired": False}, "asp": {}, "applied_gene_lists": []},
            "Bas. ",
            "Analysen omfattar",
        ),
        (
            {
                "sample": {"paired": False},
                "asp": {},
                "applied_gene_lists": [{"isgl_id": "", "selected_for": ["snv"], "genes": ["TP53"]}],
            },
            "Bas. ",
            "Analysen omfattar",
        ),
        (
            {
                "sample": {"paired": True},
                "asp": {"germline_genes": ["TP53"]},
                "applied_gene_lists": [
                    {"isgl_id": "solid", "selected_for": ["snv"], "genes": ["TP53"]}
                ],
            },
            "konstitutionella mutationer",
            "never",
        ),
        (
            {
                "sample": {"paired": False},
                "asp": {},
                "applied_gene_lists": [
                    {"isgl_id": "a", "selected_for": ["snv"], "genes": ["TP53", "KRAS"]},
                    {"isgl_id": "b", "selected_for": ["snv"], "genes": ["KRAS", "BRAF"]},
                ],
            },
            "genlistorna",
            "never",
        ),
    ],
)
def test_dna_intro_scope_variants(scope, expected, unexpected) -> None:
    text = render_dna_report_intro(scope, _terms())
    assert expected in text
    assert unexpected not in text


def test_dna_intro_uses_gene_count_for_large_lists_and_omits_empty_genes() -> None:
    genes = [f"GENE{index}" for index in range(22)] + ["", "GENE1"]
    scope = {
        "sample": {"paired": True},
        "asp": {"germline_genes": []},
        "applied_gene_lists": [
            {"isgl_id": "large", "selected_for": ["snv"], "genes": genes},
            {"isgl_id": "cnv", "selected_for": ["cnv"], "genes": ["IGNORED"]},
        ],
    }
    assert "22 gener" in render_dna_report_intro(scope, _terms())


def test_fusion_summary_filters_nonreportable_rows_and_renders_optional_evidence() -> None:
    findings = [
        {"kind": "snv", "tier": 1, "fusion_gene_1": "A", "fusion_gene_2": "B"},
        {"kind": "fusion", "tier": 4, "fusion_gene_1": "A", "fusion_gene_2": "B"},
        {"kind": "fusion", "tier": 1, "fusion_gene_1": "A"},
        {
            "kind": "fusion",
            "tier": 1,
            "fusion_gene_1": "KMT2A",
            "fusion_gene_2": "AFF1",
            "fusion_breakpoint_1": "11:1",
            "fusion_breakpoint_2": "4:2",
            "fusion_spanning_pairs": 12,
            "fusion_spanning_reads": 7,
            "fusion_annotation": "Reviewed annotation",
        },
        {
            "kind": "fusion",
            "tier": 2,
            "fusion_gene_1": "RUNX1",
            "fusion_gene_2": "RUNX1T1",
            "fusion_annotation": "   ",
        },
    ]

    text = render_fusion_summary(findings, _terms())

    assert "KMT2A" in text
    assert "11:1" in text
    assert "12" in text
    assert "Reviewed annotation" in text
    assert "Vidare finner man" in text
    assert "Tier IV" not in text
    assert render_fusion_summary([], _terms()) == "\n\n"


@pytest.mark.parametrize("name", ["dna_report_intro", "tier_summary", "fusion_summary"])
def test_named_renderer_dispatches_every_supported_renderer(name) -> None:
    scope = {"sample": {"paired": False}, "asp": {}, "applied_gene_lists": []}
    source = []
    assert isinstance(render_named(name, source=source, scope=scope, terminology=_terms()), str)


def test_named_renderer_rejects_unknown_capabilities() -> None:
    with pytest.raises(ValueError, match="Unsupported clinical renderer"):
        render_named("unknown", source=None, scope={}, terminology={})
