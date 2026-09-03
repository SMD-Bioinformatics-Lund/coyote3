"""Focused tests for bounded COSMIC finding evidence lookups."""

from types import SimpleNamespace

import mongomock

from api.infra.knowledgebase.cosmic import CosmicRepository


def _repository() -> tuple[CosmicRepository, SimpleNamespace]:
    database = mongomock.MongoClient().knowledgebase
    adapter = SimpleNamespace(
        cosmic_collection=database.cosmic,
        cosmic_noncoding_collection=database.cosmic_noncoding,
        cosmic_cna_collection=database.cosmic_cna,
        cosmic_fusion_collection=database.cosmic_fusions,
        cosmic_breakpoints_collection=database.cosmic_breakpoints,
        cosmic_cgc_hallmarks_collection=database.cosmic_cgc_hallmarks,
        cosmic_actionability_collection=database.cosmic_actionability,
    )
    return CosmicRepository(adapter), adapter


def test_variant_evidence_matches_identity_and_never_exposes_source_samples() -> None:
    repository, adapter = _repository()
    adapter.cosmic_collection.insert_one(
        {
            "id": "COSV1",
            "chr": "2",
            "start": 100,
            "ref": "A",
            "alt": "T",
            "gene": "DNMT3A",
            "hgvsp": "p.Arg1Trp",
            "cosmic_sample_id": "must-not-leave-the-repository",
        }
    )
    adapter.cosmic_cgc_hallmarks_collection.insert_one(
        {"gene_symbol": "DNMT3A", "hallmark": "epigenetic regulation"}
    )

    evidence = repository.get_variant_evidence(
        {
            "CHROM": "chr2",
            "POS": 100,
            "REF": "A",
            "ALT": "T",
            "cosmic_ids": [],
            "INFO": {"selected_CSQ": {"SYMBOL": "DNMT3A"}},
        }
    )

    assert evidence["match_count"] == 1
    assert evidence["cosmic_ids"] == ["COSV1"]
    assert evidence["records"][0]["hgvsp"] == "p.Arg1Trp"
    assert "cosmic_sample_id" not in evidence["records"][0]
    assert evidence["hallmarks"][0]["gene_symbol"] == "DNMT3A"


def test_fusion_evidence_matches_either_partner_orientation() -> None:
    repository, adapter = _repository()
    adapter.cosmic_fusion_collection.insert_many(
        [
            {
                "cosmic_fusion_id": "COSF1",
                "five_prime_gene_symbol": "NTRK1",
                "three_prime_gene_symbol": "TPM3",
                "cosmic_sample_id": "private",
            },
            {
                "cosmic_fusion_id": "COSF2",
                "five_prime_gene_symbol": "TPM3",
                "three_prime_gene_symbol": "NTRK1",
            },
        ]
    )

    evidence = repository.get_fusion_evidence({"fusion": [{"gene1": "NTRK1", "gene2": "TPM3"}]})

    assert evidence["match_count"] == 2
    assert evidence["cosmic_ids"] == ["COSF1", "COSF2"]
    assert all("cosmic_sample_id" not in row for row in evidence["records"])


def test_cnv_evidence_requires_interval_overlap() -> None:
    repository, adapter = _repository()
    adapter.cosmic_cna_collection.insert_many(
        [
            {
                "cosmic_cnv_id": "COSCNA1",
                "chromosome": "7",
                "genome_start": 100,
                "genome_stop": 200,
                "gene_symbol": "EGFR",
                "mut_type": "gain",
            },
            {
                "cosmic_cnv_id": "COSCNA2",
                "chromosome": "7",
                "genome_start": 10_000,
                "genome_stop": 20_000,
                "gene_symbol": "EGFR",
                "mut_type": "gain",
            },
        ]
    )

    evidence = repository.get_cnv_evidence(
        {"chr": "7", "start": 150, "end": 250, "genes": [{"gene": "EGFR"}]}
    )

    assert evidence["match_count"] == 1
    assert evidence["records"][0]["cosmic_ids"] == ["COSCNA1"]


def test_translocation_evidence_matches_breakpoint_ranges() -> None:
    repository, adapter = _repository()
    adapter.cosmic_breakpoints_collection.insert_one(
        {
            "cosmic_structural_id": "COSS1",
            "chrom_from": "2",
            "location_from_min": 95,
            "location_from_max": 105,
            "chrom_to": "5",
            "location_to_min": 195,
            "location_to_max": 205,
            "cosmic_sample_id": "private",
        }
    )

    evidence = repository.get_translocation_evidence({"positions": "2:100-5:200"})

    assert evidence["match_count"] == 1
    assert evidence["cosmic_ids"] == ["COSS1"]
    assert "cosmic_sample_id" not in evidence["records"][0]
