"""Synthetic offline VEP builds, annotation matching and complete sample bundles."""

import sqlite3
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from bson import ObjectId

from scripts.migration_common.apply_bundle import load_bundle
from scripts.migration_common.commands import sample_bundles
from scripts.migration_common.conversion import independent_plan, sample_plan
from scripts.migration_common.offline import RecordConversionError, digest, private_json, read_json
from scripts.migration_common.schema_inventory import inventory_export
from scripts.migration_common.vep import VepReference, build_vep_reference
from tests.unit.test_legacy_migration_preflight import catalog
from tests.unit.test_offline_legacy_migrations import make_index, review, sample, variant


def consequence(feature="NM_SYNTHETIC.1", *, coding="c.1A>T", protein="p.Synthetic"):
    """Return historical synthetic transcript evidence with accession-prefixed HGVS."""
    return {
        "Feature": feature,
        "SYMBOL": "SYNTHETIC_GENE",
        "HGVSc": f"{feature}:{coding}",
        "HGVSp": f"ENSP_SYNTHETIC:{protein}",
        "Consequence": "missense_variant",
        "STRAND": 1,
    }


def source_index(
    root, version, *, consequences=None, annotation=None, release="103", genome_build=37
):
    """Build a private synthetic source with original VEP evidence and no selected call."""
    root.mkdir()
    owner = sample()
    owner["genome_build"] = genome_build
    if release:
        owner["database_versions"] = {"vep": release}
    finding = variant(owner["_id"])
    finding["INFO"]["CSQ"] = consequences or [consequence()]
    physical = "variants" if version == 3 else "variants_idref"
    records = {"samples": [owner], physical: [finding]}
    if annotation:
        records["annotation"] = [annotation]
    return make_index(root, version, records), owner, finding


def annotation():
    """Return a synthetic scoped protein annotation, preserving its original authorship."""
    return {
        "_id": ObjectId(),
        "assay": "synthetic",
        "subpanel": "base",
        "nomenclature": "p",
        "variant": "p.Synthetic",
        "gene": "SYNTHETIC_GENE",
        "transcript": "NM_SYNTHETIC.1",
        "author": "synthetic_reviewer",
        "class": 1,
        "time_created": sample()["time_added"],
    }


def test_combined_reference_deduplicates_and_unions_exact_transcripts(tmp_path):
    original = annotation()
    first, _, _ = source_index(tmp_path / "v2", 2, annotation=original)
    second, _, _ = source_index(
        tmp_path / "v3",
        3,
        consequences=[consequence(), consequence("NM_ALTERNATE.2")],
    )
    output = tmp_path / "vep"
    try:
        manifest = build_vep_reference(
            [(first, {}), (second, {})],
            output,
            version="103",
            target_sha256="synthetic-target",
            batch_size=1,
        )
        assert manifest["counts"]["source_variants"] == 2
        assert manifest["counts"]["unique_variants"] == 1
        assert manifest["counts"]["repeated_variants"] == 1
        bundle = load_bundle(output / "bundles/000001")
        assert len(bundle["anno_vep"]) == 1
        assert len(bundle["anno_vep"][0]["CSQ"]) == 2
        reference = VepReference(output)
        try:
            before = deepcopy(original)
            converted = independent_plan(first, "annotation", {}, vep=reference)["annotation"][0]
            assert converted["hgvsp"] == "p.Synthetic"
            assert converted["hgvsc"] == "c.1A>T"
            assert converted["genomic"] == "1_100_A_T"
            assert converted["transcript"] == "NM_SYNTHETIC.1"
            for key in ("_id", "author", "class", "time_created"):
                assert converted[key] == original[key]
            assert first.get("annotation", str(original["_id"])) == before
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                reference.connection.execute("DELETE FROM records")
            wrong = {**original, "transcript": "NM_SYNTHETIC.2"}
            with pytest.raises(ValueError, match="exact transcript"):
                reference.enrich(wrong)
            with pytest.raises(ValueError, match="exact transcript"):
                reference.enrich({**original, "transcript": "NM_SYNTHETIC"})
        finally:
            reference.close()
    finally:
        first.close()
        second.close()


