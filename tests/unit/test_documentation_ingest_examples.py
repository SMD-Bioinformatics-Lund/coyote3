"""Keep downloadable pipeline examples compatible with actual ingest boundaries."""

import json
from pathlib import Path

import pytest

from coyote3.application.ingest.parsers import DnaIngestParser, _normalize_fusion_docs
from coyote3.contracts.schemas.dna import (
    BiomarkersDoc,
    CnvsDoc,
    D4CoverageDoc,
    PgxDoc,
    TranslocationsDoc,
    VariantsDoc,
)
from coyote3.contracts.schemas.rna import (
    FusionsDoc,
    RnaClassificationDoc,
    RnaExpressionDoc,
    RnaQcDoc,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "docs/assets/examples/ingest"


@pytest.mark.parametrize("fail", [False, True])
def test_small_variant_reader_closes_after_ingest(monkeypatch, fail):
    """Successful and rejected ingestion both release the open VCF handle."""
    from coyote3.application.ingest import analysis_parsers

    source = analysis_parsers.VariantFile(str(EXAMPLES / "small-variants-vcf.vcf"))
    monkeypatch.setattr(analysis_parsers, "VariantFile", lambda _: source)
    if fail:

        def reject_record(*args):
            """Simulate a malformed input after the reader has been opened."""
            raise ValueError("Invalid synthetic record")

        monkeypatch.setattr(analysis_parsers.cmdvcf, "parse_variant", reject_record)
        with pytest.raises(ValueError, match="Invalid synthetic record"):
            DnaIngestParser()._parse_snvs_only(str(EXAMPLES / "small-variants-vcf.vcf"))
    else:
        DnaIngestParser()._parse_snvs_only(str(EXAMPLES / "small-variants-vcf.vcf"))
    try:
        assert source.closed
    finally:
        source.close()


def test_small_variant_accepts_af_format_field(tmp_path):
    """The documented AF alternative must preserve measured allele fractions."""
    path = tmp_path / "af.vcf"
    path.write_text((EXAMPLES / "small-variants-vcf.vcf").read_text().replace("VAF", "AF"))
    rows = DnaIngestParser()._parse_snvs_only(
        str(path), case_id="SYNTHETIC-T", control_id="SYNTHETIC-N"
    )
    assert float(rows[0]["GT"][0]["AF"]) == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("copy-number", CnvsDoc),
        ("coverage", D4CoverageDoc),
        ("biomarkers", BiomarkersDoc),
        ("hrd", BiomarkersDoc),
        ("msi", BiomarkersDoc),
        ("tmb", BiomarkersDoc),
        ("fusions", FusionsDoc),
        ("expression", RnaExpressionDoc),
        ("classification", RnaClassificationDoc),
        ("quality-control", RnaQcDoc),
        ("pharmacogenomics", PgxDoc),
    ],
)
def test_raw_json_examples_satisfy_ingest_contracts(filename, model):
    """Validate downloaded JSON after the same normalization and parent injection as ingest."""
    payload = json.loads((EXAMPLES / f"{filename}.json").read_text())
    if filename == "copy-number":
        rows = DnaIngestParser._parse_cnvs_only(payload)
    elif filename == "fusions":
        rows = _normalize_fusion_docs(payload)
    else:
        rows = [payload]
    assert rows
    for row in rows:
        assert "SAMPLE_ID" not in row
        linked = dict(row, SAMPLE_ID="synthetic-sample-id")
        if filename == "coverage":
            linked["sample"] = "SYNTHETIC-T"
        model.model_validate(linked)


def test_small_variant_example_preserves_genotypes_and_transcript():
    """Parse the complete VCF and verify its case evidence and selected transcript."""
    rows = DnaIngestParser()._parse_snvs_only(
        str(EXAMPLES / "small-variants-vcf.vcf"),
        case_id="SYNTHETIC-T",
        control_id="SYNTHETIC-N",
    )
    assert len(rows) == 1
    variant = VariantsDoc.model_validate(dict(rows[0], SAMPLE_ID="synthetic-sample-id"))
    assert variant.GT[0].sample == "SYNTHETIC-T"
    assert variant.GT[0].AF == pytest.approx(0.4)
    assert variant.selected_csq_feature == "ENST000001.1"


def test_translocation_example_retains_gene_fusion_annotation():
    """Verify the complete breakend VCF produces one contract-valid gene fusion."""
    rows = DnaIngestParser()._parse_transloc_only(str(EXAMPLES / "translocations-vcf.vcf"))
    assert len(rows) == 1
    translocation = TranslocationsDoc.model_validate(dict(rows[0], SAMPLE_ID="synthetic-sample-id"))
    assert "gene_fusion" in translocation.INFO.ANN[0].Annotation
