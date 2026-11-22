"""Record actors are server-owned and independent of administrative permissions."""

import pytest
from coyote.application.common.protected_records import (
    reject_system_managed_change,
    reject_system_managed_delete,
)
from coyote.application.common.record_attribution import attribute_record
from coyote.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS
from coyote.domain.exceptions import AppError


@pytest.mark.parametrize(
    "collection",
    [
        "variants",
        "cnvs",
        "translocations",
        "fusions",
        "biomarkers",
        "pgx",
        "rna_expression",
        "rna_classification",
        "rna_qc",
        "d4_coverage",
    ],
)
def test_evidence_keeps_actors_without_installation_flag(collection):
    metadata = {"created_by": "old", "updated_by": "old", "system_installed": True}
    result = attribute_record(metadata, actor="operator", collection=collection)
    assert result == {"created_by": "operator", "updated_by": "operator"}
    properties = COLLECTION_MODEL_ADAPTERS[collection].json_schema()["properties"]
    assert {"created_by", "updated_by"} <= properties.keys()
    assert "system_installed" not in properties
    assert metadata["created_by"] == "old"


@pytest.mark.parametrize(
    "collection",
    [
        "samples",
        "blacklist",
        "anno_vep",
        "sample_comments",
        "finding_comments",
        "reports",
    ],
)
def test_clinical_records_keep_authors_without_installation_ownership(collection):
    result = attribute_record(
        {"system_installed": True},
        actor="editor",
        previous={"created_by": "original", "system_installed": True},
        collection=collection,
    )
    assert result["created_by"] == "original"
    assert result["updated_by"] == "editor"
    assert "system_installed" not in result
    assert (
        "system_installed" not in COLLECTION_MODEL_ADAPTERS[collection].json_schema()["properties"]
    )


def test_import_does_not_trust_submitted_actors_or_installation_flags():
    proposed = {
        "created_by": "forged",
        "updated_by": "forged",
        "system_installed": True,
        "system_managed": True,
    }
    result = attribute_record(proposed, actor="authenticated.author")
    assert result == {
        "created_by": "authenticated.author",
        "updated_by": "authenticated.author",
        "system_installed": False,
        "system_managed": False,
    }
    assert proposed["created_by"] == "forged"


def test_edit_preserves_creator_and_records_new_actor():
    previous = {"created_by": "first.author", "updated_by": "previous.editor"}
    result = attribute_record({"created_by": "spoofed"}, actor="next.editor", previous=previous)
    assert result["created_by"] == "first.author"
    assert result["updated_by"] == "next.editor"


def test_unknown_historical_creator_is_not_replaced_with_editor():
    result = attribute_record({}, actor="editor", previous={})
    assert result["created_by"] is None
    assert result["updated_by"] == "editor"


def test_installed_catalog_is_attributed_to_system_not_operator():
    result = attribute_record({}, actor="installation.operator", system_installation=True)
    assert result["created_by"] == result["updated_by"] == "system"
    assert result["system_installed"] is True


@pytest.mark.parametrize("flag", ["system_managed", "system_installed"])
@pytest.mark.parametrize("operation", [reject_system_managed_change, reject_system_managed_delete])
def test_both_installed_flags_block_administrative_writes(flag, operation):
    with pytest.raises(AppError) as error:
        operation({flag: True}, resource="test resource")
    assert error.value.status_code == 409


def test_automated_creation_alone_does_not_disable_normal_sample_workflows():
    reject_system_managed_change(
        {"created_by": "system", "system_installed": False}, resource="sample"
    )


def test_evidence_normalization_keeps_actors_and_payload_without_installation_flag():
    from coyote.contracts.schemas.registry import normalize_collection_document

    source = {
        "SAMPLE_ID": "synthetic-sample",
        "result": {"call": "preserved"},
        "created_by": "historical",
        "updated_by": "historical",
        "system_installed": True,
    }
    result = normalize_collection_document("pgx", source)
    assert result == {
        "SAMPLE_ID": "synthetic-sample",
        "result": {"call": "preserved"},
        "created_by": "historical",
        "updated_by": "historical",
    }
    assert source["created_by"] == "historical"


def test_annotation_vault_normalization_keeps_authorship_without_installation_flag():
    from coyote.contracts.schemas.registry import normalize_collection_document

    source = {
        "simple_id": "1_100_A_G",
        "simple_id_hash": "synthetic",
        "vep_version": "103",
        "variant_class": "SNV",
        "CSQ": [],
        "created_by": "historical",
        "updated_by": "editor",
        "system_installed": True,
    }
    result = normalize_collection_document("anno_vep", source)
    assert result["created_by"] == "historical"
    assert result["updated_by"] == "editor"
    assert result["CSQ"] == []
    assert "system_installed" not in result
    assert source["system_installed"] is True


def test_annotation_retains_author_without_generic_actor_duplicates():
    from coyote.contracts.schemas.registry import normalize_collection_document

    source = {
        "variant": "p.Val600Glu",
        "nomenclature": "p",
        "gene": "BRAF",
        "hgvsp": "p.Val600Glu",
        "hgvsc": "c.1799T>A",
        "genomic": "7_140753336_A_T",
        "genomic_hash": "synthetic-hash",
        "asp_group": "synthetic",
        "diagnosis_id": "base",
        "namespace": "clinical",
        "author": "original.author",
        "text": "Synthetic annotation",
        "created_by": "duplicate",
        "updated_by": "duplicate",
        "system_installed": True,
    }
    result = normalize_collection_document("annotation", source)
    assert result["author"] == "original.author"
    assert result["text"] == source["text"]
    assert not {"created_by", "updated_by", "system_installed"} & result.keys()
    attributed = attribute_record(result, actor="importer", collection="annotation")
    assert attributed["author"] == "original.author"
    assert not {"created_by", "updated_by", "system_installed"} & attributed.keys()
    assert source["created_by"] == "duplicate"
