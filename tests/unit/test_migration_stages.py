"""Synthetic reference prerequisites and assay-by-assay migration stages."""

from copy import deepcopy
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId

from scripts.migration_common.apply_bundle import load_bundle
from scripts.migration_common.commands import sample_bundles
from scripts.migration_common.offline import digest, private_json, read_json
from scripts.migration_common.prepare_references import (
    reference_snapshot,
    verify_reference_snapshot,
)
from scripts.migration_common.sample_scope import (
    ASSAY_SOURCES,
    matches_assay,
    prepare_scope,
    sample_assay,
    validate_assay,
)
from scripts.migration_common.vep import VepReference, build_vep_reference
from tests.unit.test_legacy_migration_preflight import catalog
from tests.unit.test_migration_vep_reference import consequence
from tests.unit.test_offline_legacy_migrations import make_index, sample, variant


def references():
    """Validate synthetic current reference fixtures in an in-memory MongoDB substitute."""
    database = mongomock.MongoClient().coyote4_migration_knowledgebase
    root = Path("tests/fixtures/collections/all_collections_dummy")
    for name in ("vep_metadata", "hgnc_genes"):
        row = read_json(root / f"{name}.json")[0]
        row["_id"] = ObjectId()
        if name == "vep_metadata":
            row["vep_id"] = "103"
        database[name].insert_one(row)
    return reference_snapshot(database, "103")


def test_reference_prerequisites_are_nonempty_valid_and_release_specific(tmp_path):
    """Missing collections, absent release and altered snapshots cannot pass the gate."""
    database = mongomock.MongoClient().coyote4_migration_knowledgebase
    with pytest.raises(ValueError, match="nonempty"):
        reference_snapshot(database, "103")
    snapshot = references()
    path = tmp_path / "references.json"
    private_json(path, snapshot)
    assert verify_reference_snapshot(path, "103") == snapshot
    with pytest.raises(ValueError, match="preflight"):
        verify_reference_snapshot(path, "104")
    snapshot["collections"]["hgnc_genes"]["count"] = 0
    other = tmp_path / "altered.json"
    private_json(other, snapshot)
    with pytest.raises(ValueError, match="preflight"):
        verify_reference_snapshot(other, "103")


@pytest.mark.parametrize("assay_id,version", ASSAY_SOURCES.items())
def test_supported_assays_have_one_authoritative_source(assay_id, version):
    """Every operator-supplied assay selects exactly one historical database version."""
    assert validate_assay(assay_id.upper(), version) == assay_id
    with pytest.raises(ValueError, match="designated source"):
        validate_assay(assay_id, 2 if version == 3 else 3)


def test_tumwgs_selection_uses_recorded_subpanel():
    """Tumwgs hema and solid remain separate ASPs with their recorded diagnosis scopes."""
    assert sample_assay({"group": "tumwgs", "subpanel": "hema"}, "group") == "tumwgs-hema"
    assert sample_assay({"group": "tumwgs", "subpanel": "solid"}, "group") == "tumwgs-solid"
    with pytest.raises(ValueError, match="subpanel"):
        sample_assay({"group": "tumwgs", "subpanel": "unknown"}, "group")
    assert not matches_assay({"group": "tumwgs"}, "group", "hema_gmsv1")
    assert not matches_assay({"group": "tumwgs", "subpanel": "solid"}, "group", "tumwgs-hema")


def test_sample_diagnosis_must_agree_with_selected_aspc():
    """A current default diagnosis must not replace the recorded historical subpanel."""
    original = {"_id": ObjectId(), "group": "tumwgs", "subpanel": "hema"}
    metadata = {"asp_id": "tumwgs-hema", "asp_group": "hematology", "diagnosis_id": "hema"}
    mapped = prepare_scope(original, metadata, assay_id="tumwgs-hema", field="group")
    assert mapped["_id"] == original["_id"]
    assert mapped["diagnosis_id"] == "hema"
    metadata["diagnosis_id"] = "base"
    with pytest.raises(ValueError, match="recorded subpanel"):
        prepare_scope(original, metadata, assay_id="tumwgs-hema", field="group")