def test_conflicting_consequences_do_not_complete_reference(tmp_path):
    first, _, _ = source_index(tmp_path / "v2", 2)
    second, _, _ = source_index(tmp_path / "v3", 3, consequences=[consequence(coding="c.2A>T")])
    try:
        output = tmp_path / "blocked"
        with pytest.raises(RecordConversionError):
            build_vep_reference(
                [(first, {}), (second, {})], output, version="103", target_sha256="target"
            )
        assert not (output / "manifest.json").exists()
        with pytest.raises((ValueError, OSError)):
            VepReference(output)
    finally:
        first.close()
        second.close()


def test_shared_vep_reference_rejects_mixed_genome_builds(tmp_path):
    """One genomic-identity vault must not combine different coordinate assemblies."""
    first, _, _ = source_index(tmp_path / "v2", 2, genome_build=37)
    second, _, _ = source_index(tmp_path / "v3", 3, genome_build=38)
    try:
        with pytest.raises(RecordConversionError):
            build_vep_reference(
                [(first, {}), (second, {})],
                tmp_path / "mixed",
                version="103",
                target_sha256="target",
            )
        assert not (tmp_path / "mixed/manifest.json").exists()
    finally:
        first.close()
        second.close()


def test_release_declaration_is_explicit_and_snapshot_bound(tmp_path):
    source, _, _ = source_index(tmp_path / "v2", 2, release=None)
    try:
        with pytest.raises(RecordConversionError):
            build_vep_reference(
                [(source, {})], tmp_path / "unknown", version="103", target_sha256="target"
            )
        evidence = {
            "vep_release": {
                "version": "103",
                "source_sha256": source.fingerprint(),
                "evidence": "Reviewed synthetic pipeline record",
            }
        }
        result = build_vep_reference(
            [(source, evidence)], tmp_path / "known", version="103", target_sha256="target"
        )
        assert result["counts"]["unique_variants"] == 1
        evidence["vep_release"]["source_sha256"] = "stale"
        with pytest.raises(ValueError, match="source digest"):
            build_vep_reference(
                [(source, evidence)], tmp_path / "stale", version="103", target_sha256="target"
            )
    finally:
        source.close()


