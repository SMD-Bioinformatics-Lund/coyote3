"""Synthetic-only migration tests; no server connections or production fixtures."""

from copy import deepcopy
from datetime import datetime

import mongomock
import pytest
from bson import BSON, ObjectId

from scripts.migration_common.apply_bundle import apply_plan, guard_target, load_bundle
from scripts.migration_common.commands import backfill_bundle, backfill_review, configuration_plan
from scripts.migration_common.conversion import (
    independent_plan,
    prepare_finding,
    prepare_sample,
    sample_plan,
    supplement,
)
from scripts.migration_common.offline import (
    SOURCE_COLLECTIONS,
    SourceIndex,
    digest,
    prepare_source,
    read_json,
    write_bundle,
)


def make_index(tmp_path, version, records):
    """Build a local source index using exclusively synthetic BSON records."""
    export = tmp_path / "export"
    export.mkdir()
    for name in SOURCE_COLLECTIONS[version]:
        (export / f"{name}.bson").write_bytes(
            b"".join(BSON.encode(row) for row in records.get(name, []))
        )
    index = tmp_path / "source.sqlite"
    prepare_source(export, index, version)
    return SourceIndex(index, version)


def sample():
    """Return an old sample with no inferred assay or current ingestion attribution."""
    return {
        "_id": ObjectId(),
        "name": "SYNTHETIC",
        "case_id": "SYNTHETIC",
        "sample_no": 1,
        "pipeline": "synthetic",
        "time_added": datetime(2024, 1, 1),
        "profile": "testing",
        "vcf_files": "/synthetic/example.vcf.gz",
    }


def review():
    """Return explicitly reviewed destination context for a synthetic sample."""
    return {
        "sample": {
            "metadata": {
                "asp_id": "synthetic",
                "omics_layer": "dna",
                "sequencing_scope": "panel",
                "ingest_status": "ready",
                "current_aspc_id": "synthetic_aspc",
                "database_versions": {"vep": "110"},
            }
        }
    }


def variant(sample_id):
    """Return a v2 idref-shaped variant without stored transcript selection."""
    return {
        "_id": ObjectId(),
        "SAMPLE_ID": str(sample_id),
        "CHROM": 1,
        "POS": 100,
        "REF": "A",
        "ALT": "T",
        "ID": ".",
        "FILTER": "PASS",
        "GT": [],
        "INFO": {
            "CSQ": [{"Feature": "ENST_SYNTHETIC", "STRAND": 1, "Consequence": "missense_variant"}]
        },
    }


@pytest.mark.parametrize("version", [2, 3])
def test_per_sample_plan_leaves_original_index_unchanged(tmp_path, version):
    first, other = sample(), sample()
    other["name"] = "SYNTHETIC_OTHER"
    source = make_index(tmp_path, version, {"samples": [first, other]})
    before = source.fingerprint()
    plan = sample_plan(source, str(first["_id"]), review())
    assert len(plan["samples"]) == 1
    assert plan["samples"][0]["_id"] == first["_id"]
    assert plan["samples"][0]["files"]["vcf_files"]["path"] == first["vcf_files"]
    assert source.get("samples", str(first["_id"])) == first
    assert source.fingerprint() == before
    with pytest.raises(Exception, match="readonly"):
        source.connection.execute("DELETE FROM samples")
    source.close()


def test_v2_authoritative_collections_exclude_obsolete_findings():
    assert "variants_idref" in SOURCE_COLLECTIONS[2] and "cnvs_wgs" in SOURCE_COLLECTIONS[2]
    assert "variants" not in SOURCE_COLLECTIONS[2] and "cnvs" not in SOURCE_COLLECTIONS[2]
    assert not {"users", "roles", "permissions", "hpaexpr", "civic_variants"} & set(
        SOURCE_COLLECTIONS[2]
    )


def test_source_missing_files_and_wrong_version_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="incomplete"):
        prepare_source(tmp_path, tmp_path / "missing.sqlite", 2)
    source = make_index(tmp_path, 2, {})
    source.close()
    with pytest.raises(ValueError, match="another version"):
        SourceIndex(tmp_path / "source.sqlite", 3)
    with pytest.raises(FileExistsError):
        prepare_source(tmp_path / "export", tmp_path / "source.sqlite", 2)


