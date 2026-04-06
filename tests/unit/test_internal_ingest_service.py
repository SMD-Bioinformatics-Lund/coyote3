"""Unit tests for internal ingestion service helpers and orchestration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import api.services.ingest.parsers as ingest_parsers
import api.services.ingest.service as ingest


class _Col:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted_one = []
        self.inserted_many = []
        self.deleted = []
        self.updated = []

    def find(self, query=None):
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


class _Handler:
    def __init__(self, col):
        self._col = col

    def get_collection(self):
        return self._col


def _store_stub(sample_docs=None):
    sample_col = _Col(sample_docs)
    refs = _Col([{"gene": "EGFR", "canonical": "NM_005228"}, {"gene": "BAD"}])
    db = {
        "refseq_canonical": refs,
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
    }
    return SimpleNamespace(
        sample_handler=_Handler(sample_col),
        variant_handler=_Handler(db["variants"]),
        copy_number_variant_handler=_Handler(db["cnvs"]),
        biomarker_handler=_Handler(db["biomarkers"]),
        translocation_handler=_Handler(db["transloc"]),
        coverage_handler=_Handler(db["panel_coverage"]),
        grouped_coverage_handler=_Handler(db["group_coverage"]),
        fusion_handler=_Handler(db["fusions"]),
        rna_expression_handler=_Handler(db["rna_expression"]),
        rna_classification_handler=_Handler(db["rna_classification"]),
        rna_quality_handler=_Handler(db["rna_qc"]),
        coyote_db=db,
    )


def _use_store(monkeypatch, store_stub, *, new_sample_id="507f1f77bcf86cd799439011"):
    monkeypatch.setattr(ingest, "_provider_sample_id", lambda sample_id: sample_id)
    monkeypatch.setattr(ingest, "_new_sample_id", lambda: new_sample_id)
    return ingest.InternalIngestService(
        sample_collection=store_stub.sample_handler.get_collection(),
        refseq_canonical_collection=store_stub.coyote_db["refseq_canonical"],
        collections={
            "samples": store_stub.sample_handler.get_collection(),
            "variants": store_stub.variant_handler.get_collection(),
            "cnvs": store_stub.copy_number_variant_handler.get_collection(),
            "biomarkers": store_stub.biomarker_handler.get_collection(),
            "translocations": store_stub.translocation_handler.get_collection(),
            "panel_coverage": store_stub.coverage_handler.get_collection(),
            "fusions": store_stub.fusion_handler.get_collection(),
            "rna_expression": store_stub.rna_expression_handler.get_collection(),
            "rna_classification": store_stub.rna_classification_handler.get_collection(),
            "rna_qc": store_stub.rna_quality_handler.get_collection(),
        },
        invalidate_variant_cache=lambda: None,
        invalidate_summary_cache=lambda: None,
    )


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

    norm_case, norm_ctrl = ingest._normalize_case_control(
        {
            "case_id": "C1",
            "control_id": "N1",
            "case_reads": "null",
            "control_reads": None,
            "case_ffpe": False,
            "control_ffpe": True,
        }
    )
    assert norm_case["reads"] is None
    assert norm_ctrl["reads"] is None

    meta = ingest.build_sample_meta_dict(
        {
            "name": "S1",
            "case_id": "C1",
            "control_id": "N1",
            "case_reads": 10,
            "control_reads": 20,
            "increment": True,
        }
    )
    assert "increment" not in meta
    assert meta["case"]["reads"] == 10
    assert meta["control"]["reads"] == 20


def test_type_and_string_helpers(monkeypatch):
    _ = monkeypatch
    assert ingest_parsers.infer_omics_layer({"vcf_files": "x"}) == "dna"
    with pytest.raises(ValueError):
        ingest_parsers.infer_omics_layer({"vcf_files": "x", "fusion_files": "y"})

    left, right, true = ingest._catch_left_right("CASE", "CASE-2")
    assert (left, right, true) == ("", "-2", "CASE")

    assert ingest_parsers._split_on_colon("NM:123") == "123"
    assert ingest_parsers._split_on_colon("NM_1") == "NM_1"

    out = ingest_parsers._split_on_ampersand({}, "A&B")
    assert out == {"A": 1, "B": 1}
    out = ingest_parsers._collect_dbsnp({}, "abc&rs1&rs2")
    assert sorted(out) == ["rs1", "rs2"]
    hot = ingest_parsers._collect_hotspots({"a": [None, "1", "1"], "b": []})
    assert hot == {"a": ["1"]}


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

    arr = [{"Feature": "A"}, {"Feature": "B"}]
    assert ingest_parsers._selected_transcript_removal(arr, "A") == [{"Feature": "B"}]
    assert ingest_parsers._refseq_no_version("NM_1.2") == "NM_1"

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
        {"EGFR": "NM_005228"},
    )
    assert src == "db"
    assert chosen["SYMBOL"] == "EGFR"


def test_next_unique_name(monkeypatch):
    stub = _store_stub([{"name": "CASE"}, {"name": "CASE-2"}])
    service = _use_store(monkeypatch, stub)

    with pytest.raises(ValueError):
        service._next_unique_name("CASE", increment=False)

    assert service._next_unique_name("NEW", increment=False) == "NEW"
    assert service._next_unique_name("CASE", increment=True) == "CASE-3"


def test_read_mane(tmp_path):
    gz = tmp_path / "mane.tsv.gz"
    import gzip

    with gzip.open(gz, "wt", encoding="utf-8") as handle:
        handle.write("RefSeq_nuc\tEnsembl_nuc\tEnsembl_Gene\n")
        handle.write("NM_1.1\tENST1.2\tENSG1.3\n")
    out = ingest_parsers._read_mane(str(gz))
    assert out["ENSG1"]["refseq"] == "NM_1"


def test_parse_yaml_payload():
    service = ingest.InternalIngestService(
        sample_collection=None,
        refseq_canonical_collection=_Col(),
        collections={},
        invalidate_variant_cache=lambda: None,
        invalidate_summary_cache=lambda: None,
    )
    parsed = service.parse_yaml_payload("name: S1\nassay: A\n")
    assert parsed["name"] == "S1"
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

    for p in [vcf, transloc]:
        p.write_text("x", encoding="utf-8")
    cnv.write_text(json.dumps({"k": {"ratio": 1}}), encoding="utf-8")
    bio.write_text(json.dumps({"name": "b"}), encoding="utf-8")
    cov.write_text(json.dumps({"genes": {}}), encoding="utf-8")
    fus.write_text(json.dumps([{"f": 1}]), encoding="utf-8")
    expr.write_text(json.dumps({"a": 1}), encoding="utf-8")
    cls.write_text(json.dumps({"c": 1}), encoding="utf-8")
    qc.write_text(json.dumps({"q": 1}), encoding="utf-8")

    parser = ingest.DnaIngestParser(canonical={})
    monkeypatch.setattr(parser, "_parse_snvs_only", lambda _: [{"CHROM": "1"}])
    monkeypatch.setattr(parser, "_parse_transloc_only", lambda _: [{"CHROM": "2"}])

    out = parser.parse(
        {
            "vcf_files": str(vcf),
            "cnv": str(cnv),
            "biomarkers": str(bio),
            "transloc": str(transloc),
            "cov": str(cov),
            "name": "S1",
        }
    )
    assert "snvs" in out and "cnvs" in out and "cov" in out and "transloc" in out

    rna = ingest.RnaIngestParser.parse(
        {
            "fusion_files": str(fus),
            "expression_path": str(expr),
            "classification_path": str(cls),
            "qc": str(qc),
        }
    )
    assert "fusions" in rna and "rna_expr" in rna and "rna_class" in rna and "rna_qc" in rna


def test_service_resolution_and_validation(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)

    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))
    out = service._normalize_collection_docs("variants", [{"a": 1}, {"b": 2}])
    assert out == [{"a": 1}, {"b": 2}]


def test_service_canonical_and_parse_preload(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)
    assert service._canonical_map() == {"EGFR": "NM_005228"}
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
        ingest,
        "ensure_variant_identity_fields",
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

    out2 = service.ingest_dependents(
        sample_id="sid",
        sample_name="S1",
        delete_existing=True,
        preload={"biomarkers": {"name": "b"}, "cnvs": [{"chr": "1"}]},
    )
    assert out2["biomarkers"] == 1 and out2["cnvs"] == 1


def test_snapshot_restore_replace_and_counts(monkeypatch):
    sid = "507f1f77bcf86cd799439014"
    cov_col = _Col([{"_id": "x", "SAMPLE_ID": str(sid), "a": 1}])
    stub = _store_stub()
    stub.coyote_db["panel_coverage"] = cov_col
    stub.coverage_handler = _Handler(cov_col)
    service = _use_store(monkeypatch, stub)

    snap = service._snapshot_dependents(sample_id=sid, keys={"cov"})
    assert "cov" in snap

    service._restore_dependents(
        sample_id=sid,
        sample_name="S1",
        backup={"cov": [{"_id": "x", "SAMPLE_ID": str(sid), "a": 1}]},
    )
    assert cov_col.inserted_many

    assert service._data_counts({"a": [1, 2], "b": {}}) == {
        "a": 2,
        "b": False,
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
        sample_collection=None,
        refseq_canonical_collection=_Col(),
        collections={},
        invalidate_variant_cache=lambda: None,
        invalidate_summary_cache=lambda: None,
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

    sample_col = _Col([{"_id": "id1", "name": "S1", "assay": "A", "x": 1}])
    stub = _store_stub()
    stub.sample_handler = _Handler(sample_col)
    service = _use_store(monkeypatch, stub)

    service._update_meta_fields(
        sample_id="id1",
        payload_meta={"name": "S1", "x": 2, "new_key": 3},
        block_fields={"assay"},
    )
    assert sample_col.updated

    with pytest.raises(ValueError):
        service._update_meta_fields(
            sample_id="id1",
            payload_meta={"assay": "B"},
            block_fields={"assay"},
        )


def test_ingest_update_and_ingest_sample_bundle(monkeypatch):
    sample_id = "507f1f77bcf86cd799439016"
    sample_col = _Col(
        [
            {
                "_id": sample_id,
                "name": "S1",
                "assay": "assay_1",
                "subpanel": "Hem",
                "profile": "production",
                "case_id": "CASE_DEMO",
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
    stub.sample_handler = _Handler(sample_col)
    service = _use_store(monkeypatch, stub)
    monkeypatch.setattr(
        service,
        "_prepare_update_payload",
        lambda sample_doc, payload: {
            "name": payload["name"],
            "assay": "assay_1",
            "subpanel": "Hem",
            "profile": "production",
            "case_id": "CASE_DEMO",
            "sample_no": 1,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
        },
    )
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
        "assay": "assay_1",
        "subpanel": "Hem",
        "profile": "production",
        "case_id": "CASE_DEMO",
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
    stub.sample_handler = _Handler(sample_col)
    service = _use_store(monkeypatch, stub, new_sample_id="507f1f77bcf86cd799439017")
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": []})
    monkeypatch.setattr(service, "_next_unique_name", lambda *_: "S1")
    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"snvs": 0})

    class _Valid:
        def model_dump(self, *args, **kwargs):
            _ = args, kwargs
            return {"name": "S1", "assay": "A", "case_id": "C", "sample_no": 1}

    monkeypatch.setattr(ingest.SamplesDoc, "model_validate", lambda _: _Valid())
    monkeypatch.setattr(
        ingest, "build_sample_meta_dict", lambda _: {"assay": "A", "case_id": "C", "sample_no": 1}
    )

    out = service.ingest_sample_bundle({"name": "S1"}, allow_update=False)
    assert out["status"] == "ok"

    monkeypatch.setattr(
        service, "_write_dependents", lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    cleaned = {"called": False}
    monkeypatch.setattr(service, "_cleanup", lambda _sid: cleaned.update(called=True))
    with pytest.raises(RuntimeError):
        service.ingest_sample_bundle({"name": "S2"}, allow_update=False)
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