def test_same_protein_at_multiple_genomic_positions_is_ambiguous(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    owner = sample()
    owner["genome_build"] = 37
    owner["database_versions"] = {"vep": "103"}
    first = variant(owner["_id"])
    first["INFO"]["CSQ"] = [consequence()]
    other = deepcopy(first)
    other.update(_id=ObjectId(), POS=101)
    other["INFO"]["CSQ"] = [consequence(coding="c.2A>T")]
    source = make_index(root, 2, {"samples": [owner], "variants_idref": [first, other]})
    try:
        output = tmp_path / "vep"
        build_vep_reference([(source, {})], output, version="103", target_sha256="target")
        reference = VepReference(output)
        try:
            with pytest.raises(ValueError, match="unique exact"):
                reference.enrich(annotation())
        finally:
            reference.close()
    finally:
        source.close()


@pytest.mark.parametrize("version", [2, 3])
def test_sample_extraction_keeps_embedded_rna_data_and_history(tmp_path, version):
    owner = sample()
    owner["reports"] = [
        {
            "_id": ObjectId(),
            "report_num": 1,
            "filepath": "/synthetic/report.html",
            "time_created": owner["time_added"],
        }
    ]
    owner["report_num"] = 1
    owner["comments"] = [
        {
            "_id": ObjectId(),
            "author": "synthetic",
            "text": "  original comment  ",
            "hidden": 1,
            "time_created": owner["time_added"],
        }
    ]
    for field, collection in (
        ("expr", "rna_expression"),
        ("classification", "rna_classification"),
        ("QC", "rna_qc"),
    ):
        payload = read_json(
            Path(f"tests/fixtures/collections/all_collections_dummy/{collection}.json")
        )[0]
        payload.pop("_id", None)
        payload.pop("SAMPLE_ID", None)
        owner[field] = [payload] if field == "QC" else payload
    source = make_index(tmp_path, version, {"samples": [owner]})
    try:
        plan = sample_plan(source, str(owner["_id"]), review())
        for collection in ("rna_expression", "rna_classification", "rna_qc"):
            assert len(plan[collection]) == 1
            assert plan[collection][0]["SAMPLE_ID"] == str(owner["_id"])
        assert not {"expr", "classification", "QC"} & plan["samples"][0].keys()
        assert plan["sample_comments"][0]["text"] == "  original comment  "
        assert plan["reports"][0]["_id"] == owner["reports"][0]["_id"]
        assert source.get("samples", str(owner["_id"])) == owner
    finally:
        source.close()


def test_all_samples_builds_numbered_bundles_with_completion_manifest(tmp_path):
    owner = sample()
    owner["database_versions"] = {"vep": "103"}
    target = catalog()
    aspc = target["collections"]["asp_configs"][0]
    owner["profile"] = aspc["environment"]
    root = tmp_path / "source"
    root.mkdir()
    source = make_index(root, 2, {"samples": [owner]})
    item = {"sample": {"metadata": {"current_aspc_id": aspc["_id"], "ingest_status": "ready"}}}
    reviews = {"samples": {str(owner["_id"]): item}}
    vep_output = tmp_path / "vep"
    try:
        build_vep_reference(
            [(source, {})], vep_output, version="103", target_sha256=target["sha256"]
        )
        reference = VepReference(vep_output)
        try:
            output = tmp_path / "samples"
            details = {
                "source_version": 2,
                "operation": "samples",
                "source_sha256": source.fingerprint(),
                "target_sha256": target["sha256"],
            }
            result = sample_bundles(
                source, reviews, target, output, provenance=details, vep=reference
            )
            assert result["complete"] is True
            assert result["counts"]["samples"] == 1
            assert load_bundle(output / "000001")["samples"][0]["_id"] == owner["_id"]
            assert (output / "000001/conversion.json").exists()
            selected = sample_bundles(
                source,
                reviews,
                target,
                tmp_path / "selected",
                provenance=details,
                vep=reference,
                sample_ids=[str(owner["_id"])],
            )
            assert selected["counts"]["samples"] == 1
            with pytest.raises(ValueError, match="distinct source identities"):
                sample_bundles(
                    source,
                    reviews,
                    target,
                    tmp_path / "duplicates",
                    provenance=details,
                    vep=reference,
                    sample_ids=[str(owner["_id"])] * 2,
                )
        finally:
            reference.close()
    finally:
        source.close()


def test_vep_cli_verifies_complete_source_audit_without_database_access(tmp_path, monkeypatch):
    """The documented builder accepts a reviewed complete offline source snapshot."""
    from scripts.migration_common.build_anno_vep import main

    root = tmp_path / "source"
    source, _, _ = source_index(root, 2)
    try:
        audit_path = tmp_path / "audit"
        audit = inventory_export(root / "export", audit_path, 2)
        review_path = tmp_path / "review.json"
        private_json(
            review_path,
            {
                "schema_audit": {
                    "manifest_sha256": digest(audit),
                    "reviewed_by": "synthetic_reviewer",
                    "reviewed_on": "2026-01-01",
                    "unprofiled_files": {},
                }
            },
        )
        target_path = tmp_path / "target.json"
        private_json(target_path, catalog())
        output = tmp_path / "vep"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "build_anno_vep.py",
                "--source",
                "2",
                str(root / "source.sqlite"),
                str(review_path),
                str(audit_path),
                "--vep-version",
                "103",
                "--target-catalog",
                str(target_path),
                "--output",
                str(output),
            ],
        )
        assert main() == 0
        assert read_json(output / "manifest.json")["counts"]["unique_variants"] == 1
        assert load_bundle(output / "bundles/000001")["anno_vep"][0]["vep_version"] == "103"
    finally:
        source.close()