def test_orphan_finding_blocks_index_completion(tmp_path):
    with pytest.raises(ValueError, match="orphan"):
        make_index(tmp_path, 2, {"variants_idref": [variant(ObjectId())]})
    with pytest.raises(ValueError, match="incomplete"):
        SourceIndex(tmp_path / "source.sqlite", 2)


def test_coverage_name_lookup_and_explicit_disposition(tmp_path):
    original = sample()
    coverage = {
        "_id": ObjectId(),
        "sample": original["name"],
        "chr": 1,
        "start": 1,
        "end": 10,
        "avg_cov": 100,
        "amplicon": "SYNTHETIC",
    }
    source = make_index(tmp_path, 2, {"samples": [original], "coverage": [coverage]})
    assert list(source.rows("coverage", str(original["_id"]))) == [coverage]
    with pytest.raises(ValueError, match="coverage"):
        sample_plan(source, str(original["_id"]), review())
    decision = review()
    decision["coverage"] = {
        "source_sha256": digest([coverage]),
        "action": "archive_only",
        "reason": "Synthetic archive-only coverage decision",
    }
    assert sample_plan(source, str(original["_id"]), decision)["samples"]
    source.close()


def test_v2_missing_transcript_is_never_reselected():
    source = variant(ObjectId())
    with pytest.raises(ValueError, match="historical transcript"):
        prepare_finding("variants", source)
    selected = source["INFO"]["CSQ"][0]
    additions = {
        "source_sha256": digest(source),
        "reason": "Synthetic archived selection",
        "fields": {
            "INFO.selected_CSQ": selected,
            "INFO.selected_CSQ_criteria": "archived selection",
        },
    }
    converted = prepare_finding("variants", source, additions)
    assert converted["simple_id"] == "1_100_A_T"
    assert converted["INFO"]["selected_CSQ"]["STRAND"] == "1"
    assert converted["INFO"]["selected_CSQ_criteria"] == "archived selection"
    assert "selected_CSQ" not in source["INFO"]
    additions["fields"]["INFO.selected_CSQ"] = {"Feature": "OTHER"}
    with pytest.raises(ValueError, match="not present"):
        prepare_finding("variants", source, additions)


def test_v2_related_findings_and_vep_vault(tmp_path):
    original = sample()
    row = variant(original["_id"])
    row["selected_csq_feature"] = "ENST_SYNTHETIC"
    row["INFO"]["CSQ"][0]["SYMBOL"] = "SYNTHETIC"
    row["INFO"]["CSQ"][0]["ExAC_MAF"] = "T:0.2&A:0.8"
    row["INFO"]["CSQ"][0]["gnomAD_AF"] = 0
    cnv = {
        "_id": ObjectId(),
        "SAMPLE_ID": str(original["_id"]),
        "chr": 1,
        "start": 100,
        "end": 200,
        "size": 100,
        "ratio": 0.5,
        "nprobes": 3,
        "genes": [{"gene": "SYNTHETIC", "class": "test", "cnv_type": "gain"}],
    }
    source = make_index(
        tmp_path, 2, {"samples": [original], "variants_idref": [row], "cnvs_wgs": [cnv]}
    )
    plan = sample_plan(source, str(original["_id"]), review())
    assert plan["variants"][0]["_id"] == row["_id"]
    assert plan["variants"][0]["genes"] == ["SYNTHETIC"]
    assert plan["variants"][0]["consequence_terms"] == ["missense_variant"]
    assert plan["variants"][0]["exac_frequency"] == 0.2
    assert plan["variants"][0]["gnomad_frequency"] == 0
    assert plan["variants"][0]["thousandG_frequency"] is None
    assert plan["cnvs"][0]["_id"] == cnv["_id"]
    assert plan["cnvs"][0]["ratio"] == 0.5
    assert plan["anno_vep"][0]["vep_version"] == "110"
    source.close()


