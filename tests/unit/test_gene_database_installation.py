"""Verify gene conversion and scoped installation using synthetic inputs only."""

import copy
import csv
import sys

import mongomock
import pytest
from bson import decode_all

from api.config.loaders.collections import load_collection_section
from scripts import gene_db_creation
from scripts.gene_db_creation import HGNC_FIELDS, build_genes, convert, read_rows


@pytest.fixture
def inputs():
    """Supply a synthetic gene with two MANE Plus Clinical transcripts."""
    gene = dict(
        hgnc_id="HGNC:999999",
        hgnc_symbol="DEMO",
        gene_name="Demo gene",
        status="Approved",
        locus="1p1",
        locus_sortable="1p1",
        entrez_id=999999,
        ensembl_gene_id="ENSG_DEMO",
        ensembl_mane_select="ENST_DEMO.1",
        refseq_mane_select="NM_DEMO.1",
    )
    row = dict(
        hgnc_id=gene["hgnc_id"],
        hgnc_symbol="DEMO",
        chromosome="1",
        start=100,
        end=300,
        gene_gc_content=40.0,
        gene_description="Demo [Source:HGNC]",
        ensembl_canonical=False,
        gene_type="protein_coding",
        refseq_mane_select="NM_DEMO.1",
        refseq_mane_plus_clinical=["NM_PLUS1.1", "NM_PLUS2.1"],
        transcript_start=110,
        transcript_end=290,
        transcript_length=100,
        transcription_start_site=110,
    )
    return [gene], [row]


def test_transcript_merge_is_order_independent_and_retains_plus_clinical(inputs):
    genes, rows = inputs
    second = dict(rows[0], ensembl_canonical=True)
    document = build_genes(genes, rows + [second])[0]
    assert document == build_genes(genes, [second] + rows)[0]
    assert document["ensembl_canonical"] is True
    assert set(document["addtional_transcript_info"]) == {"NM_DEMO.1", "NM_PLUS1.1", "NM_PLUS2.1"}
    assert convert("0", bool, None) is False
    assert convert("false", bool, None) is False
    with pytest.raises(ValueError):
        convert("unknown", bool, None)


@pytest.mark.parametrize(
    "problem", ["missing", "duplicate", "chromosome", "coordinates", "bounds", "symbol"]
)
def test_invalid_input_is_rejected(inputs, problem):
    genes, rows = copy.deepcopy(inputs)
    if problem == "missing":
        rows = []
    elif problem == "duplicate":
        genes += genes
    elif problem == "chromosome":
        rows.append(dict(rows[0], chromosome="2"))
    elif problem == "coordinates":
        rows.append(dict(rows[0], start=101))
    elif problem == "bounds":
        rows[0]["transcript_length"] = None
    else:
        rows[0]["hgnc_symbol"] = "OTHER"
    with pytest.raises(ValueError):
        build_genes(genes, rows)


def test_headers_and_metadata_skip_are_explicit(tmp_path):
    source = tmp_path / "genes.tsv"
    source.write_text("metadata\nhgnc_id\tsymbol\nHGNC:999999\tDEMO\n")
    assert read_rows(source, HGNC_FIELDS, "\t", 1)[0]["hgnc_symbol"] == "DEMO"
    with pytest.raises(ValueError, match="header"):
        read_rows(source, HGNC_FIELDS, "\t")
    source.write_text("hgnc_id\thgnc_id\n1\t1\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_rows(source, HGNC_FIELDS, "\t")


def test_scoped_install_preserves_unrelated_records_and_backs_up(inputs, tmp_path, monkeypatch):
    database = mongomock.MongoClient().knowledgebase
    documents = build_genes(*inputs)
    previous = dict(documents[0], _id="existing-id", gene_name="Previous")
    database.hgnc_genes.insert_one(previous)
    database.hgnc_genes.insert_one({"_id": "unrelated", "hgnc_id": "HGNC:OTHER"})
    monkeypatch.setattr(
        gene_db_creation, "run_transaction", lambda client, callback: callback(None)
    )
    backup = tmp_path / "backup.bson"
    gene_db_creation.install_genes(database, documents, backup, {"release": "demo"})
    assert decode_all(backup.read_bytes()) == [previous]
    assert database.hgnc_genes.find_one({"_id": "existing-id"})["gene_name"] == "Demo gene"
    assert database.hgnc_genes.find_one({"_id": "unrelated"})
    versions = load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
    assert database[versions].find_one({"source": "hgnc_genes"})
    with pytest.raises(FileExistsError):
        gene_db_creation.install_genes(database, documents, backup, {"release": "demo"})


def test_concurrent_change_stops_publication(inputs, tmp_path, monkeypatch):
    database = mongomock.MongoClient().knowledgebase
    documents = build_genes(*inputs)

    def concurrent_write(client, callback):
        database.hgnc_genes.insert_one(documents[0])
        callback(None)

    monkeypatch.setattr(gene_db_creation, "run_transaction", concurrent_write)
    with pytest.raises(RuntimeError, match="changed after backup"):
        gene_db_creation.install_genes(
            database, documents, tmp_path / "backup.bson", {"release": "demo"}
        )
    versions = load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
    assert database[versions].count_documents({}) == 0


def test_cli_review_does_not_connect_to_mongo(inputs, tmp_path, monkeypatch):
    """The complete standalone conversion defaults to filesystem-only validation."""
    genes, rows = inputs
    paths = []
    for filename, mapping, source, delimiter in (
        ("hgnc.tsv", gene_db_creation.HGNC_FIELDS, genes[0], "\t"),
        ("biomart.csv", gene_db_creation.BIOMART_FIELDS, rows[0], ","),
    ):
        path = tmp_path / filename
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream, delimiter=delimiter)
            columns = [key for key, (target, _, _) in mapping.items() if target in source]
            writer.writerow(columns)
            writer.writerow(
                [
                    "|".join(source[mapping[key][0]])
                    if isinstance(source[mapping[key][0]], list)
                    else source[mapping[key][0]]
                    for key in columns
                ]
            )
        paths.append(path)
    output = tmp_path / "review.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gene_db_creation.py",
            "--hgnc",
            str(paths[0]),
            "--biomart",
            str(paths[1]),
            "--output",
            str(output),
            "--release",
            "synthetic",
            "--assembly",
            "GRCh38",
        ],
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Review must not connect to MongoDB")

    monkeypatch.setattr(gene_db_creation, "MongoClient", forbidden)
    assert gene_db_creation.main() == 0
    assert '"hgnc_id": "HGNC:999999"' in output.read_text()
    assert '"sha256"' in output.read_text()