@pytest.mark.parametrize("version", [2, 3])
def test_complete_sample_includes_every_supported_related_collection(tmp_path, version):
    """One sample migration includes structural, biomarker, coverage and history data."""
    owner = sample()
    owner["genome_build"] = 37
    owner["database_versions"] = {"vep": "103"}
    comment = {
        "_id": ObjectId(),
        "author": "synthetic",
        "text": "original",
        "time_created": owner["time_added"],
    }
    report = {
        "_id": ObjectId(),
        "report_num": 1,
        "report_id": "synthetic-report",
        "report_name": "report.html",
        "filepath": "/synthetic/report.html",
    }
    owner.update(comments=[comment], reports=[report], report_num=1)
    finding = variant(owner["_id"])
    finding["INFO"]["CSQ"] = [consequence()]
    finding["selected_csq_feature"] = "NM_SYNTHETIC.1"
    finding["simple_id"] = "1_100_A_T"
    finding["comments"] = [{**comment, "_id": ObjectId()}]
    physical = "variants" if version == 3 else "variants_idref"
    records = {"samples": [owner], physical: [finding]}
    expected = {
        "samples",
        "variants",
        "cnvs",
        "translocations",
        "biomarkers",
        "sample_comments",
        "finding_comments",
        "reports",
        "anno_vep",
    }
    for collection, source_collection in (
        ("cnvs", "cnvs" if version == 3 else "cnvs_wgs"),
        ("translocations", "transloc"),
        ("biomarkers", "biomarkers"),
    ):
        document = read_json(
            Path(f"tests/fixtures/collections/all_collections_dummy/{collection}.json")
        )[0]
        document.update(_id=ObjectId(), SAMPLE_ID=str(owner["_id"]))
        records[source_collection] = [document]
    if version == 2:
        fusion = read_json(Path("tests/fixtures/collections/all_collections_dummy/fusions.json"))[0]
        fusion.update(_id=ObjectId(), SAMPLE_ID=str(owner["_id"]))
        records["fusions"] = [fusion]
        expected.add("fusions")
    else:
        coverage = read_json(
            Path("tests/fixtures/collections/all_collections_dummy/d4_coverage.json")
        )[0]
        coverage.update(_id=ObjectId(), SAMPLE_ID=str(owner["_id"]), sample=owner["name"])
        records["panel_cov"] = [coverage]
        original_annotation = annotation()
        records["annotation"] = [original_annotation]
        records["reported_variants"] = [
            {
                "_id": ObjectId(),
                "var_oid": finding["_id"],
                "sample_oid": owner["_id"],
                "sample_name": owner["name"],
                "report_oid": report["_id"],
                "report_id": report["report_id"],
                "simple_id": finding["simple_id"],
                "tier": 2,
                "text": "Historical report wording",
                "created_by": "synthetic_reviewer",
                "created_on": owner["time_added"],
                "annotation_oid": original_annotation["_id"],
                "sample_comment_oid": comment["_id"],
            }
        ]
        expected.update({"d4_coverage", "annotation", "reported_variants"})
    source = make_index(tmp_path, version, records)
    supplied = review()
    supplied["sample"]["metadata"]["database_versions"] = {"vep": "103"}
    try:
        output = tmp_path / "vep"
        build_vep_reference([(source, {})], output, version="103", target_sha256="target")
        reference = VepReference(output)
        try:
            plan = sample_plan(source, str(owner["_id"]), supplied, vep=reference)
            assert expected <= plan.keys()
            assert all(plan[key] for key in expected)
            assert plan["reports"][0]["_id"] == report["_id"]
            assert plan["finding_comments"][0]["finding_oid"] == finding["_id"]
            if version == 3:
                assert plan["reported_variants"][0]["text"] == "Historical report wording"
                assert plan["annotation"][0]["hgvsc"] == "c.1A>T"
            assert source.get("samples", str(owner["_id"])) == owner
        finally:
            reference.close()
    finally:
        source.close()
