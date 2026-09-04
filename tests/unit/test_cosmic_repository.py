"""Focused tests for bounded COSMIC finding evidence lookups."""

from types import SimpleNamespace

import mongomock

from api.infra.knowledgebase.cosmic import CosmicRepository


def _repository() -> tuple[CosmicRepository, SimpleNamespace]:
    database = mongomock.MongoClient().knowledgebase
    adapter = SimpleNamespace(
        knowledgebase_db=database,
        cosmic_collection=database.cosmic,
        cosmic_noncoding_collection=database.cosmic_noncoding,
        cosmic_targeted_collection=database.cosmic_targeted,
        cosmic_mutation_census_collection=database.cosmic_mutation_census,
        cosmic_mutant_census_collection=database.cosmic_mutant_census,
        cosmic_cna_collection=database.cosmic_cna,
        cosmic_fusion_collection=database.cosmic_fusions,
        cosmic_breakpoints_collection=database.cosmic_breakpoints,
        cosmic_cgc_hallmarks_collection=database.cosmic_cgc_hallmarks,
        cosmic_cgc_collection=database.cosmic_cgc,
        cosmic_classification_collection=database.cosmic_classifications,
        cosmic_resistance_collection=database.cosmic_resistance,
        cosmic_actionability_collection=database.cosmic_actionability,
        cosmic_structural_collection=database.cosmic_structural,
        knowledgebase_versions_collection=database.versions,
    )
    return CosmicRepository(adapter), adapter


def test_index_setup_does_not_create_an_absent_optional_genome_collection() -> None:
    repository, adapter = _repository()

    repository.ensure_indexes()

    assert (
        adapter.cosmic_collection.name
        not in adapter.cosmic_collection.database.list_collection_names()
    )


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


def test_variant_evidence_uses_mutation_census_and_reports_product_availability() -> None:
    repository, adapter = _repository()
    adapter.cosmic_mutation_census_collection.insert_one(
        {
            "genomic_mutation_id": "COSV2",
            "chr_grch38": "17",
            "start_grch38": 7_676_154,
            "ref": "G",
            "alt": "A",
            "gene_name": "TP53",
            "mutation_aa": "p.Arg175His",
            "cosmic_sample_mutated": 120,
            "source_row": 1,
            "record_key": "cmc-1",
        }
    )
    adapter.cosmic_cgc_collection.insert_one(
        {"gene_symbol": "TP53", "tier": "1", "role_in_cancer": "TSG"}
    )
    adapter.cosmic_resistance_collection.insert_one(
        {"genomic_mutation_id": "COSV2", "drug_name": "Example drug"}
    )
    adapter.cosmic_actionability_collection.insert_one(
        {
            "genes": ["TP53"],
            "mutation_remark": "TP53_unspecified",
            "disease": "solid tumour",
        }
    )
    adapter.knowledgebase_versions_collection.insert_many(
        [
            {"source": "cosmic_mutation_census", "status": "active"},
            {"source": "cosmic_cancer_gene_census", "status": "active"},
            {"source": "cosmic_resistance_mutations", "status": "active"},
        ]
    )

    evidence = repository.get_variant_evidence(
        {
            "CHROM": "17",
            "POS": 7_676_154,
            "REF": "G",
            "ALT": "A",
            "INFO": {"selected_CSQ": {"SYMBOL": "TP53"}},
        }
    )

    assert evidence["records"][0]["source_product"] == "Mutation Census"
    assert evidence["gene_census"][0]["role_in_cancer"] == "TSG"
    assert evidence["resistance"][0]["drug_name"] == "Example drug"
    assert evidence["actionability"][0]["mutation_remark"] == "TP53_unspecified"
    assert evidence["availability"]["mutation_census"] is True
    assert evidence["availability"]["actionability"] is False


def test_cancer_gene_census_records_are_returned_as_a_gene_map() -> None:
    repository, adapter = _repository()
    adapter.cosmic_cgc_collection.insert_many(
        [
            {"gene_symbol": "TP53", "tier": "1", "role_in_cancer": "TSG"},
            {"gene_symbol": "NTRK1", "tier": "1", "role_in_cancer": "oncogene"},
        ]
    )

    records = repository.get_cancer_gene_census_records(["tp53", "NOT_CGC"])

    assert list(records) == ["TP53"]
    assert records["TP53"]["role_in_cancer"] == "TSG"


def test_cancer_gene_census_summary_is_unavailable_without_collection() -> None:
    repository, _ = _repository()

    summary = repository.get_cancer_gene_census_summary()

    assert summary["available"] is False
    assert summary["total_genes"] == 0


def test_cancer_gene_census_summary_does_not_require_hallmarks() -> None:
    repository, adapter = _repository()
    adapter.cosmic_cgc_collection.insert_one(
        {"gene_symbol": "TP53", "tier": "1", "role_in_cancer": "TSG"}
    )

    summary = repository.get_cancer_gene_census_summary()

    assert summary["available"] is True
    assert summary["total_genes"] == 1
    assert summary["hallmarks"] == []
    assert summary["hallmark_records"] == 0


def test_cancer_gene_census_summary_counts_unique_genes_and_optional_hallmarks() -> None:
    repository, adapter = _repository()
    adapter.cosmic_cgc_collection.insert_many(
        [
            {
                "gene_symbol": "TP53",
                "tier": "1",
                "somatic": "yes",
                "germline": "yes",
                "role_in_cancer": "TSG",
                "mutation_types": "Missense; Frameshift",
                "molecular_genetics": "Dominant",
            },
            {
                "gene_symbol": "NTRK1",
                "tier": "1",
                "somatic": True,
                "germline": False,
                "role_in_cancer": "oncogene",
                "mutation_types": "Fusion",
                "molecular_genetics": "Dominant",
            },
        ]
    )
    adapter.cosmic_cgc_hallmarks_collection.insert_many(
        [
            {"gene_symbol": "TP53", "hallmark": "Genome instability"},
            {"gene_symbol": "NTRK1", "impact": "Proliferative signalling"},
        ]
    )

    summary = repository.get_cancer_gene_census_summary()

    assert summary["available"] is True
    assert summary["total_genes"] == 2
    assert summary["tiers"] == [{"name": "Tier 1", "value": 2}]
    assert summary["origins"] == [
        {"name": "Somatic and germline", "value": 1},
        {"name": "Somatic only", "value": 1},
    ]
    assert summary["roles"] == [
        {"name": "Oncogene", "value": 1},
        {"name": "Tumour suppressor", "value": 1},
    ]
    assert summary["molecular_genetics"] == [{"name": "Dominant", "value": 2}]
    assert summary["hallmark_records"] == 2


def test_fusion_evidence_matches_either_partner_orientation() -> None:
    repository, adapter = _repository()
    adapter.cosmic_fusion_collection.insert_many(
        [
            {
                "cosmic_fusion_id": "COSF1",
                "cosmic_phenotype_id": "COSO1",
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
    adapter.cosmic_classification_collection.insert_one(
        {
            "cosmic_phenotype_id": "COSO1",
            "primary_site": "soft tissue",
            "primary_histology": "sarcoma",
        }
    )

    evidence = repository.get_fusion_evidence({"fusion": [{"gene1": "NTRK1", "gene2": "TPM3"}]})

    assert evidence["match_count"] == 2
    assert evidence["cosmic_ids"] == ["COSF1", "COSF2"]
    assert all("cosmic_sample_id" not in row for row in evidence["records"])
    assert evidence["classifications"][0]["primary_histology"] == "sarcoma"


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
