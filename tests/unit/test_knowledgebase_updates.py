"""Tests for manual knowledgebase snapshot update commands."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

import mongomock
import pytest

from scripts.knowledgebase_update_common import (
    CollectionSpec,
    clean_text,
    parse_float,
    parse_int,
    publish_release,
)
from scripts.update_brca_exchange import documents as brca_documents
from scripts.update_civic import gene_documents, variant_documents
from scripts.update_cosmic import tsv_documents, vcf_documents
from scripts.update_tp53_database import documents as tp53_documents


def _write(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def _tar_gzip_member(path: Path, member_name: str, value: str) -> Path:
    compressed = gzip.compress(value.encode("utf-8"))
    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo(member_name)
        info.size = len(compressed)
        archive.addfile(info, io.BytesIO(compressed))
    return path


def test_source_number_parsers_preserve_missing_values() -> None:
    assert clean_text("-") is None
    assert parse_int("") is None
    assert parse_float("NA") is None
    assert parse_int("0") == 0
    assert parse_float("0") == 0.0


def test_publish_release_replaces_collection_and_records_manifest() -> None:
    database = mongomock.MongoClient().knowledgebase
    database.civic_genes.insert_one({"gene_id": 1, "name": "OLD"})
    spec = CollectionSpec(
        name="civic_genes",
        documents=lambda: iter(({"gene_id": 2, "name": "TP53"},)),
        indexes=(((("gene_id", 1),), {"name": "gene_id_1", "unique": True}),),
    )

    report = publish_release(
        database,
        source="civic",
        release="2026-09-01",
        files=[{"name": "features.tsv", "sha256": "abc", "size_bytes": 12}],
        specs=[spec],
        drop_previous=False,
    )

    assert report["status"] == "active"
    assert database.civic_genes.find_one({"gene_id": 2})["name"] == "TP53"
    assert database.versions.find_one({"source": "civic"})["status"] == "active"
    assert any(
        name.startswith("__kb_previous__civic_genes") for name in database.list_collection_names()
    )


def test_publish_release_restores_every_collection_when_second_swap_fails(monkeypatch) -> None:
    database = mongomock.MongoClient().knowledgebase
    database.first.insert_one({"value": "old-first"})
    database.second.insert_one({"value": "old-second"})
    specs = [
        CollectionSpec("first", lambda: iter(({"value": "new-first"},)), ()),
        CollectionSpec("second", lambda: iter(({"value": "new-second"},)), ()),
    ]
    collection_type = type(database.first)
    original_rename = collection_type.rename

    def fail_second_stage(self, new_name, **kwargs):
        if self.name.startswith("__kb_stage__second"):
            raise RuntimeError("simulated publication failure")
        return original_rename(self, new_name, **kwargs)

    monkeypatch.setattr(collection_type, "rename", fail_second_stage)

    with pytest.raises(RuntimeError, match="simulated publication failure"):
        publish_release(
            database,
            source="test_source",
            release="one",
            files=[],
            specs=specs,
            drop_previous=False,
        )

    assert database.first.find_one()["value"] == "old-first"
    assert database.second.find_one()["value"] == "old-second"
    assert not any(name.startswith("__kb_stage__") for name in database.list_collection_names())
    assert database.versions.find_one({"source": "test_source"})["status"] == "failed"


def test_publish_release_uses_parallel_batch_workers() -> None:
    database = mongomock.MongoClient().knowledgebase
    spec = CollectionSpec(
        name="large_reference",
        documents=lambda: ({"record_key": str(index)} for index in range(12_001)),
        indexes=(((("record_key", 1),), {"name": "record_key_1", "unique": True}),),
    )

    report = publish_release(
        database,
        source="parallel_source",
        release="one",
        files=[],
        specs=[spec],
        drop_previous=False,
        cpus=3,
    )

    assert report["collections"][0]["documents"] == 12_001
    assert database.large_reference.count_documents({}) == 12_001
    assert database.versions.find_one({"source": "parallel_source"})["import_cpus"] == 3


def test_brca_parser_maps_both_assemblies(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "brca.tsv",
        "\t".join(
            (
                "id",
                "Chr",
                "Pos",
                "Ref",
                "Alt",
                "Genomic_Coordinate_hg38",
                "Gene_Symbol",
                "Clinical_significance_ENIGMA",
                "Clinical_significance_citations_ENIGMA",
                "Comment_on_clinical_significance_ENIGMA",
            )
        )
        + "\n1\t17\t41276045\tA\tG\t17-43124027-A-G\tBRCA1\tPathogenic\tPMID:1\treviewed\n",
    )

    document = next(brca_documents(path))

    assert document["pos"] == 41276045
    assert document["pos38"] == 43124027
    assert document["gene"] == "BRCA1"


def test_civic_parsers_support_current_feature_model(tmp_path: Path) -> None:
    feature_path = _write(
        tmp_path / "features.tsv",
        "feature_id\tfeature_civic_url\tfeature_type\tname\tfeature_aliases\tdescription\tlast_review_date\tentrez_id\n"
        "1\thttps://civicdb.org/links/features/1\tGene\tTP53\tp53\tTumor suppressor\t2026-01-01 00:00:00 UTC\t7157\n",
    )
    variant_path = _write(
        tmp_path / "variants.tsv",
        "variant_id\tvariant_civic_url\tfeature_type\tfeature_id\tfeature_name\tvariant\tvariant_types\tlast_review_date\tgene\tentrez_id\tchromosome\tstart\tstop\treference_bases\tvariant_bases\thgvs_descriptions\n"
        "2\thttps://civicdb.org/links/variants/2\tGene\t1\tTP53\tR175H\tmissense_variant\t2026-01-01 00:00:00 UTC\tTP53\t7157\t17\t7675088\t7675088\tC\tT\tNM_000546.6:c.524G>A\n",
    )

    gene = next(gene_documents(feature_path))
    variant = next(variant_documents(variant_path))

    assert gene["entrez_id"] == 7157
    assert variant["start"] == 7675088
    assert variant["hgvs_expressions"] == ["NM_000546.6:c.524G>A"]


def test_tp53_parser_does_not_invent_missing_counts(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "MutationView_r21.csv",
        "MUT_ID\tc_description\tProtDescription\tSomatic_count\tGermline_count\n"
        "1\tc.524G>A\tp.Arg175His\t12\t\n",
    )

    document = next(tp53_documents(path))

    assert document["n_somatic"] == 12
    assert "n_germline" not in document


def test_cosmic_vcf_and_tsv_stream_from_tar_without_extraction(tmp_path: Path) -> None:
    vcf_path = _tar_gzip_member(
        tmp_path / "coding.tar",
        "coding.vcf.gz",
        "##fileformat=VCFv4.1\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "17\t7675088\tCOSV1\tC\tT\t.\t.\tGENE=TP53;HGVSP=p.Arg175His;GENOME_SCREEN_SAMPLE_COUNT=8\n",
    )
    tsv_path = _tar_gzip_member(
        tmp_path / "classification.tar",
        "classification.tsv.gz",
        "COSMIC_PHENOTYPE_ID\tPRIMARY_SITE\nCOSO1\tlung\n",
    )

    variant = next(vcf_documents(vcf_path))
    classification = next(tsv_documents(tsv_path, ".tsv.gz"))

    assert variant["cnt"] == {"samples": 8}
    assert variant["gene"] == "TP53"
    assert classification["cosmic_phenotype_id"] == "COSO1"
