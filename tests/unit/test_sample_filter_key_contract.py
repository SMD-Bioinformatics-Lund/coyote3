"""Guardrails for canonical sample filter shape."""

from __future__ import annotations

from pathlib import Path

from api.domain.common.sample_filters import merge_filter_defaults, normalize_sample_filters

RETIRED_SAMPLE_FILTER_DOT_PATHS = (
    "filters.genelists",
    "filters.cnv_genelists",
    "filters.min_depth",
    "filters.min_alt_reads",
    "filters.min_freq",
    "filters.max_freq",
    "filters.max_control_freq",
    "filters.max_popfreq",
    "filters.cnv_loss_cutoff",
    "filters.cnv_gain_cutoff",
    "filters.warn_cov",
    "filters.error_cov",
)


def test_sectioned_sample_filter_payload_stays_in_canonical_contract():
    """Runtime sample filters must stay in the current sectioned shape."""
    normalized = normalize_sample_filters(
        {
            "somatic": {
                "snv": {
                    "min_depth": 100,
                    "min_alt_reads": 5,
                    "snvlists": ["myeloid"],
                },
                "cnv": {
                    "cnvlists": ["cnv-myeloid"],
                    "cnv_loss_cutoff": -0.1,
                },
                "coverage": {"warn_cov": 500},
            },
        },
        omics_layer="dna",
    )

    assert normalized["snv"]["min_depth"] == 100
    assert normalized["snv"]["snvlists"] == ["myeloid"]
    assert normalized["cnv"]["cnvlists"] == ["cnv-myeloid"]
    assert normalized["cnv"]["cnv_loss_cutoff"] == -0.1
    assert normalized["coverage"]["warn_cov"] == 500
    assert "genelists" not in normalized
    assert "cnv_genelists" not in normalized


def test_backend_services_do_not_query_retired_flat_sample_filter_paths():
    """Runtime code should query sectioned filter paths, not retired flat paths."""
    roots = [Path("api/application"), Path("api/interfaces"), Path("api/infra")]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for dot_path in RETIRED_SAMPLE_FILTER_DOT_PATHS:
                if dot_path in text:
                    offenders.append(f"{path}: {dot_path}")

    assert not offenders, "Retired flat sample filter paths found:\n" + "\n".join(offenders)


def test_filter_defaults_complete_an_existing_empty_intent_profile():
    """A partial persisted snapshot receives missing values from its resolved ASPC."""
    merged = merge_filter_defaults(
        {"somatic": {}},
        {
            "somatic": {
                "snv": {"min_depth": 120, "snvlists": ["myeloid"]},
                "cnv": {"cnv_loss_cutoff": -0.2, "cnv_gain_cutoff": 0.2},
            }
        },
        omics_layer="dna",
        analysis_intents=["somatic"],
    )

    assert merged["somatic"]["snv"]["min_depth"] == 120
    assert merged["somatic"]["snv"]["snvlists"] == ["myeloid"]
    assert merged["somatic"]["cnv"]["cnv_loss_cutoff"] == -0.2
    assert merged["somatic"]["cnv"]["cnv_gain_cutoff"] == 0.2
