from api.infra.knowledgebase.clinpgx_public import (
    build_clinpgx_knowledge_summary,
    normalize_clinpgx_gene_row,
)


def test_normalize_clinpgx_gene_row_maps_flags_and_aliases():
    row = {
        "PharmGKB Accession Id": "PA123",
        "NCBI Gene ID": "7157",
        "HGNC ID": "HGNC:11998",
        "Ensembl Id": "ENSG00000141510",
        "Name": "tumor protein p53",
        "Symbol": "TP53",
        "Alternate Names": "p53; LFS1",
        "Alternate Symbols": "BCC7, TRP53",
        "Is VIP": "Yes",
        "Has Variant Annotation": "true",
        "Has CPIC Dosing Guideline": "No",
        "Cross-references": "HGNC:11998, NCBI Gene:7157",
        "Chromosome": "17",
        "Chromosomal Start - GRCh37": "7565097",
        "Chromosomal Stop - GRCh37": "7590856",
        "Chromosomal Start - GRCh38": "7668402",
        "Chromosomal Stop - GRCh38": "7687550",
    }

    doc = normalize_clinpgx_gene_row(
        row,
        source_file="genes.zip",
        source_reference="Human genome reference sequence = GRCh38",
        source_created="Created on 07/05/2026 at 00:37:40 PDT.",
    )

    assert doc["symbol"] == "TP53"
    assert doc["pharmgkb_accession_id"] == "PA123"
    assert doc["ncbi_gene_id"] == 7157
    assert doc["alternate_symbols"] == ["BCC7", "TRP53"]
    assert doc["alternate_names"] == ["p53", "LFS1"]
    assert doc["is_vip"] is True
    assert doc["has_variant_annotation"] is True
    assert doc["has_cpic_dosing_guideline"] is False
    assert doc["grch38_start"] == 7668402


def test_build_clinpgx_knowledge_summary_keeps_useful_api_evidence():
    summary = build_clinpgx_knowledge_summary(
        gene={
            "id": "PA124",
            "symbol": "CYP2C19",
            "name": "cytochrome P450 family 2 subfamily C member 19",
            "alleleFile": "CYP2C19_allele_definition_table.xlsx",
            "alleleFunctionSource": "CPIC",
            "alleleType": "Named Alleles",
            "buildVersion": "GRCh38.p7",
            "chr": {"name": "chr10"},
            "chrStartPosB38": 94762681,
            "chrStopPosB38": 94853205,
            "cpicGene": True,
            "amp": True,
            "pharmVarGene": True,
            "vipId": "PA166169770",
            "vipTier": "Tier 1",
            "vipSummary": {"html": "<p>CYP2C19 is a key pharmacogene.</p>"},
        },
        guidelines=[
            {
                "id": "PA1",
                "name": "Annotation of CPIC Guideline for clopidogrel and CYP2C19",
                "objCls": "Guideline Annotation",
            }
        ],
        labels=[
            {
                "id": "PA2",
                "name": "Annotation of FDA Label for clopidogrel and CYP2C19",
                "objCls": "Label Annotation",
            }
        ],
        variant_annotations=[
            {
                "accessionId": "PA3",
                "objCls": "Variant Drug Annotation",
                "sentence": "CYP2C19 poor metabolizer is associated with clopidogrel response.",
                "significance": {"term": "yes"},
            }
        ],
        chemicals=[
            {
                "connectedObject": {"objCls": "Chemical", "id": "PA449053", "name": "clopidogrel"},
                "connectionTypes": ["Guideline Annotation", "Label Annotation"],
            }
        ],
        pathways=[
            {
                "connectedObject": {
                    "objCls": "Pathway",
                    "id": "PA154424674",
                    "name": "Clopidogrel Pathway, Pharmacokinetics",
                },
                "connectionTypes": ["Pathway"],
            }
        ],
        query={"clinpgx_id": "PA124", "symbol": "CYP2C19"},
    )

    assert summary["symbol"] == "CYP2C19"
    assert summary["flags"]["cpic_gene"] is True
    assert summary["vip"]["summary"] == "CYP2C19 is a key pharmacogene."
    assert summary["counts"]["guideline_annotations"] == 1
    assert summary["counts"]["label_annotations"] == 1
    assert summary["counts"]["variant_annotations"] == 1
    assert summary["top_chemicals"][0]["name"] == "clopidogrel"
    assert summary["pathways"][0]["name"] == "Clopidogrel Pathway, Pharmacokinetics"