def test_platform_filters_and_multiple_paths_are_not_guessed():
    original = sample()
    original["sequencing_technology"] = "legacy"
    with pytest.raises(ValueError, match="platform"):
        prepare_sample(original, {})
    original.pop("sequencing_technology")
    original["filters"] = {"min_depth": 200}
    with pytest.raises(ValueError, match="filter"):
        prepare_sample(original, {})
    original.pop("filters")
    original["vcf_files"] = ["/synthetic/a.vcf", "/synthetic/b.vcf"]
    with pytest.raises(ValueError, match="Multiple"):
        prepare_sample(original, {})
    sample_review = {
        "file_registration": {
            "source_sha256": digest({"vcf_files": original["vcf_files"]}),
            "reason": "Synthetic combined VCF manifest",
            "files": {"vcf_files": {"path": "/synthetic/combined.vcf"}},
        }
    }
    converted, _ = prepare_sample(original, sample_review)
    assert converted["files"]["vcf_files"]["path"] == "/synthetic/combined.vcf"
    assert original["vcf_files"] == ["/synthetic/a.vcf", "/synthetic/b.vcf"]


def test_msi_percentage_and_structural_genotype_names_are_preserved():
    source = {"_id": ObjectId(), "MSIS": {"tot": 100, "som": 2, "perc": 2.0}}
    assert prepare_finding("biomarkers", source)["MSIS"] == {"tot": 100, "som": 2, "per": 2.0}
    source["MSIS"]["per"] = 3.0
    with pytest.raises(ValueError, match="Conflicting"):
        prepare_finding("biomarkers", source)
    translocation = {"INFO": {"PANEL": "one|two"}, "GT": [{"_sample_id": "SYNTHETIC"}]}
    result = prepare_finding("translocations", translocation)
    assert result["GT"] == [{"sample": "SYNTHETIC"}]
    assert result["INFO"]["PANEL"] == ["one", "two"]


def test_scalar_biomarker_and_stale_supplements_are_blocked():
    with pytest.raises(ValueError, match="typed measurement"):
        prepare_finding("biomarkers", {"biomarker": "TMB", "value": 10})
    with pytest.raises(ValueError, match="matching source"):
        supplement({"_id": ObjectId()}, {"source_sha256": "bad", "reason": "review"})
    source = {"_id": ObjectId(), "value": 10}
    with pytest.raises(ValueError, match="overwrite"):
        supplement(
            source, {"source_sha256": digest(source), "reason": "review", "fields": {"value": 20}}
        )


@pytest.mark.parametrize("version", [2, 3])
def test_metadata_backfill_is_typed_missing_only_and_offline(tmp_path, version):
    original = sample()
    source = make_index(tmp_path, version, {"samples": [original]})
    tsv = tmp_path / "metadata.tsv"
    tsv.write_text(
        "sample_id\tfield\tvalue\tevidence\n"
        f"{original['_id']}\tcase.reads\t123\tsynthetic manifest\n"
        f"{original['_id']}\tcase.sequencing_run\tSYNTHETIC_RUN\tsynthetic manifest\n"
    )
    result = backfill_review(source, tsv, {})
    fields = result["samples"][str(original["_id"])]["sample"]["supplement"]["fields"]
    assert fields == {"case.reads": 123, "case.sequencing_run": "SYNTHETIC_RUN"}
    assert "case" not in source.get("samples", str(original["_id"]))
    tsv.write_text(
        "sample_id\tfield\tvalue\tevidence\n"
        f"{original['_id']}\tpipeline\tCHANGED\tsynthetic manifest\n"
    )
    with pytest.raises(ValueError, match="overwrite"):
        backfill_review(source, tsv, {})
    source.close()


@pytest.mark.parametrize(
    "field,value", [("case.reads", "-1"), ("count", "1"), ("control.reads", "1")]
)
def test_invalid_backfill_does_not_write_source(tmp_path, field, value):
    original = sample()
    source = make_index(tmp_path, 2, {"samples": [original]})
    tsv = tmp_path / "metadata.tsv"
    tsv.write_text(
        f"sample_id\tfield\tvalue\tevidence\n{original['_id']}\t{field}\t{value}\tfile\n"
    )
    with pytest.raises(ValueError):
        backfill_review(source, tsv, {})
    source.close()


