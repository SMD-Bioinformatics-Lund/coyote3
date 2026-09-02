"""Unit tests for internal ingestion service helpers and orchestration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import api.application.ingest.helpers as ingest_helpers
import api.application.ingest.parsers as ingest_parsers
import api.application.ingest.sample_updates as sample_updates
import api.application.ingest.service as ingest
from api.contracts.schemas.rna import FusionsDoc
from api.domain.core.dna.transcript_payloads import (
    annotate_transcript_provenance,
    compact_selected_csq,
    feature_without_version,
)
from api.infra.mongo.ingest_gateway import IngestCollectionGateway


class _Col:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted_one = []
        self.inserted_many = []
        self.deleted = []
        self.updated = []

    def find(self, query=None, projection=None):
        _ = projection
        query = query or {}
        if "_id" in query:
            needle = query["_id"]
            return [d for d in self.docs if d.get("_id") == needle]
        if "name" in query and isinstance(query["name"], str):
            needle = query["name"]
            return [d for d in self.docs if d.get("name") == needle]
        if "name" in query and isinstance(query["name"], dict):
            needle = query["name"].get("$regex", "")
            return [d for d in self.docs if needle in d.get("name", "")]
        if "SAMPLE_ID" in query:
            needle = query["SAMPLE_ID"]
            return [d for d in self.docs if d.get("SAMPLE_ID") == needle]
        return list(self.docs)

    def find_one(self, query):
        if "asp_id" in query:
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items()):
                    return doc
            return None
        for doc in self.find(query):
            return doc
        return None

    def insert_one(self, doc):
        self.inserted_one.append(doc)
        self.docs.append(doc)
        return SimpleNamespace(inserted_id="oid1")

    def insert_many(self, docs, ordered=True):
        _ = ordered
        self.inserted_many.append(list(docs))
        self.docs.extend(docs)
        return SimpleNamespace(inserted_ids=["oid" for _ in docs])

    def delete_many(self, query):
        self.deleted.append(query)

    def delete_one(self, query):
        self.deleted.append(query)

    def update_one(self, query, update, upsert=False):
        self.updated.append((query, update, upsert))

    def replace_one(self, filter, replacement, upsert=False):
        self.updated.append((filter, replacement, upsert))
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

    def estimated_document_count(self):
        return len(self.docs)


class _Handler:
    def __init__(self, col):
        self._col = col

    def get_collection(self):
        return self._col


class _AnnoVepRepo:
    def __init__(self):
        self.docs = []

    def upsert_many(self, docs, session=None):
        _ = session
        self.docs.extend(list(docs))


def _store_stub(sample_docs=None):
    sample_col = _Col(sample_docs)
    db = {
        "variants": _Col(),
        "cnvs": _Col(),
        "biomarkers": _Col(),
        "transloc": _Col(),
        "panel_coverage": _Col(),
        "group_coverage": _Col(),
        "fusions": _Col(),
        "rna_expression": _Col(),
        "rna_classification": _Col(),
        "rna_qc": _Col(),
        "asp_configs": _Col(
            [
                {
                    "_id": "aspc-1",
                    "aspc_id": "assay_1:production:base",
                    "asp_id": "assay_1",
                    "subpanel_id": "Hem",
                    "environment": "production",
                    "is_active": True,
                    "analysis_types": [],
                    "filters": {},
                },
                {
                    "_id": "aspc-a",
                    "aspc_id": "A:production:base",
                    "asp_id": "A",
                    "subpanel_id": "base",
                    "environment": "production",
                    "is_active": True,
                    "analysis_types": [],
                    "filters": {},
                },
            ]
        ),
        "assay_specific_panels": _Col(
            [
                {
                    "asp_id": "assay_1",
                    "assay_name": "assay_1",
                    "asp_group": "hematology",
                    "asp_family": "panel-dna",
                    "asp_category": "dna",
                    "display_name": "Assay 1",
                    "expected_files": [
                        "vcf_files",
                        "cnv",
                        "cov",
                        "cnvprofile",
                        "transloc",
                        "biomarkers",
                    ],
                    "required_files": ["vcf_files"],
                },
                {
                    "asp_id": "A",
                    "assay_name": "A",
                    "asp_group": "hematology",
                    "asp_family": "panel-dna",
                    "asp_category": "dna",
                    "display_name": "Assay A",
                    "expected_files": [
                        "vcf_files",
                        "cnv",
                        "cov",
                        "cnvprofile",
                        "transloc",
                        "biomarkers",
                    ],
                    "required_files": ["vcf_files"],
                },
            ]
        ),
        "hgnc_genes": _Col(),
        "anno_vep": _Col(),
    }
    anno_vep_repository = _AnnoVepRepo()
    return SimpleNamespace(
        sample_repository=_Handler(sample_col),
        variant_repository=_Handler(db["variants"]),
        copy_number_variant_repository=_Handler(db["cnvs"]),
        biomarker_repository=_Handler(db["biomarkers"]),
        translocation_repository=_Handler(db["transloc"]),
        coverage_repository=_Handler(db["panel_coverage"]),
        grouped_coverage_repository=_Handler(db["group_coverage"]),
        fusion_repository=_Handler(db["fusions"]),
        rna_expression_repository=_Handler(db["rna_expression"]),
        rna_classification_repository=_Handler(db["rna_classification"]),
        rna_quality_repository=_Handler(db["rna_qc"]),
        anno_vep_repository=anno_vep_repository,
        coyote_db=db,
    )


def _use_store(monkeypatch, store_stub, *, new_sample_id="507f1f77bcf86cd799439011"):
    monkeypatch.setattr(ingest, "_provider_sample_id", lambda sample_id: sample_id)
    monkeypatch.setattr(ingest, "_new_sample_id", lambda: new_sample_id)
    return ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            collections={
                "samples": store_stub.sample_repository.get_collection(),
                "variants": store_stub.variant_repository.get_collection(),
                "cnvs": store_stub.copy_number_variant_repository.get_collection(),
                "biomarkers": store_stub.biomarker_repository.get_collection(),
                "translocations": store_stub.translocation_repository.get_collection(),
                "panel_coverage": store_stub.coverage_repository.get_collection(),
                "fusions": store_stub.fusion_repository.get_collection(),
                "rna_expression": store_stub.rna_expression_repository.get_collection(),
                "rna_classification": store_stub.rna_classification_repository.get_collection(),
                "rna_qc": store_stub.rna_quality_repository.get_collection(),
                "asp_configs": store_stub.coyote_db["asp_configs"],
                "assay_specific_panels": store_stub.coyote_db["assay_specific_panels"],
                "hgnc_genes": store_stub.coyote_db["hgnc_genes"],
                "anno_vep": store_stub.coyote_db["anno_vep"],
            }
        ),
        anno_vep_repository=store_stub.anno_vep_repository,
        invalidate_dashboard_summary=lambda: None,
    )


def test_collection_document_count_reports_supported_collection_occupancy(monkeypatch):
    store_stub = _store_stub(sample_docs=[{"_id": "sample-1", "name": "sample_one"}])
    service = _use_store(monkeypatch, store_stub)

    assert service.collection_document_count("samples") == 1
    assert service.collection_document_count("variants") == 0

    with pytest.raises(ValueError, match="Unsupported collection"):
        service.collection_document_count("not_a_collection")


def test_small_helpers_and_build_meta(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    assert ingest_parsers._exists(str(p))
    ingest_parsers.require_exists("A", str(p))
    with pytest.raises(FileNotFoundError):
        ingest_parsers.require_exists("A", str(tmp_path / "missing"))

    assert (
        ingest_parsers.runtime_file_path({"vcf_files": "/tmp/a.vcf"}, "vcf_files") == "/tmp/a.vcf"
    )
    assert (
        ingest_parsers.runtime_file_path(
            {"vcf_files": "/tmp/a.vcf", "_runtime_files": {"vcf_files": "/staged/a.vcf"}},
            "vcf_files",
        )
        == "/staged/a.vcf"
    )

    norm_case, norm_ctrl = ingest_helpers.normalize_case_control(
        {
            "case_id": "C1",
            "control_id": "N1",
            "case_reads": "null",
            "control_reads": None,
            "case_ffpe": False,
            "control_ffpe": True,
        }
    )
    assert "reads" not in norm_case
    assert "reads" not in norm_ctrl
    assert norm_case["ffpe"] is False
    assert norm_ctrl["ffpe"] is True

    meta = ingest.build_sample_meta_dict(
        {
            "name": "S1",
            "sex": "female",
            "case_id": "C1",
            "control_id": "N1",
            "database_versions": {
                "clinvar": "202402",
                "dbsnp": 154,
                "vep": "v110",
            },
            "case_reads": 10,
            "control_reads": 20,
            "increment": True,
        }
    )
    assert "increment" not in meta
    assert meta["database_versions"] == {"clinvar": "202402", "dbsnp": "154", "vep": "110"}
    assert meta["sex"] == "female"
    assert meta["case"]["reads"] == 10
    assert meta["control"]["reads"] == 20


def test_sample_meta_omits_unknown_ffpe_and_uses_contract_default():
    payload = {
        "name": "RNA1",
        "asp_id": "fusion",
        "subpanel_id": "base",
        "environment": "production",
        "case_id": "RNA1",
        "sample_no": 1,
        "paired": False,
        "sequencing_scope": "wts",
        "omics_layer": "rna",
        "platform": "illumina",
        "pipeline": "rnaseq_fusion",
        "pipeline_version": "not_provided",
        "fusion_files": "/data/fusions.json",
        "genome_build": None,
        "case_ffpe": None,
        "case_sequencing_run": None,
        "case_reads": None,
        "case_purity": None,
    }

    validated = ingest.SamplesDoc.model_validate(payload).model_dump(exclude_none=True)
    assert "pipeline_version" not in validated
    meta = ingest.build_sample_meta_dict(validated)

    assert meta["case"] == {"id": "RNA1"}
    final_sample = ingest.SamplesDoc.model_validate(meta)
    assert final_sample.case.ffpe is False
    assert final_sample.case.sequencing_run is None
    assert final_sample.case.reads is None
    assert final_sample.case.purity is None


def test_dna_parser_loads_nested_sample_file_docs(tmp_path, monkeypatch):
    cnv_path = tmp_path / "sample.cnv.json"
    biomarker_path = tmp_path / "sample.bio.json"
    transloc_path = tmp_path / "sample.transloc.vcf"
    cov_path = tmp_path / "sample.cov.json"
    cnv_path.write_text(
        json.dumps(
            {
                "cnv-1": {
                    "chr": "1",
                    "start": 10,
                    "end": 20,
                    "size": 10,
                    "ratio": 0.5,
                    "genes": [{"gene": "TP53", "class": 1}],
                }
            }
        ),
        encoding="utf-8",
    )
    biomarker_path.write_text(json.dumps({"name": "S1"}), encoding="utf-8")
    transloc_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    cov_path.write_text(json.dumps({"genes": {}}), encoding="utf-8")

    monkeypatch.setattr(
        ingest_parsers.DnaIngestParser,
        "_parse_transloc_only",
        staticmethod(lambda _path: [{"CHROM": "1", "POS": 1}]),
    )

    parser = ingest_parsers.DnaIngestParser()
    preload = parser.parse(
        {
            "omics_layer": "dna",
            "files": {
                "cnv": {"path": str(cnv_path)},
                "biomarkers": {"path": str(biomarker_path)},
                "transloc": {"path": str(transloc_path)},
                "cov": {"path": str(cov_path)},
            },
        }
    )

    assert set(preload) == {"cnvs", "biomarkers", "transloc", "cov"}
    assert preload["cnvs"][0]["chr"] == "1"
    assert preload["biomarkers"]["name"] == "S1"
    assert preload["transloc"] == [{"CHROM": "1", "POS": 1}]
    assert preload["cov"] == {"genes": {}}


def test_select_csq_prefers_hgnc_mane_plus_and_current_symbol():
    csq_arr = [
        {
            "Feature": "NM_000002.1",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "OLD1",
            "IMPACT": "MODERATE",
            "CANONICAL": "YES",
            "BIOTYPE": "protein_coding",
            "MANE": "NM_000002.1",
            "MANE_PLUS_CLINICAL": "",
        },
        {
            "Feature": "NM_000001.1",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "OLD1",
            "IMPACT": "MODERATE",
            "CANONICAL": "",
            "BIOTYPE": "protein_coding",
            "MANE": "",
            "MANE_PLUS_CLINICAL": "NM_000001.1",
        },
    ]
    hgnc_doc = {
        "hgnc_id": "HGNC:1",
        "hgnc_symbol": "NEW1",
        "prev_symbol": ["OLD1"],
        "alias_symbol": [],
        "refseq_mane_select": "NM_000002.1",
        "ensembl_mane_select": "ENST000002",
        "refseq_mane_plus_clinical": ["NM_000001.1"],
    }

    selected, source = ingest_parsers._select_csq(
        csq_arr,
        hgnc_by_id={"HGNC:1": hgnc_doc},
        hgnc_by_symbol={"OLD1": hgnc_doc, "NEW1": hgnc_doc},
    )

    assert source == "ncbi_mane_plus_clinical"
    assert selected["Feature"] == "NM_000001.1"
    assert selected["SYMBOL"] == "NEW1"
    assert selected["HGNC_ID"] == "HGNC:1"


def test_select_csq_uses_explicit_ncbi_then_ensembl_mane_priority():
    hgnc_doc = {
        "hgnc_id": "HGNC:1",
        "hgnc_symbol": "GENE1",
        "refseq_mane_plus_clinical": ["NM_PLUS.1"],
        "ensembl_mane_plus_clinical": ["ENST_PLUS.1"],
        "refseq_mane_select": "NM_SELECT.1",
        "ensembl_mane_select": "ENST_SELECT.1",
    }
    by_id = {"HGNC:1": hgnc_doc}
    rows = [
        {"Feature": "ENST_SELECT.1", "HGNC_ID": "HGNC:1", "IMPACT": "HIGH"},
        {"Feature": "NM_SELECT.1", "HGNC_ID": "HGNC:1", "IMPACT": "HIGH"},
        {
            "Feature": "ENST_PLUS.1",
            "HGNC_ID": "HGNC:1",
            "IMPACT": "LOW",
            "MANE_PLUS_CLINICAL": "NM_PLUS.1",
        },
        {"Feature": "NM_PLUS.1", "HGNC_ID": "HGNC:1", "IMPACT": "LOW"},
    ]

    selected, source = ingest_parsers._select_csq(rows, hgnc_by_id=by_id)
    assert (selected["Feature"], source) == ("NM_PLUS.1", "ncbi_mane_plus_clinical")

    selected, source = ingest_parsers._select_csq(rows[:-1], hgnc_by_id=by_id)
    assert (selected["Feature"], source) == (
        "ENST_PLUS.1",
        "ensembl_mane_plus_clinical",
    )

    selected, source = ingest_parsers._select_csq(rows[:2], hgnc_by_id=by_id)
    assert (selected["Feature"], source) == ("NM_SELECT.1", "ncbi_mane_select")

    selected, source = ingest_parsers._select_csq(rows[:1], hgnc_by_id=by_id)
    assert (selected["Feature"], source) == ("ENST_SELECT.1", "ensembl_mane_select")


def test_annotate_transcript_provenance_from_hgnc_and_vep_metadata():
    hgnc_doc = {
        "hgnc_id": "HGNC:1",
        "hgnc_symbol": "NEW1",
        "prev_symbol": ["OLD1"],
        "alias_symbol": [],
        "refseq_mane_select": "NM_000002.1",
        "ensembl_mane_select": "ENST000002.3",
        "refseq_mane_plus_clinical": ["NM_000001.1"],
    }
    rows = [
        {
            "Feature": "NM_000001.1",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "OLD1",
            "MANE_PLUS_CLINICAL": "NM_000001.1",
            "MANE": "",
            "CANONICAL": "",
        },
        {
            "Feature": "NM_000002.1",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "OLD1",
            "MANE_PLUS_CLINICAL": "",
            "MANE": "NM_000002.1",
            "CANONICAL": "YES",
        },
        {
            "Feature": "ENST000002.3",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "OLD1",
            "MANE_PLUS_CLINICAL": "",
            "MANE": "",
            "CANONICAL": "",
        },
    ]

    annotated = annotate_transcript_provenance(
        rows,
        hgnc_by_id={"HGNC:1": hgnc_doc},
        hgnc_by_symbol={"OLD1": hgnc_doc, "NEW1": hgnc_doc},
    )

    assert annotated[0]["transcript_tags"] == ["ncbi_mane_plus_clinical"]
    assert annotated[0]["canonical_source"] is None
    assert annotated[1]["transcript_tags"] == [
        "ncbi_mane_select",
        "vep_canonical",
    ]
    assert annotated[1]["canonical_source"] == "vep_canonical"
    assert annotated[1]["is_canonical"] is True
    assert annotated[2]["transcript_tags"] == ["ensembl_mane_select"]


def test_select_csq_prefers_native_refseq_mane_over_linked_ensembl_row():
    hgnc_doc = {
        "hgnc_id": "HGNC:1",
        "hgnc_symbol": "GENE1",
        "refseq_mane_plus_clinical": ["NM_000001.1"],
        "ensembl_mane_plus_clinical": [],
        "refseq_mane_select": "NM_000002.1",
        "ensembl_mane_select": "ENST000002.1",
    }
    selected, source = ingest_parsers._select_csq(
        [
            {
                "Feature": "ENST000001.1",
                "HGNC_ID": "HGNC:1",
                "IMPACT": "MODERATE",
                "BIOTYPE": "protein_coding",
                "MANE_PLUS_CLINICAL": "NM_000001.1",
            },
            {
                "Feature": "NM_000002.1",
                "HGNC_ID": "HGNC:1",
                "IMPACT": "HIGH",
                "BIOTYPE": "protein_coding",
                "MANE": "NM_000002.1",
            },
        ],
        hgnc_by_id={"HGNC:1": hgnc_doc},
    )

    assert selected["Feature"] == "NM_000002.1"
    assert source == "ncbi_mane_select"


def test_select_csq_uses_vep_canonical_after_mane_candidates_are_exhausted():
    hgnc_doc = {
        "hgnc_id": "HGNC:2",
        "hgnc_symbol": "NEW2",
        "prev_symbol": ["OLD2"],
        "alias_symbol": ["ALIAS2"],
        "refseq_mane_select": "",
        "ensembl_mane_select": "",
        "refseq_mane_plus_clinical": [],
    }

    selected, source = ingest_parsers._select_csq(
        [
            {
                "Feature": "NM_000004.1",
                "HGNC_ID": "",
                "SYMBOL": "OLD2",
                "IMPACT": "MODERATE",
                "CANONICAL": "",
                "BIOTYPE": "protein_coding",
            },
            {
                "Feature": "NM_000099.1",
                "HGNC_ID": "",
                "SYMBOL": "OTHER",
                "IMPACT": "MODERATE",
                "CANONICAL": "YES",
                "BIOTYPE": "protein_coding",
            },
        ],
        hgnc_by_symbol={"OLD2": hgnc_doc, "NEW2": hgnc_doc, "ALIAS2": hgnc_doc},
    )

    assert source == "vep_canonical_protein_coding"
    assert selected["Feature"] == "NM_000099.1"


def test_hgnc_metadata_maps_include_case_insensitive_aliases():
    class _Gateway:
        def collection(self, name):
            assert name == "hgnc_genes"
            return _Col(
                [
                    {
                        "_id": "HGNC:3",
                        "hgnc_id": "HGNC:3",
                        "hgnc_symbol": "NEW3",
                        "prev_symbol": ["Old3"],
                        "alias_symbol": ["Alias3"],
                    }
                ]
            )

        def sample_collection(self):
            return _Col()

        def mongo_client(self):
            return None

        def session_scope(self):
            return None

    service = ingest.InternalIngestService(
        collection_gateway=_Gateway(),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_summary=lambda: None,
    )
    by_id, by_symbol = service._hgnc_metadata_maps()

    assert by_id["HGNC:3"]["hgnc_symbol"] == "NEW3"
    assert by_symbol["NEW3"]["hgnc_id"] == "HGNC:3"
    assert by_symbol["OLD3"]["hgnc_id"] == "HGNC:3"
    assert by_symbol["ALIAS3"]["hgnc_id"] == "HGNC:3"


def test_sample_meta_extracts_vep_database_versions_from_vcf_header(tmp_path):
    vcf = tmp_path / "sample.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        '##VEP="v103" time="2026-07-12 00:47:04" cache="/tmp/cache" '
        'Assembly="GRCh38.p13" COSMIC="92" ClinVar="202008" dbSNP="154" '
        'Ensembl="103.4c8d44a" Gencode="GENCODE 37" Genebuild="2014-07" '
        'gnomAD="r2.1" HGMD-Public="20194" PolyPhen="2.2.2" SIFT="sift5.2.2" '
        'RandomPlugin="do-not-store"\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
        encoding="utf-8",
    )
    meta = ingest.build_sample_meta_dict(
        {
            "name": "S1",
            "case_id": "C1",
            "sample_no": 1,
            "vcf_files": str(vcf),
        }
    )
    assert meta["database_versions"] == {
        "assembly": "GRCh38.p13",
        "clinvar": "202008",
        "cosmic": "92",
        "dbsnp": "154",
        "ensembl": "103.4c8d44a",
        "gencode": "GENCODE 37",
        "genebuild": "2014-07",
        "gnomad": "r2.1",
        "hgmd_public": "20194",
        "polyphen": "2.2.2",
        "sift": "sift5.2.2",
        "vep": "103",
    }
    assert meta["database_versions"]["vep"] == "103"
    assert meta["database_versions"]["cosmic"] == "92"
    assert meta["database_versions"]["clinvar"] == "202008"
    assert meta["database_versions"]["dbsnp"] == "154"
    assert meta["database_versions"]["gnomad"] == "r2.1"


def test_sample_meta_extracts_versions_from_runtime_vcf_path(tmp_path):
    vcf = tmp_path / "uploaded.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        '##VEP="v112" COSMIC="99" ClinVar="202406"\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
        encoding="utf-8",
    )
    meta = ingest.build_sample_meta_dict(
        {
            "name": "S1",
            "case_id": "C1",
            "sample_no": 1,
            "_runtime_files": {"vcf_files": str(vcf)},
            "files": {"vcf_files": {"path": "/staged/original-name.vcf"}},
        }
    )
    assert meta["database_versions"]["vep"] == "112"
    assert meta["database_versions"]["cosmic"] == "99"
    assert meta["database_versions"]["clinvar"] == "202406"


def test_type_and_string_helpers(monkeypatch):
    _ = monkeypatch
    assert ingest_parsers.infer_omics_layer({"vcf_files": "x"}) == "dna"
    with pytest.raises(ValueError):
        ingest_parsers.infer_omics_layer({"vcf_files": "x", "fusion_files": "y"})

    left, right, true = sample_updates.catch_left_right("CASE", "CASE-2")
    assert (left, right, true) == ("", "-2", "CASE")

    assert ingest_parsers._split_on_colon("NM:123") == "123"
    assert ingest_parsers._split_on_colon("NM_1") == "NM_1"

    out = ingest_parsers._split_on_ampersand({}, "A&B")
    assert out == {"A": 1, "B": 1}
    out = ingest_parsers._collect_dbsnp({}, "abc&rs1&rs2")
    assert sorted(out) == ["rs1", "rs2"]
    hot = ingest_parsers._collect_hotspots({"a": [None, "1", "1"], "b": []})
    assert hot == {"a": ["1"]}


def test_assay_file_policy_normalizes_pipeline_asp_identifier(monkeypatch):
    store_stub = _store_stub()
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "asp_id": "hema_gmsv1",
            "asp_category": "dna",
            "expected_files": ["vcf_files", "cnv"],
            "required_files": ["vcf_files"],
        }
    ]
    service = _use_store(monkeypatch, store_stub)

    expected, required = service._assay_file_policy(
        assay_name="hema_GMSv1",
        omics_layer="DNA",
    )

    assert expected == {"vcf_files", "cnv"}
    assert required == {"vcf_files"}


def test_ingest_rejects_file_keys_outside_asp_expected_files(monkeypatch, tmp_path):
    store_stub = _store_stub()
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "asp_id": "assay_1",
            "assay_name": "assay_1",
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "display_name": "Assay 1",
            "expected_files": ["vcf_files", "cov"],
        }
    ]
    service = _use_store(monkeypatch, store_stub)
    vcf_path = tmp_path / "a.vcf.gz"
    cov_path = tmp_path / "a.cov.json"
    runtime_vcf_path = tmp_path / "runtime.a.vcf.gz"
    runtime_cov_path = tmp_path / "runtime.a.cov.json"
    for path in (vcf_path, cov_path, runtime_vcf_path, runtime_cov_path):
        path.write_text("{}", encoding="utf-8")
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "environment": "production",
        "case_id": "CASE1",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "vcf_files": str(vcf_path),
        "cov": str(cov_path),
        "cnv": "/data/a.cnv.json",
        "biomarkers": "/data/a.biomarkers.json",
        "_runtime_files": {
            "vcf_files": str(runtime_vcf_path),
            "cov": str(runtime_cov_path),
            "cnv": "/runtime/a.cnv.json",
        },
    }

    with pytest.raises(ValueError, match="biomarkers, cnv"):
        service._validate_payload_file_keys(payload)


def test_ingest_rejects_declared_unreadable_optional_file_keys(monkeypatch, tmp_path):
    store_stub = _store_stub()
    store_stub.coyote_db["asp_configs"].docs = [
        {
            "_id": "aspc-1",
            "aspc_id": "assay_1_base_production",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "production",
            "is_active": True,
            "analysis_types": ["SNV", "TRANSLOCATION"],
        }
    ]
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "asp_id": "assay_1",
            "assay_name": "assay_1",
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "display_name": "Assay 1",
            "expected_files": ["vcf_files", "transloc"],
            "required_files": ["vcf_files"],
        }
    ]
    service = _use_store(monkeypatch, store_stub)
    vcf_path = tmp_path / "sample.vcf"
    vcf_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "environment": "production",
        "case_id": "CASE1",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "vcf_files": str(vcf_path),
        "transloc": str(tmp_path / "missing.annotated.vcf"),
    }

    validated = service._validate_payload_file_keys(payload)

    assert validated["vcf_files"] == str(vcf_path)
    assert validated["transloc"] == str(tmp_path / "missing.annotated.vcf")
    with pytest.raises(FileNotFoundError, match="transloc="):
        service._validate_declared_file_resources(validated)


def test_aspc_enabled_analysis_requires_its_file_resource(tmp_path, monkeypatch):
    store_stub = _store_stub()
    store_stub.coyote_db["asp_configs"].docs = [
        {
            "_id": "aspc-1",
            "aspc_id": "assay_1_base_production",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "production",
            "is_active": True,
            "analysis_types": ["SNV", "CNV", "CNV_PROFILE", "COVERAGE"],
        }
    ]
    service = _use_store(monkeypatch, store_stub)
    vcf_path = tmp_path / "sample.vcf"
    vcf_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    payload = service._validate_payload_file_keys(
        {
            "name": "S1",
            "asp_id": "assay_1",
            "environment": "production",
            "omics_layer": "dna",
            "vcf_files": str(vcf_path),
        }
    )

    with pytest.raises(ValueError, match="cnv, cnvprofile, cov"):
        service._validate_declared_file_resources(payload)


def test_float_and_af_helpers():
    assert ingest_parsers._is_float("1.2")
    assert not ingest_parsers._is_float("1")
    assert not ingest_parsers._is_float("x")

    d = {"INFO": {"CSQ": [{"CADD_PHRED": "1.2&3.4", "SIFT": "x"}]}}
    out = ingest_parsers._emulate_perl(d)
    assert out["INFO"]["CSQ"][0]["CADD_PHRED"] == 3.4

    assert ingest_parsers._parse_allele_freq("A:0.1&C:0.2", "C") == 0.2
    assert ingest_parsers._parse_allele_freq(None, "A") == 0.0

    assert ingest_parsers._max_gnomad("0.1&0.2") == 0.2
    assert ingest_parsers._max_gnomad(None) is None

    var = {
        "ALT": "A",
        "INFO": {
            "CSQ": [
                {
                    "ExAC_MAF": "A:0.01",
                    "GMAF": "A:0.02",
                    "gnomAD_AF": "0.03&0.05",
                    "MAX_AF": "0.06",
                }
            ]
        },
    }
    af = ingest_parsers._pick_af_fields(var)
    assert af["gnomad_frequency"] == 0.05
    assert af["gnomad_max"] == "0.06"
    assert af["exac_frequency"] == 0.01


def test_transcript_helpers():
    csq = [
        {
            "Feature": "ENST0001.1",
            "HGNC_ID": "HGNC:1",
            "SYMBOL": "EGFR",
            "Consequence": "missense_variant",
            "IMPACT": "MODERATE",
            "VARIANT_CLASS": "SNV",
            "HGVSc": "NM:1",
            "HGVSp": "NP:2",
            "BIOTYPE": "protein_coding",
            "CANONICAL": "YES",
            "COSMIC": "COSM1&COSM2",
            "Existing_variation": "db&rs10",
            "PUBMED": "1&2",
            "luhotspot_OID": "OID1",
        }
    ]
    parsed = ingest_parsers._parse_transcripts(csq)
    assert parsed[1] == ["COSM1", "COSM2"]
    assert parsed[2] == "rs10"
    assert parsed[3] == ["1", "2"]
    assert parsed[4] == ["ENST0001"]
    assert parsed[9] == ["missense_variant"]

    assert feature_without_version("NM_1.2") == "NM_1"

    chosen, src = ingest_parsers._select_csq(
        [
            {
                "IMPACT": "LOW",
                "SYMBOL": "X",
                "Feature": "ENST.1",
                "CANONICAL": "NO",
                "BIOTYPE": "protein_coding",
            },
            {
                "IMPACT": "MODERATE",
                "SYMBOL": "EGFR",
                "Feature": "NM_005228.5",
                "CANONICAL": "NO",
                "BIOTYPE": "protein_coding",
            },
        ],
    )
    assert src == "first_protein_coding"
    assert chosen["SYMBOL"] == "EGFR"


def test_next_unique_name(monkeypatch):
    stub = _store_stub([{"name": "CASE"}, {"name": "CASE-2"}])
    service = _use_store(monkeypatch, stub)

    with pytest.raises(ValueError):
        service._next_unique_name("CASE", increment=False)

    assert service._next_unique_name("NEW", increment=False) == "NEW"
    assert service._next_unique_name("CASE", increment=True) == "CASE-3"


def test_build_anno_vep_docs_includes_selected_and_alternate_transcripts():
    docs = ingest_parsers._build_anno_vep_docs(
        [
            {
                "simple_id": "1:100:A:T",
                "variant_class": "SNV",
                "INFO": {
                    "selected_CSQ": {"Feature": "ENST1", "SIFT": "deleterious"},
                    "CSQ": [{"Feature": "ENST2", "SIFT": "tolerated"}],
                },
            }
        ],
        "v103",
    )

    assert docs == [
        {
            "simple_id": "1:100:A:T",
            "simple_id_hash": ingest_parsers.build_simple_id_hash_from_simple_id("1:100:A:T"),
            "vep_version": "103",
            "variant_class": "SNV",
            "CSQ": [
                {"Feature": "ENST1", "SIFT": "deleterious"},
                {"Feature": "ENST2", "SIFT": "tolerated"},
            ],
        }
    ]


def test_selected_transcript_projection_excludes_vault_only_provenance() -> None:
    selected = compact_selected_csq(
        {
            "Feature": "NM_000001.1",
            "SYMBOL": "TP53",
            "HGNC_ID": "HGNC:11998",
            "Consequence": ["missense_variant"],
            "VEP_SYMBOL": "P53",
            "HGNC_MATCHED": True,
            "HGNC_MATCH_SOURCE": "previous_or_alias_symbol",
            "MANE_SELECT": "NM_000001.1",
            "MANE_PLUS_CLINICAL": "NM_000001.1",
            "transcript_tags": ["ncbi_mane_plus_clinical"],
            "canonical_source": "vep_canonical",
            "is_canonical": True,
        }
    )

    assert selected == {
        "Feature": "NM_000001.1",
        "SYMBOL": "TP53",
        "HGNC_ID": "HGNC:11998",
        "Consequence": ["missense_variant"],
    }


def test_parse_transcripts_indexes_consequences_from_every_transcript() -> None:
    parsed = ingest_parsers._parse_transcripts(
        [
            {"Consequence": "missense_variant"},
            {"Consequence": "splice_region_variant&intron_variant"},
            {"Consequence": "missense_variant"},
        ]
    )

    assert parsed[9] == ["missense_variant", "splice_region_variant", "intron_variant"]


def test_parse_transcripts_normalizes_clinical_significance_terms() -> None:
    parsed = ingest_parsers._parse_transcripts(
        [
            {
                "Feature": "NM_000001.1",
                "CLIN_SIG": "uncertain_significance&likely_pathogenic",
            }
        ]
    )

    assert parsed[0][0]["CLIN_SIG"] == ["uncertain_significance", "likely_pathogenic"]


def test_normalize_historical_transloc_doc():
    out = ingest_parsers._normalize_transloc_doc(
        {
            "FILTER": "PASS",
            "FORMAT": "UR",
            "GT": [{"UR": "2", "_sample_id": "S1"}],
            "INFO": {
                "SVTYPE": "BND",
                "set": "genefuse",
                "ANN": [
                    {
                        "Allele": "G",
                        "Annotation": ["bidirectional_gene_fusion"],
                        "Gene_Name": "ALK&ROS1",
                        "Gene_ID": "ENSG1&ENSG2",
                        "Feature_Type": "transcript",
                        "Feature_ID": "ENST1",
                    }
                ],
            },
        }
    )
    assert out["FILTER"] == ["PASS"]
    assert out["FORMAT"] == ["UR"]
    assert out["GT"] == [{"UR": 2.0, "sample": "S1", "PR": "", "SR": ""}]
    assert out["INFO"]["SOMATIC"] is False
    assert out["INFO"]["PANEL"] == ["genefuse"]


def test_normalize_translocation_preserves_missing_ur_and_qual():
    from api.application.ingest.parsers import _normalize_transloc_doc

    out = _normalize_transloc_doc(
        {
            "QUAL": "",
            "GT": [{"UR": "", "_sample_id": "S1", "PR": "0,1", "SR": "2,3"}],
        }
    )

    assert out["QUAL"] is None
    assert out["GT"] == [{"UR": None, "sample": "S1", "PR": "0,1", "SR": "2,3"}]


def test_parse_yaml_payload():
    service = ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            collections={"samples": _Col(), "anno_vep": _Col()}
        ),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_summary=lambda: None,
    )
    parsed = service.parse_yaml_payload("name: S1\nasp_id: A\ndatabase_versions:\n  vep: '110'\n")
    assert parsed["name"] == "S1"
    assert parsed["database_versions"]["vep"] == "110"
    parsed = service.parse_yaml_payload(
        "name: S1\nasp_id: A\ncontrol_id: 'null'\ncontrol_reads: n/a\ncase_purity: NONE\n"
    )
    assert parsed["control_id"] is None
    assert parsed["control_reads"] is None
    assert parsed["case_purity"] is None

    parsed = service.parse_yaml_payload(
        "name: S1\nassay: hema_GMSv1\nsubpanel: Hem\nprofile: production\n"
        "sequencing_technology: Illumina\n"
    )
    assert parsed["asp_id"] == "hema_GMSv1"
    assert parsed["subpanel_id"] == "Hem"
    assert parsed["environment"] == "production"
    assert parsed["platform"] == "Illumina"
    assert "assay" not in parsed

    parsed = service.parse_yaml_payload(
        "subpanel: Hem\nname: SAMPLE_1\nclarity_case_id: CASE_CLARITY\n"
        "clarity_control_id: CONTROL_CLARITY\ngenome_build: 38\n"
        "vcf_files: /srv/coyote3-data/case.vcf\nsample_no: 2\n"
        "case_id: CASE_1\ncontrol_id: CONTROL_1\nprofile: production\n"
        "assay: hema_GMSv1\nsequencing_scope: panel\nomics_layer: DNA\n"
        "sequencing_technology: Illumina\npipeline: SomaticPanelPipeline\n"
        "pipeline_version: 3.2.0\ncase_purity: null\ncontrol_purity: 'null'\n"
        "paired: true\ncnv: /srv/coyote3-data/case.cnvs.json\n"
        "cnvprofile: /srv/coyote3-data/case.profile.png\n"
        "cov: /srv/coyote3-data/case.coverage.json\n"
    )
    assert parsed["asp_id"] == "hema_GMSv1"
    assert parsed["subpanel_id"] == "Hem"
    assert parsed["environment"] == "production"
    assert parsed["platform"] == "Illumina"
    assert parsed["vcf_files"] == "/srv/coyote3-data/case.vcf"
    assert parsed["cnv"] == "/srv/coyote3-data/case.cnvs.json"
    assert parsed["cnvprofile"] == "/srv/coyote3-data/case.profile.png"
    assert parsed["cov"] == "/srv/coyote3-data/case.coverage.json"
    assert parsed["case_purity"] is None
    assert parsed["control_purity"] is None

    with pytest.raises(ValueError, match="conflicting values"):
        service.parse_yaml_payload("name: S1\nassay: assay_a\nasp_id: assay_b\n")

    with pytest.raises(ValueError):
        service.parse_yaml_payload("- 1\n- 2\n")


def test_dna_and_rna_parser_parse(tmp_path, monkeypatch):
    vcf = tmp_path / "a.vcf"
    cnv = tmp_path / "a.cnv.json"
    bio = tmp_path / "a.bio.json"
    cov = tmp_path / "a.cov.json"
    transloc = tmp_path / "a.transloc.vcf"
    fus = tmp_path / "fusions.json"
    expr = tmp_path / "expr.json"
    cls = tmp_path / "class.json"
    qc = tmp_path / "qc.json"
    pgx = tmp_path / "pgx.json"

    for p in [vcf, transloc]:
        p.write_text("x", encoding="utf-8")
    cnv.write_text(json.dumps({"k": {"ratio": 1}}), encoding="utf-8")
    bio.write_text(json.dumps({"name": "b"}), encoding="utf-8")
    cov.write_text(json.dumps({"genes": {}}), encoding="utf-8")
    fus.write_text(
        json.dumps(
            [
                {
                    "genes": "NTRK1^TPM3",
                    "gene1": "NTRK1",
                    "gene2": "TPM3",
                    "calls": [
                        {
                            "caller": "starfusion",
                            "selected": 1,
                            "longestanchor": "<25",
                            "spanpairs": "1",
                            "spanreads": "6",
                            "breakpoint1": "1:100:+",
                            "breakpoint2": "2:200:-",
                        },
                        {
                            "caller": "fusioncatcher",
                            "longestanchor": "36",
                            "spanpairs": "9",
                            "spanreads": "2",
                            "breakpoint1": "1:101:+",
                            "breakpoint2": "2:201:-",
                            "effect": "out-of-frame",
                            "commonreads": "0",
                            "desc": "known",
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    expr.write_text(json.dumps({"a": 1}), encoding="utf-8")
    cls.write_text(json.dumps({"c": 1}), encoding="utf-8")
    qc.write_text(json.dumps({"q": 1}), encoding="utf-8")
    pgx.write_text(
        json.dumps([{"gene": "CYP2C19", "phenotype": "Intermediate metabolizer"}]),
        encoding="utf-8",
    )

    parser = ingest.DnaIngestParser()
    monkeypatch.setattr(parser, "_parse_snvs_only", lambda _: [{"CHROM": "1"}])
    monkeypatch.setattr(parser, "_parse_transloc_only", lambda _: [{"CHROM": "2"}])

    out = parser.parse(
        {
            "vcf_files": str(vcf),
            "cnv": str(cnv),
            "biomarkers": str(bio),
            "transloc": str(transloc),
            "cov": str(cov),
            "pgx": str(pgx),
            "name": "S1",
        }
    )
    assert {"snvs", "cnvs", "cov", "transloc", "pgx"} <= set(out)
    assert out["pgx"] == {"records": [{"gene": "CYP2C19", "phenotype": "Intermediate metabolizer"}]}

    rna = ingest.RnaIngestParser.parse(
        {
            "fusion_files": str(fus),
            "expression_path": str(expr),
            "classification_path": str(cls),
            "qc": str(qc),
        }
    )
    assert "fusions" in rna and "rna_expr" in rna and "rna_class" in rna and "rna_qc" in rna
    assert rna["fusions"][0]["calls"][0]["selected"] == 1
    assert rna["fusions"][0]["calls"][1]["selected"] == 0
    assert rna["fusions"][0]["calls"][0]["effect"] == ""
    assert rna["fusions"][0]["calls"][0]["commonreads"] == 0
    assert rna["fusions"][0]["calls"][0]["desc"] == ""

    stored = dict(rna["fusions"][0], SAMPLE_ID="S1")
    validated = FusionsDoc.model_validate(stored)
    assert validated.calls[0].longestanchor == "<25"
    assert validated.calls[1].longestanchor == 36


def test_rna_parser_rejects_fusion_without_exactly_one_selected_call(tmp_path):
    fusion_path = tmp_path / "invalid-fusions.json"
    fusion_path.write_text(
        json.dumps(
            [
                {
                    "genes": "NTRK1^TPM3",
                    "calls": [
                        {"caller": "fusioncatcher"},
                        {"caller": "star-fusion"},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly one selected call; found 0"):
        ingest.RnaIngestParser.parse({"fusion_files": str(fusion_path)})


def test_dna_parser_normalizes_pipeline_cnv_shape(tmp_path):
    cnv = tmp_path / "pipeline.cnv.json"
    cnv.write_text(
        json.dumps(
            {
                "1:100-200": {
                    "callers": "gatk",
                    "ratio": 0.5,
                    "size": 100,
                    "chr": "1",
                    "start": 100,
                    "end": 200,
                    "genes": [{"gene": "TP53", "class": "somatic", "cnv_type": "unspec"}],
                },
                "2:300-400": {
                    "callers": "manta",
                    "ratio": "DEL",
                    "size": 100,
                    "chr": "2",
                    "start": 300,
                    "end": 400,
                    "genes": [{"gene": "EGFR"}],
                },
            }
        ),
        encoding="utf-8",
    )

    parser = ingest.DnaIngestParser()
    out = parser.parse({"cnv": str(cnv), "name": "S1"})

    assert out["cnvs"][0]["callers"] == ["gatk"]
    assert out["cnvs"][0]["nprobes"] == 0
    assert out["cnvs"][0]["ratio"] == 0.5
    assert out["cnvs"][0]["type"] == "DUP"
    assert out["cnvs"][1]["callers"] == ["manta"]
    assert out["cnvs"][1]["nprobes"] == 0
    assert out["cnvs"][1]["ratio"] == -1.0
    assert out["cnvs"][1]["type"] == "DEL"


def test_service_resolution_and_validation(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)

    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))
    out = service._normalize_collection_docs("variants", [{"a": 1}, {"b": 2}])
    assert out == [{"a": 1}, {"b": 2}]


def test_service_parse_preload(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)
    assert "samples" in service.list_supported_collections()

    monkeypatch.setattr(ingest.DnaIngestParser, "parse", lambda self, args: {"snvs": [args]})
    assert "snvs" in service._parse_preload({"omics_layer": "dna", "vcf_files": "x"})

    monkeypatch.setattr(ingest.RnaIngestParser, "parse", lambda args: {"fusions": [args]})
    assert "fusions" in service._parse_preload({"omics_layer": "rna", "fusion_files": "x"})

    with pytest.raises(ValueError):
        service._parse_preload({})


def test_write_and_ingest_dependents(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)
    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))
    monkeypatch.setattr(
        "api.application.ingest.dependent_writes.ensure_variant_identity_fields",
        lambda doc: {**doc, "simple_id_hash": "ok"},
    )

    preload = {
        "snvs": [{"CHROM": "1", "POS": 1, "REF": "A", "ALT": "T", "INFO": {}, "GT": []}],
        "cov": {"genes": {}},
    }
    out = service._write_dependents(
        preload=preload,
        sample_id="507f1f77bcf86cd799439012",
        sample_name="S1",
    )
    assert out["snvs"] == 1 and out["cov"] == 1

    with pytest.raises(TypeError):
        service._write_dependents(
            preload={"cov": []}, sample_id="507f1f77bcf86cd799439013", sample_name="S1"
        )


def test_snapshot_restore_replace_and_counts(monkeypatch):
    sid = "507f1f77bcf86cd799439014"
    cov_col = _Col([{"_id": "x", "SAMPLE_ID": str(sid), "a": 1}])
    stub = _store_stub()
    stub.coyote_db["panel_coverage"] = cov_col
    stub.coverage_repository = _Handler(cov_col)
    service = _use_store(monkeypatch, stub)

    snap = service._snapshot_dependents(sample_id=sid, keys={"cov"})
    assert "cov" in snap

    service._restore_dependents(
        sample_id=sid,
        sample_name="S1",
        backup={"cov": [{"_id": "x", "SAMPLE_ID": str(sid), "a": 1}]},
    )
    assert cov_col.inserted_many

    assert service._data_counts({"snvs": [1, 2], "cov": {}, "anno_vep": [1]}) == {
        "snvs": 2,
        "cov": False,
    }

    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"x": 1})
    out = service._replace_dependents(
        preload={"cov": {"genes": {}}}, sample_id=sid, sample_name="S1"
    )
    assert out["x"] == 1


def test_replace_dependents_restores_on_failure(monkeypatch):
    sid = "507f1f77bcf86cd799439015"
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)
    called = {"restored": False}

    monkeypatch.setattr(
        service, "_write_dependents", lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(service, "_restore_dependents", lambda **_: called.update(restored=True))

    with pytest.raises(RuntimeError):
        service._replace_dependents(preload={"snvs": []}, sample_id=sid, sample_name="S1")
    assert called["restored"]


def test_update_payload_guard_and_meta_update(monkeypatch):
    service = ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            collections={"samples": _Col(), "anno_vep": _Col()}
        ),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_summary=lambda: None,
    )
    out = service._prepare_update_payload(
        sample_doc={"omics_layer": "rna", "fusion_files": "x"},
        payload={"name": "S1"},
    )
    assert out["omics_layer"] == "rna"

    with pytest.raises(ValueError):
        service._prepare_update_payload(
            sample_doc={"omics_layer": "rna", "fusion_files": "x"},
            payload={"name": "S1", "vcf_files": "/tmp/a.vcf"},
        )

    sample_col = _Col([{"_id": "id1", "name": "S1", "asp_id": "A", "x": 1}])
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    service = _use_store(monkeypatch, stub)

    service._update_meta_fields(
        sample_id="id1",
        payload_meta={"name": "S1", "x": 2, "new_key": 3},
        block_fields={"asp_id"},
    )
    assert sample_col.updated

    with pytest.raises(ValueError):
        service._update_meta_fields(
            sample_id="id1",
            payload_meta={"asp_id": "B"},
            block_fields={"asp_id"},
        )


def test_ingest_update_and_ingest_sample_bundle(monkeypatch):
    sample_id = "507f1f77bcf86cd799439016"
    sample_col = _Col(
        [
            {
                "_id": sample_id,
                "name": "S1",
                "asp_id": "assay_1",
                "subpanel_id": "Hem",
                "environment": "production",
                "case_id": "seed_case",
                "sample_no": 1,
                "sequencing_scope": "panel",
                "omics_layer": "dna",
                "pipeline": "SomaticPanelPipeline",
                "pipeline_version": "1.0.0",
                "vcf_files": "x",
            }
        ]
    )
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    service = _use_store(monkeypatch, stub)
    monkeypatch.setattr(
        service,
        "_prepare_update_payload",
        lambda sample_doc, payload: {
            "name": payload["name"],
            "asp_id": "assay_1",
            "subpanel_id": "Hem",
            "environment": "production",
            "case_id": "seed_case",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "case_ffpe": False,
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
        },
    )
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": [{"a": 1}]})
    monkeypatch.setattr(service, "_replace_dependents", lambda **_: {"snvs": 1})
    monkeypatch.setattr(ingest, "build_sample_meta_dict", lambda _: {"name": "S1"})
    monkeypatch.setattr(service, "_update_meta_fields", lambda **_: None)

    out = service._ingest_update({"name": "S1"})
    assert out["status"] == "ok"

    with pytest.raises(ValueError):
        service._ingest_update({"name": "MISSING"})

    with pytest.raises(ValueError):
        service.ingest_sample_bundle({}, allow_update=False)

    monkeypatch.setattr(service, "_ingest_update", lambda _: {"status": "ok"})
    update_payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "subpanel_id": "Hem",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "vcf_files": "x",
    }
    assert service.ingest_sample_bundle(update_payload, allow_update=True)["status"] == "ok"


def test_ingest_sample_bundle_create_and_insert_helpers(monkeypatch):
    sample_col = _Col([])
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    service = _use_store(monkeypatch, stub, new_sample_id="507f1f77bcf86cd799439017")
    monkeypatch.setattr(service, "_validate_payload_file_keys", lambda payload: payload)
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_apply_resolved_aspc_snapshot", lambda payload: payload)
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": []})
    monkeypatch.setattr(service, "_next_unique_name", lambda *_: "S1")
    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"snvs": 0})

    class _Valid:
        def model_dump(self, *args, **kwargs):
            _ = args, kwargs
            return {"name": "S1", "asp_id": "A", "case_id": "C", "sample_no": 1}

        def to_persistence_document(self):
            return self.model_dump()

    monkeypatch.setattr(ingest.SamplesDoc, "model_validate", lambda _: _Valid())
    monkeypatch.setattr(
        ingest, "build_sample_meta_dict", lambda _: {"asp_id": "A", "case_id": "C", "sample_no": 1}
    )

    out = service.ingest_sample_bundle(
        {"name": "S1", "asp_id": "A", "omics_layer": "dna"}, allow_update=False
    )
    assert out["status"] == "ok"

    monkeypatch.setattr(
        service, "_write_dependents", lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    cleaned = {"called": False}
    monkeypatch.setattr(service, "_cleanup", lambda _sid: cleaned.update(called=True))
    with pytest.raises(RuntimeError):
        service.ingest_sample_bundle(
            {"name": "S2", "asp_id": "A", "omics_layer": "dna"}, allow_update=False
        )
    assert cleaned["called"]

    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))

    one = service.insert_collection_document(collection="variants", document={"a": 1})
    assert one["inserted_count"] == 1

    many = service.insert_collection_documents(
        collection="variants", documents=[{"a": 1}, {"b": 2}]
    )
    assert many["inserted_count"] == 2

    zero = service.insert_collection_documents(collection="variants", documents=[])
    assert zero["inserted_count"] == 0


def test_ingest_sample_bundle_persists_meaningful_null_metadata(monkeypatch):
    sample_col = _Col([])
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    service = _use_store(monkeypatch, stub, new_sample_id="507f1f77bcf86cd799439018")
    monkeypatch.setattr(service, "_validate_payload_file_keys", lambda payload: payload)
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_apply_resolved_aspc_snapshot", lambda payload: payload)
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": []})
    monkeypatch.setattr(service, "_next_unique_name", lambda *_: "S2")
    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"snvs": 0})

    result = service.ingest_sample_bundle(
        {
            "name": "S2",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "production",
            "case_id": "C2",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "not provided",
            "files": {"vcf_files": {"path": "x"}},
        }
    )

    assert result["status"] == "ok"
    inserted = sample_col.inserted_one[0]
    assert inserted["pipeline_version"] is None
    assert inserted["control"] is None
    assert inserted["case"]["purity"] is None
    assert inserted["files"]["vcf_files"]["checksum"] is None


def test_ingest_sample_bundle_stages_loading_then_marks_ready(monkeypatch):
    sample_col = _Col([])
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    service = _use_store(monkeypatch, stub, new_sample_id="507f1f77bcf86cd799439019")
    monkeypatch.setattr(service, "_validate_payload_file_keys", lambda payload: payload)
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_apply_resolved_aspc_snapshot", lambda payload: payload)
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": []})
    monkeypatch.setattr(service, "_next_unique_name", lambda *_: "S3")
    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"snvs": 0})

    class _Valid:
        def __init__(self, payload):
            self.payload = dict(payload)

        def model_dump(self, *args, **kwargs):
            _ = args, kwargs
            return dict(self.payload)

        def to_persistence_document(self):
            return self.model_dump()

    monkeypatch.setattr(ingest.SamplesDoc, "model_validate", lambda payload: _Valid(payload))
    monkeypatch.setattr(
        ingest,
        "build_sample_meta_dict",
        lambda payload: {
            "asp_id": payload.get("asp_id", "A"),
            "case_id": payload.get("case_id", "C"),
            "sample_no": payload.get("sample_no", 1),
        },
    )

    out = service.ingest_sample_bundle(
        {"name": "S3", "asp_id": "A", "case_id": "C", "sample_no": 1},
        allow_update=False,
    )

    assert out["status"] == "ok"
    assert sample_col.inserted_one[0]["ingest_status"] == "loading"
    assert sample_col.updated[-1][1] == {
        "$set": {"ingest_status": "ready", "data_counts": {"snvs": 0}}
    }


def test_ingest_sample_bundle_initializes_sample_filters_from_aspc(monkeypatch):
    sample_col = _Col([])
    stub = _store_stub()
    stub.sample_repository = _Handler(sample_col)
    stub.coyote_db["asp_configs"].docs = [
        {
            "asp_id": "assay_1",
            "subpanel_id": "hem",
            "environment": "production",
            "is_active": True,
            "asp_category": "dna",
            "analysis_intents": ["somatic"],
            "filters": {
                "somatic": {
                    "snv": {
                        "max_freq": 1,
                        "min_freq": 0,
                        "max_control_freq": 0.05,
                        "max_popfreq": 0.05,
                        "min_depth": 100,
                        "min_alt_reads": 5,
                        "snvlists": ["hematology_myeloid"],
                        "vep_consequences": ["missense"],
                    },
                    "cnv": {"cnveffects": ["gain", "loss"], "cnvlists": []},
                }
            },
            "reporting": {"report_sections": ["SNV"]},
        }
    ]
    service = _use_store(monkeypatch, stub, new_sample_id="507f1f77bcf86cd799439018")
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_parse_preload", lambda payload: {"snvs": [], "_seen": payload})
    monkeypatch.setattr(service, "_next_unique_name", lambda *_: "S1")
    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"snvs": 0})

    out = service.ingest_sample_bundle(
        {
            "name": "S1",
            "asp_id": "assay_1",
            "subpanel_id": "hem",
            "environment": "production",
            "case_id": "seed_case",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "case_ffpe": False,
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
        },
        allow_update=False,
    )

    assert out["status"] == "ok"
    inserted = sample_col.inserted_one[-1]
    assert inserted["filters"]["somatic"]["snv"]["snvlists"] == ["hematology_myeloid"]
    assert inserted["filters"]["somatic"]["snv"]["vep_consequences"] == ["missense"]
    assert inserted["filters"]["somatic"]["cnv"]["cnveffects"] == ["gain", "loss"]