def test_annotation_filter_selects_one_mapped_asp(tmp_path):
    """A per-ASP annotation run still enforces the v2/v3 group ownership split."""
    from scripts.migration_common.conversion import independent_plan
    from tests.unit.test_migration_annotation_scope_mapping import annotation

    included = annotation("myeloid", "base")
    excluded = annotation("solid", "BC")
    hematology = annotation("hematology", "base")
    source = make_index(tmp_path, 2, {"annotation": [included, excluded, hematology]})
    try:
        rows = independent_plan(source, "annotation", {}, assay_id="myeloid_gmsv1")["annotation"]
        assert [row["_id"] for row in rows] == [included["_id"]]
    finally:
        source.close()


@pytest.mark.parametrize("version,assay_id", [(3, "hema_gmsv1"), (2, "myeloid_gmsv1")])
@pytest.mark.parametrize("assay_field", ["group", "assay"])
def test_findings_then_samples_keep_original_id_and_omit_annotations(
    tmp_path, version, assay_id, assay_field
):
    """Assay selection produces separate findings/sample bundles without early annotations."""
    owner = sample()
    owner.update(subpanel="BASE", profile="production", genome_build=37)
    owner[assay_field] = assay_id.upper()
    owner["database_versions"] = {"vep": "103"}
    unselected = deepcopy(owner)
    unselected.update(_id=ObjectId(), name="SYNTHETIC_OTHER")
    unselected[assay_field] = "not-selected"
    finding = variant(owner["_id"])
    finding["INFO"]["CSQ"] = [consequence()]
    finding["selected_csq_feature"] = "NM_SYNTHETIC.1"
    finding["simple_id"] = "1_100_A_T"
    source = make_index(
        tmp_path,
        version,
        {
            "samples": [owner, unselected],
            "variants" if version == 3 else "variants_idref": [finding],
            "annotation": [{"_id": ObjectId(), "assay": "unselected"}],
        },
    )
    target = catalog()
    records = target["collections"]
    asp = records["assay_specific_panels"][0]
    asp["asp_id"] = assay_id
    aspc = records["asp_configs"][0]
    aspc.update(asp_id=assay_id, diagnosis_id="base")
    target["sha256"] = digest(records)
    review = {
        "samples": {
            str(owner["_id"]): {
                "sample": {"metadata": {"current_aspc_id": aspc["_id"], "ingest_status": "ready"}}
            }
        }
    }
    try:
        vep_dir = tmp_path / "vep"
        build_vep_reference(
            [(source, {})],
            vep_dir,
            version="103",
            target_sha256=target["sha256"],
            references=references(),
        )
        reference = VepReference(vep_dir)
        try:
            for stage in ("findings", "samples"):
                output = tmp_path / stage
                manifest = sample_bundles(
                    source,
                    review,
                    target,
                    output,
                    provenance={"source_version": version, "operation": "samples"},
                    vep=reference,
                    assay_id=assay_id,
                    assay_field=assay_field,
                    stage=stage,
                )
                assert len(manifest["samples"]) == 1
                plan = load_bundle(output / "000001")
                assert "annotation" not in plan
                if stage == "findings":
                    assert "samples" not in plan
                    assert plan["variants"][0]["_id"] == finding["_id"]
                    assert plan["variants"][0]["SAMPLE_ID"] == str(owner["_id"])
                    assert plan["anno_vep"]
                else:
                    assert "variants" not in plan
                    migrated = plan["samples"][0]
                    assert migrated["_id"] == owner["_id"]
                    assert migrated["asp_id"] == assay_id
                    assert migrated["asp_group"] == asp["asp_group"]
                    assert migrated["diagnosis_id"] == "base"
                    assert "group" not in migrated and "subpanel" not in migrated
            assert source.get("samples", str(owner["_id"])) == owner
        finally:
            reference.close()
    finally:
        source.close()