def test_blacklist_is_independent_and_configuration_requires_review(tmp_path):
    original = {"_id": ObjectId(), "assay": "synthetic", "pos": "1_100", "in_normal_perc": 1.0}
    source = make_index(tmp_path, 2, {"blacklist": [original], "groups": [{"_id": "synthetic"}]})
    result = independent_plan(source, "blacklist", {})["blacklist"][0]
    assert result["assay_group"] == "synthetic" and result["pos"] == "1_100"
    with pytest.raises(ValueError, match="configuration"):
        configuration_plan(source, {})
    source.close()


def test_private_bundle_checksums_and_insert_idempotence(tmp_path, monkeypatch):
    plan = {"blacklist": [{"_id": ObjectId(), "pos": "1_100", "assay_group": "synthetic"}]}
    path = tmp_path / "bundle"
    write_bundle(path, plan, provenance={"source_version": 2})
    assert path.stat().st_mode & 0o777 == 0o700
    assert (path / "blacklist.bson").stat().st_mode & 0o777 == 0o600
    assert load_bundle(path) == plan
    target = mongomock.MongoClient().coyote4_migration_test
    monkeypatch.setattr(
        "scripts.migration_common.apply_bundle.run_transaction", lambda _, call: call(None)
    )
    assert apply_plan(target, plan)["insert_counts"] == {"blacklist": 1}
    assert target.blacklist.count_documents({}) == 0
    assert apply_plan(target, plan, apply=True)["applied"]
    assert apply_plan(target, plan)["insert_counts"] == {"blacklist": 0}
    changed = deepcopy(plan)
    changed["blacklist"][0]["pos"] = "2_200"
    with pytest.raises(ValueError, match="conflicting"):
        apply_plan(target, changed, apply=True)
    (path / "blacklist.bson").write_bytes(b"")
    with pytest.raises(ValueError, match="checksum"):
        load_bundle(path)


@pytest.mark.parametrize(
    "uri,database",
    [
        ("mongodb://localhost:28803", "coyote4_migration_test"),
        ("mongodb://host.docker.internal:28803", "coyote4_migration_test"),
        ("mongodb://remote:27017", "coyote4_migration_test"),
        ("mongodb://localhost", "coyote"),
        ("mongodb://localhost", "coyote3"),
        ("mongodb://localhost/coyote", "coyote4_migration_test"),
        ("mongodb+srv://example.invalid", "coyote4_migration_test"),
    ],
)
def test_live_endpoints_are_rejected_before_connection(uri, database):
    with pytest.raises(ValueError):
        guard_target(uri, database)


def test_explicit_local_migration_target_is_accepted():
    guard_target("mongodb://127.0.0.1:27018/?replicaSet=synthetic", "coyote4_migration_test")


def configured_target(sample_record):
    """Return an in-memory target with explicit synthetic assay scope."""
    target = mongomock.MongoClient().coyote4_migration_test
    target.assay_specific_panels.insert_one({"asp_id": sample_record["asp_id"]})
    target.asp_configs.insert_one(
        {
            "_id": sample_record["current_aspc_id"],
            "asp_id": sample_record["asp_id"],
            "asp_category": sample_record["omics_layer"],
            "environment": sample_record["environment"],
            "subpanel_id": "base",
        }
    )
    return target


