"""Synthetic SnpEff structural ingestion, pairing and transcript-selection regressions."""

from copy import deepcopy

import pytest

from api.application.dna.export import build_transloc_export_rows
from api.application.ingest.parsers import DnaIngestParser
from api.application.reporting.snapshot_rows import build_translocation_snapshot_rows
from api.contracts.schemas.dna import TranslocationsDoc
from api.domain.core.dna.structural_annotations import select_structural_annotation
from api.domain.core.dna.structural_identity import translocation_annotation_identity

HEADER = """##fileformat=VCFv4.2
##contig=<ID=1,length=1000000>
##contig=<ID=2,length=1000000>
##FILTER=<ID=LowQual,Description="Synthetic low quality">
##INFO=<ID=SVTYPE,Number=1,Type=String,Description="Structural type">
##INFO=<ID=MATEID,Number=1,Type=String,Description="Mate identifier">
##INFO=<ID=END,Number=1,Type=Integer,Description="End position">
##INFO=<ID=ANN,Number=.,Type=String,Description="Allele | Annotation | Annotation_Impact | Gene_Name | Gene_ID | Feature_Type | Feature_ID | Transcript_BioType | Rank | HGVS.c | HGVS.p">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""


def _ann(
    gene="GENEA",
    feature="ENST000001.1",
    effect="gene_fusion",
    impact="HIGH",
    biotype="protein_coding",
    custom=False,
):
    """Construct one complete synthetic SnpEff annotation."""
    return "|".join(
        [
            "N",
            effect,
            impact,
            gene,
            f"ID_{gene}",
            "CUSTOM&sorted" if custom else "transcript",
            feature,
            biotype,
            "",
            "c.?",
            "p.?",
        ]
    )


def _record(identifier, annotations, mate=None, svtype="BND", pos=100, end=None, quality="PASS"):
    """Construct a VCF record with optional reciprocal mate and interval."""
    info = [f"SVTYPE={svtype}", f"ANN={annotations}"]
    if mate is not None:
        info.append(f"MATEID={mate}")
    if end is not None:
        info.append(f"END={end}")
    alt = f"<{svtype}>" if svtype != "BND" else "N]2:500]"
    return f"1\t{pos}\t{identifier}\tN\t{alt}\t60\t{quality}\t{';'.join(info)}\n"


def _parse(tmp_path, records, parser=None):
    """Parse a temporary synthetic VCF and validate every retained finding."""
    path = tmp_path / "structural.vcf"
    path.write_text(HEADER + "".join(records))
    parser = parser or DnaIngestParser()
    rows = parser._parse_transloc_only(str(path))
    for row in rows:
        TranslocationsDoc.model_validate({**row, "SAMPLE_ID": "synthetic"})
    return rows


@pytest.mark.parametrize(
    "svtype,effect", [("DEL", "transcript_ablation"), ("DUP", "frameshift_variant")]
)
def test_symbolic_intervals_preserve_end_and_snpeff_annotations(tmp_path, svtype, effect):
    rows = _parse(tmp_path, [_record("interval", _ann(effect=effect), svtype=svtype, end=800)])
    assert rows[0]["END"] == 800
    assert rows[0]["INFO"]["ANN"][0]["Annotation"] == [effect]
    assert rows[0]["INFO"]["ANN_selection_source"] == "first_protein_coding"
    assert "MANE_ANN" not in rows[0]["INFO"]


def test_custom_pair_is_order_independent_and_preserves_multiple_annotations(tmp_path):
    left = _record(
        "left",
        ",".join(
            [
                _ann(feature="GENEA_ID1", effect="feature_fusion&gene_fusion", custom=True),
                _ann(feature="GENEC_ID3", effect="feature_fusion", custom=True),
            ]
        ),
        mate="right",
    )
    right = _record(
        "right",
        _ann(gene="GENEB", feature="GENEB_ID2", effect="feature_fusion", custom=True),
        mate="left",
        pos=200,
    )
    first = _parse(tmp_path, [left, right])
    assert first == _parse(tmp_path, [right, left])
    assert len(first) == 1
    row = first[0]
    assert row["ID"] == "left"
    assert [record["ID"] for record in row["source_records"]] == ["left", "right"]
    assert len(row["source_records"][0]["INFO"]["ANN"]) == 2
    assert len(row["INFO"]["ANN"]) == 5
    assert {ann["Gene_Name"] for ann in row["INFO"]["ANN"] if ann["Gene_Name"].count("&")} == {
        "GENEA&GENEB",
        "GENEC&GENEB",
    }


@pytest.mark.parametrize(
    "fault",
    ["missing", "self", "nonreciprocal", "filtered", "duplicate", "malformed", "multiple_mates"],
)
def test_invalid_custom_pairs_fail_without_partial_results(tmp_path, fault):
    feature = "malformed" if fault == "malformed" else "GENEA_ID1"
    left = _record(
        "left",
        _ann(feature=feature, effect="feature_fusion", custom=True),
        mate="left" if fault == "self" else "right,other" if fault == "multiple_mates" else "right",
    )
    right = _record(
        "right",
        _ann(gene="GENEB", feature="GENEB_ID2", effect="feature_fusion", custom=True),
        mate="other" if fault == "nonreciprocal" else "left",
        quality="LowQual" if fault == "filtered" else "PASS",
    )
    records = [left] if fault in {"missing", "self"} else [left, right]
    if fault == "duplicate":
        records.append(left)
    with pytest.raises(ValueError):
        _parse(tmp_path, records)


def test_exclusions_are_counted_and_all_source_annotations_remain(tmp_path):
    parser = DnaIngestParser()
    rows = _parse(
        tmp_path,
        [
            _record("mixed", _ann() + "," + _ann(effect="intron_variant")),
            _record("pseudo", _ann(biotype="pseudogene")),
            _record("low", _ann(), quality="LowQual"),
            _record("inv", _ann(), svtype="INV"),
        ],
        parser,
    )
    assert len(rows) == 1
    assert len(rows[0]["INFO"]["ANN"]) == 2
    assert any("no_eligible_annotation" in warning for warning in parser.translocation_warnings)
    assert any("not_pass" in warning for warning in parser.translocation_warnings)
    assert any("unsupported_svtype" in warning for warning in parser.translocation_warnings)


def test_mane_uses_internal_hgnc_priority_before_snpeff_impact(tmp_path):
    hgnc = {
        "hgnc_symbol": "GENEA",
        "ensembl_mane_select": "ENST000001.9",
        "refseq_mane_plus_clinical": ["NM_000002.4"],
    }
    parser = DnaIngestParser(hgnc_by_symbol={"GENEA": hgnc})
    rows = _parse(
        tmp_path,
        [_record("mane", _ann() + "," + _ann(feature="NM_000002.1", impact="LOW"))],
        parser,
    )
    info = rows[0]["INFO"]
    assert info["ANN_selection_source"] == "ncbi_mane_plus_clinical"
    assert info["MANE_ANN"]["Feature_ID"] == "NM_000002.1"
    assert len(info["ANN"]) == 2


def test_every_partner_must_have_exact_mane_evidence():
    ann = {
        "Gene_Name": "GENEA&GENEB",
        "Gene_ID": "A&B",
        "Feature_ID": "ENST000001.4&ENST000002.1",
        "Annotation_Impact": "HIGH",
        "Transcript_BioType": "protein_coding",
    }
    metadata = {
        "GENEA": {"ensembl_mane_select": "ENST000001"},
        "GENEB": {"ensembl_mane_select": "ENST000002"},
    }
    original = deepcopy(ann)
    assert select_structural_annotation([ann], {}, metadata)[1] == "ensembl_mane_select"
    metadata["GENEB"]["ensembl_mane_select"] = "ENST0000020"
    assert select_structural_annotation([ann], {}, metadata)[1] == "first_protein_coding"
    assert ann == original


def test_unspecified_impact_has_a_fallback_and_never_claims_vep_canonical():
    ann = {"Transcript_BioType": "protein_coding", "CANONICAL": "YES"}
    assert select_structural_annotation([ann], {}, {}) == (ann, "first_protein_coding")


def test_symbolic_interval_requires_explicit_end(tmp_path):
    with pytest.raises(ValueError, match="explicit END"):
        _parse(tmp_path, [_record("missing-end", _ann(), svtype="DEL")])


def test_interval_identity_and_exports_preserve_distinct_endpoints(tmp_path):
    rows = _parse(
        tmp_path,
        [
            _record("short", _ann(), svtype="DEL", end=200),
            _record("long", _ann(), svtype="DEL", end=800),
        ],
    )
    assert len({translocation_annotation_identity(row) for row in rows}) == 2
    snapshots = build_translocation_snapshot_rows(rows)
    assert len({row["simple_id_hash"] for row in snapshots}) == 2
    assert snapshots[0]["end"] in {200, 800}
    assert {row.positions for row in build_transloc_export_rows(rows)} == {
        "1:100-200 <DEL>",
        "1:100-800 <DEL>",
    }


def test_ordinary_annotations_with_more_than_two_genes_are_not_empty(tmp_path):
    rows = _parse(tmp_path, [_record("complex", _ann(gene="GENEA&GENEB&GENEC"))])
    assert rows[0]["INFO"]["ANN"]


def test_conflicting_custom_impacts_are_not_fabricated(tmp_path):
    rows = _parse(
        tmp_path,
        [
            _record(
                "left",
                _ann(feature="GENEA_ID1", effect="feature_fusion", impact="HIGH", custom=True),
                mate="right",
            ),
            _record(
                "right",
                _ann(feature="GENEB_ID2", effect="feature_fusion", impact="LOW", custom=True),
                mate="left",
                pos=200,
            ),
        ],
    )
    assert rows[0]["INFO"]["ANN"][0]["Annotation_Impact"] is None


def test_multiple_ordinary_records_without_ids_are_not_collapsed(tmp_path):
    rows = _parse(tmp_path, [_record(".", _ann()), _record(".", _ann(), pos=200)])
    assert len(rows) == 2


def test_pipeline_warnings_use_the_existing_ingest_warning_channel(tmp_path):
    path = tmp_path / "translocations.vcf"
    path.write_text(HEADER + _record("filtered", _ann(), quality="LowQual"))
    preload = DnaIngestParser().parse({"files": {"transloc": str(path)}})
    assert preload["transloc"] == []
    assert "not_pass" in preload["_warnings"][0]
