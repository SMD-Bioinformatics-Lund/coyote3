"""Behavioral tests for the public OncoKB Mongo cache repository."""

from __future__ import annotations

from types import SimpleNamespace

import mongomock
import pytest
from pymongo.errors import BulkWriteError

from api.infra.knowledgebase.oncokb_public_cache import (
    OncoKbPublicCacheRepository,
    _as_symbol_list,
    _merge_public_gene_records,
)


@pytest.fixture
def repository() -> OncoKbPublicCacheRepository:
    """Return a repository backed by isolated in-memory Mongo collections."""
    database = mongomock.MongoClient()["coyote3_test"]
    adapter = SimpleNamespace(
        oncokb_public_collection=database.oncokb_public,
        oncokb_genes_public_collection=database.oncokb_genes_public,
        oncokb_cancer_genes_public_collection=database.oncokb_cancer_genes_public,
    )
    return OncoKbPublicCacheRepository(adapter)


def test_symbol_list_normalization_and_public_record_merge() -> None:
    """Symbols normalize consistently and summaries retain their authoritative fields."""
    assert _as_symbol_list(None) == []
    assert _as_symbol_list(" TP53 ") == ["TP53"]
    assert _as_symbol_list("  ") == []
    assert _as_symbol_list(["TP53", "", None, " P53 "]) == ["TP53", "P53"]
    assert _as_symbol_list(17) == ["17"]

    assert _merge_public_gene_records(cancer_gene=None, gene_summary=None) is None
    merged = _merge_public_gene_records(
        cancer_gene={"gene": "TP53", "gene_type": "TSG"},
        gene_summary={"gene": "TP53", "gene_summary": "Tumour suppressor", "background": "x"},
    )
    assert merged is not None
    assert merged["gene_summary"] == "Tumour suppressor"
    assert merged["gene_type"] == "TSG"
    assert merged["public_api"] is True
    assert merged["therapeutic_data_included"] is False
    assert merged["public_gene_summary"]["background"] == "x"
    assert merged["public_cancer_gene"]["gene_type"] == "TSG"


def test_indexes_hash_lookup_counts_and_symbols(repository: OncoKbPublicCacheRepository) -> None:
    """Cache indexes and lookup helpers cover variant and gene collections."""
    repository.ensure_indexes()
    assert "query_hash_1" in repository.get_collection().index_information()
    assert repository.gene_collection.index_information()["gene_1"]["unique"] is True
    assert repository.cancer_gene_collection.index_information()["gene_1"]["unique"] is True

    repository.get_collection().insert_many(
        [{"query_hash": "a", "gene": "TP53"}, {"query_hash": "b", "gene": "KRAS"}]
    )
    assert repository.existing_query_hashes([]) == set()
    assert repository.existing_query_hashes(["a", "missing", "a", ""]) == {"a"}

    repository.gene_collection.insert_many([{"gene": "TP53"}, {"gene": "KRAS"}])
    repository.cancer_gene_collection.insert_one(
        {
            "gene": "ERBB2",
            "previous_symbols": ["HER2"],
            "alias_symbols": ["NEU"],
        }
    )
    assert repository.public_gene_count() == 2
    assert repository.public_cancer_gene_count() == 1
    assert repository.public_gene_symbols() == {"TP53", "KRAS"}
    assert repository.public_cancer_gene_symbols() == {"ERBB2", "HER2", "NEU"}


def test_annotation_insert_adds_cache_timestamps(
    repository: OncoKbPublicCacheRepository,
) -> None:
    """Annotations receive timestamps without retaining sample identity."""
    assert repository.insert_missing_annotations([]) == 0
    assert repository.insert_missing_annotations([{"query_hash": "one", "gene": "TP53"}]) == 1
    stored = repository.get_collection().find_one({"query_hash": "one"})
    assert stored is not None
    assert stored["created_on"].tzinfo is None  # mongomock stores UTC datetimes without tzinfo
    assert stored["queried_at"] is not None
    assert "sample_ids" not in stored
    assert "sample_names" not in stored


def test_annotation_insert_rejects_sample_identity(
    repository: OncoKbPublicCacheRepository,
) -> None:
    with pytest.raises(ValueError, match="cannot contain sample identity fields"):
        repository.insert_missing_annotations(
            [{"query_hash": "one", "gene": "TP53", "sample_names": ["synthetic-sample"]}]
        )


def test_duplicate_only_bulk_write_is_tolerated(
    repository: OncoKbPublicCacheRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unordered duplicate race reports only the newly inserted record count."""
    details = {"writeErrors": [{"code": 11000, "index": 0}]}

    def duplicate_insert(*_args, **_kwargs):
        raise BulkWriteError(details)

    monkeypatch.setattr(repository.get_collection(), "insert_many", duplicate_insert)
    assert repository.insert_missing_annotations([{"query_hash": "duplicate"}]) == 0

    details["writeErrors"].append({"code": 121, "index": 1})
    with pytest.raises(BulkWriteError):
        repository.insert_missing_annotations(
            [{"query_hash": "duplicate"}, {"query_hash": "invalid"}]
        )


def test_gene_marker_upserts_and_alias_lookups(repository: OncoKbPublicCacheRepository) -> None:
    """Public marker refreshes preserve one record and resolve approved and former symbols."""
    assert repository.upsert_gene_markers([{"gene": ""}]) == 0
    assert (
        repository.upsert_gene_markers(
            [
                {
                    "gene": "TP53",
                    "source": "public.api.oncokb.org",
                    "gene_summary": "Tumour suppressor",
                    "previous_symbols": ["P53"],
                    "alias_symbols": ["BCC7"],
                    "gene_exist": True,
                }
            ]
        )
        == 1
    )
    assert repository.upsert_gene_markers([{"gene": "TP53", "gene_summary": "Updated"}]) == 1

    assert repository.upsert_cancer_gene_markers([{"gene": " "}]) == 0
    assert (
        repository.upsert_cancer_gene_markers(
            [
                {
                    "gene": "TP53",
                    "gene_type": "TSG",
                    "oncokb_annotated": True,
                    "previous_symbols": ["P53"],
                    "alias_symbols": ["BCC7"],
                }
            ]
        )
        == 1
    )
    # An identical refresh is idempotent; no persisted field changes.
    assert repository.upsert_cancer_gene_markers([{"gene": "TP53", "gene_type": "TSG"}]) == 0

    assert repository.get_gene_record(None) is None
    record = repository.get_gene_record("P53")
    assert record is not None
    assert record["gene"] == "TP53"
    assert record["gene_type"] == "TSG"
    assert record["gene_summary"] == "Updated"

    records = repository.get_gene_records(["TP53", "P53", "BCC7", "", "TP53"])
    assert records["TP53"]["gene_type"] == "TSG"
    assert records["P53"]["gene"] == "TP53"
    assert records["BCC7"]["gene"] == "TP53"
    assert repository.get_gene_records([]) == {}


def test_summary_only_gene_lookup(repository: OncoKbPublicCacheRepository) -> None:
    """Curated gene summaries remain available without a cancer-gene marker."""
    repository.gene_collection.insert_one(
        {"gene": "SRSF2", "previous_symbols": ["SFRS2"], "gene_summary": "Splicing factor"}
    )
    record = repository.get_gene_record("SFRS2")
    assert record is not None
    assert record["gene_summary"] == "Splicing factor"

    records = repository.get_gene_records(["SFRS2"])
    assert records["SRSF2"]["gene_summary"] == "Splicing factor"