@pytest.mark.parametrize("version", [2, 3])
def test_later_tsv_backfill_preserves_clinical_fields_and_is_idempotent(
    tmp_path, monkeypatch, version
):
    original = sample()
    source = make_index(tmp_path, version, {"samples": [original]})
    plan = sample_plan(source, str(original["_id"]), review())
    source.close()
    target = configured_target(plan["samples"][0])
    monkeypatch.setattr(
        "scripts.migration_common.apply_bundle.run_transaction", lambda _, call: call(None)
    )
    apply_plan(target, plan, apply=True)
    bundle = tmp_path / "original-bundle"
    write_bundle(bundle, plan, provenance={"source_version": version})
    tsv = tmp_path / "runs.tsv"
    tsv.write_text(
        f"sample_id\tfield\tvalue\tevidence\n{original['_id']}\tcase.reads\t123\tsynthetic-qc\n"
    )
    patch = tmp_path / "patch"
    backfill_bundle(bundle, tsv, patch, version)
    converted = load_bundle(patch)
    expected = read_json(patch / "manifest.json")["provenance"]["expected_samples"]
    assert apply_plan(target, converted, expected_samples=expected)["insert_counts"]["samples"] == 1
    assert "case" not in target.samples.find_one()
    apply_plan(target, converted, apply=True, expected_samples=expected)
    assert target.samples.find_one()["case"]["reads"] == 123
    assert (
        apply_plan(target, converted, apply=True, expected_samples=expected)["insert_counts"][
            "samples"
        ]
        == 0
    )
    target.samples.update_one({}, {"$set": {"reported": True}})
    with pytest.raises(ValueError, match="changed since"):
        apply_plan(target, converted, apply=True, expected_samples=expected)


def test_after_import_backfill_rejects_unrelated_fields_and_recorded_values(tmp_path):
    original = sample()
    original["case"] = {"reads": 100}
    source = make_index(tmp_path, 2, {"samples": [original]})
    plan = sample_plan(source, str(original["_id"]), review())
    source.close()
    bundle = tmp_path / "original-bundle"
    write_bundle(bundle, plan, provenance={"source_version": 2})
    tsv = tmp_path / "metadata.tsv"
    for field, value, expected in [
        ("case.reads", "200", "overwrite"),
        ("pipeline_version", "1.0", "only run"),
    ]:
        tsv.write_text(
            "sample_id\tfield\tvalue\tevidence\n"
            f"{original['_id']}\t{field}\t{value}\tsynthetic-manifest\n"
        )
        with pytest.raises(ValueError, match=expected):
            backfill_bundle(bundle, tsv, tmp_path / "patch", 2)
    assert not (tmp_path / "patch").exists()


def test_scope_mismatch_and_transaction_failure_leave_target_untouched(tmp_path, monkeypatch):
    original = sample()
    source = make_index(tmp_path, 3, {"samples": [original]})
    plan = sample_plan(source, str(original["_id"]), review())
    source.close()
    target = configured_target(plan["samples"][0])
    target.asp_configs.update_one({}, {"$set": {"environment": "production"}})
    with pytest.raises(ValueError, match="scope"):
        apply_plan(target, plan, apply=True)
    target.asp_configs.update_one({}, {"$set": {"environment": "testing"}})

    def no_transactions(_client, _callback):
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr("scripts.migration_common.apply_bundle.run_transaction", no_transactions)
    with pytest.raises(RuntimeError, match="transaction failure"):
        apply_plan(target, plan, apply=True)
    assert target.samples.count_documents({}) == 0


def test_v2_report_reference_keeps_identity_and_file_path(tmp_path):
    original = sample()
    report_id = ObjectId()
    original["reports"] = [
        {
            "_id": report_id,
            "author": "synthetic_author",
            "report_num": 1,
            "time_created": datetime(2024, 2, 1),
            "filepath": "/synthetic/report-original.html",
        }
    ]
    original["report_num"] = 1
    source = make_index(tmp_path, 2, {"samples": [original]})
    plan = sample_plan(source, str(original["_id"]), review())
    assert plan["reports"][0]["_id"] == report_id
    assert plan["reports"][0]["report_id"] == str(report_id)
    assert plan["reports"][0]["report_name"] == "report-original.html"
    assert plan["reports"][0]["filepath"] == original["reports"][0]["filepath"]
    source.close()


def test_cnv_ratio_is_not_silently_discarded():
    for value in ("unparseable", "GAIN", "NaN"):
        with pytest.raises(ValueError, match="ratio"):
            prepare_finding("cnvs", {"ratio": value})
