"""Unit tests for internal ingestion service helpers and orchestration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import coyote.application.ingest.helpers as ingest_helpers
import coyote.application.ingest.parsers as ingest_parsers
import coyote.application.ingest.sample_updates as sample_updates
import coyote.application.ingest.service as ingest
import pytest
from coyote.application.ingest.analysis_parsers import DnaIngestParser, RnaIngestParser
from coyote.contracts.schemas.rna import FusionsDoc
from coyote.domain.dna.transcript_payloads import (
    annotate_transcript_provenance,
    compact_selected_csq,
    feature_without_version,
)


class _Col:
    def __init__(self, docs=None):
        self.database = SimpleNamespace(client=None)
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

    def find_one(self, query, session=None):
        if "asp_id" in query:
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items()):
                    return doc
            return None
        for doc in self.find(query):
            return doc
        return None

    def insert_one(self, doc, session=None):
        self.inserted_one.append(doc)
        self.docs.append(doc)
        return SimpleNamespace(inserted_id="oid1")

    def insert_many(self, docs, ordered=True, session=None):
        _ = ordered
        self.inserted_many.append(list(docs))
        self.docs.extend(docs)
        return SimpleNamespace(inserted_ids=["oid" for _ in docs])

    def delete_many(self, query, session=None):
        self.deleted.append(query)

    def delete_one(self, query):
        self.deleted.append(query)

    def update_one(self, query, update, upsert=False, session=None):
        self.updated.append((query, update, upsert))

    def replace_one(self, filter, replacement, upsert=False, session=None):
        self.updated.append((filter, replacement, upsert))
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

    def estimated_document_count(self):
        return len(self.docs)


class _AnnoVepRepo:
    def __init__(self):
        self.docs = []

    def upsert_many(self, docs, session=None):
        _ = session
        self.docs.extend(list(docs))


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
        "diagnosis_id": "base",
        "environment": "production",
        "case_id": "RNA1",
        "sample_no": 1,
        "paired": False,
        "asp_family": "wts",
        "asp_category": "rna",
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

    assert meta["case"] == {"id": "RNA1", "bam": "", "bai": "", "ffpe": False}
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
    biomarker_path.write_text(
        json.dumps({"name": "S1", "HRD": {"tai": 1, "hrd": 2, "lst": 3, "sum": 6}}),
        encoding="utf-8",
    )
    transloc_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
    cov_path.write_text(json.dumps({"genes": {}}), encoding="utf-8")

    monkeypatch.setattr(
        DnaIngestParser,
        "_parse_transloc_only",
        staticmethod(lambda _path: [{"CHROM": "1", "POS": 1}]),
    )

    parser = DnaIngestParser()
    preload = parser.parse(
        {
            "asp_category": "dna",
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
        def hgnc_documents(self, projection):
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
            ).find({}, projection)

        def sample_collection(self):
            return _Col()

        def mongo_client(self):
            return None

        def session_scope(self):
            return None

    service = ingest.InternalIngestService(
        collection_gateway=_Gateway(),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_metrics=lambda: None,
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
    assert ingest_parsers.infer_asp_category({"vcf_files": "x"}) == "dna"
    with pytest.raises(ValueError):
        ingest_parsers.infer_asp_category({"vcf_files": "x", "fusion_files": "y"})

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


@pytest.mark.parametrize(
    "score,expected", [(3.4, "3.4"), (0, "0"), (12, "12"), ("3.40", "3.40"), (None, None)]
)
def test_ingest_normalizes_cadd_score_for_selected_csq(score, expected):
    from coyote.contracts.schemas.dna import VariantCsqDoc
    from coyote.domain.dna.transcript_payloads import compact_selected_csq

    transcripts = ingest_parsers._parse_transcripts(
        [{"Feature": "ENST_SYNTHETIC", "CADD_PHRED": score}]
    )[0]
    selected = compact_selected_csq(transcripts[0])
    assert VariantCsqDoc.model_validate(selected).CADD_PHRED == expected


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
    from coyote.application.ingest.parsers import _normalize_transloc_doc

    out = _normalize_transloc_doc(
        {
            "QUAL": "",
            "GT": [{"UR": "", "_sample_id": "S1", "PR": "0,1", "SR": "2,3"}],
        }
    )

    assert out["QUAL"] is None
    assert out["GT"] == [{"UR": None, "sample": "S1", "PR": "0,1", "SR": "2,3"}]


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
    bio.write_text(json.dumps({"name": "b", "TMB": {"value": 0}}), encoding="utf-8")
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

    parser = DnaIngestParser()
    monkeypatch.setattr(parser, "_parse_snvs_only", lambda _, **kwargs: [{"CHROM": "1"}])
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

    rna = RnaIngestParser.parse(
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
        RnaIngestParser.parse({"fusion_files": str(fusion_path)})


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

    parser = DnaIngestParser()
    out = parser.parse({"cnv": str(cnv), "name": "S1"})

    assert out["cnvs"][0]["callers"] == ["gatk"]
    assert out["cnvs"][0]["nprobes"] == 0
    assert out["cnvs"][0]["ratio"] == 0.5
    assert out["cnvs"][0]["type"] == "DUP"
    assert out["cnvs"][1]["callers"] == ["manta"]
    assert out["cnvs"][1]["nprobes"] == 0
    assert out["cnvs"][1]["ratio"] == -1.0
    assert out["cnvs"][1]["type"] == "DEL"
