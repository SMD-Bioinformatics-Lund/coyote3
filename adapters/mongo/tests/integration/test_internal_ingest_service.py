"""Unit tests for internal ingestion service helpers and orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import coyote.application.ingest.service as ingest
import pytest
from coyote.application.common.release_resources import capture_assay_resource
from coyote.application.ingest.analysis_parsers import DnaIngestParser, RnaIngestParser
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.settings import audit_context
from mongo_test_support.writes import repository_writes  # noqa: F401

pytestmark = pytest.mark.usefixtures("repository_writes")


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
        "d4_coverage": _Col(),
        "d4_coverage_blacklist": _Col(),
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
                    "diagnosis_id": "Hem",
                    "environment": "production",
                    "is_active": True,
                    "analysis_types": [],
                    "filters": {},
                },
                {
                    "_id": "aspc-a",
                    "aspc_id": "A:production:base",
                    "asp_id": "A",
                    "diagnosis_id": "base",
                    "environment": "production",
                    "is_active": True,
                    "analysis_types": [],
                    "filters": {},
                },
            ]
        ),
        "assay_groups": _Col([{"group_id": "hematology", "is_active": True}]),
        "assay_specific_panels": _Col(
            [
                {
                    "is_active": True,
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
                    "asp_id": "a",
                    "is_active": True,
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
        d4_coverage_repository=_Handler(db["d4_coverage"]),
        d4_coverage_blacklist_repository=_Handler(db["d4_coverage_blacklist"]),
        fusion_repository=_Handler(db["fusions"]),
        rna_expression_repository=_Handler(db["rna_expression"]),
        rna_classification_repository=_Handler(db["rna_classification"]),
        rna_quality_repository=_Handler(db["rna_qc"]),
        anno_vep_repository=anno_vep_repository,
        coyote_db=db,
    )


def _use_store(monkeypatch, store_stub, *, new_sample_id="507f1f77bcf86cd799439011"):
    for panel in store_stub.coyote_db["assay_specific_panels"].docs:
        panel.setdefault("version", 1)
    for configuration in store_stub.coyote_db["asp_configs"].docs:
        configuration.setdefault("version", 1)
        configuration.setdefault("asp_group", "hematology")
        configuration.setdefault("analysis_intents", ["somatic"])
        panel = next(
            (
                panel
                for panel in store_stub.coyote_db["assay_specific_panels"].docs
                if panel["asp_id"] == configuration["asp_id"].lower()
            ),
            None,
        )
        if panel is not None:
            configuration["assay_resource_release"] = capture_assay_resource(panel)
    monkeypatch.setattr(
        "coyote_mongo.repositories.ingest_gateway.to_provider_id", lambda sample_id: sample_id
    )
    monkeypatch.setattr(
        IngestCollectionGateway, "new_sample_id", staticmethod(lambda: new_sample_id)
    )
    monkeypatch.setattr(
        IngestCollectionGateway, "run_transaction", lambda self, operation: operation(None)
    )
    monkeypatch.setattr(
        "coyote_mongo.persistence.run_transaction", lambda client, operation: operation(None)
    )
    return ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            context=audit_context(),
            collections={
                "samples": store_stub.sample_repository.get_collection(),
                "variants": store_stub.variant_repository.get_collection(),
                "cnvs": store_stub.copy_number_variant_repository.get_collection(),
                "biomarkers": store_stub.biomarker_repository.get_collection(),
                "translocations": store_stub.translocation_repository.get_collection(),
                "d4_coverage": store_stub.d4_coverage_repository.get_collection(),
                "fusions": store_stub.fusion_repository.get_collection(),
                "rna_expression": store_stub.rna_expression_repository.get_collection(),
                "rna_classification": store_stub.rna_classification_repository.get_collection(),
                "rna_qc": store_stub.rna_quality_repository.get_collection(),
                "asp_configs": store_stub.coyote_db["asp_configs"],
                "assay_specific_panels": store_stub.coyote_db["assay_specific_panels"],
                "assay_groups": store_stub.coyote_db["assay_groups"],
                "hgnc_genes": store_stub.coyote_db["hgnc_genes"],
                "anno_vep": store_stub.coyote_db["anno_vep"],
            },
        ),
        anno_vep_repository=store_stub.anno_vep_repository,
        invalidate_dashboard_metrics=lambda: None,
    )


def test_collection_document_count_reports_supported_collection_occupancy(monkeypatch):
    store_stub = _store_stub(sample_docs=[{"_id": "sample-1", "name": "sample_one"}])
    service = _use_store(monkeypatch, store_stub)

    assert service.collection_document_count("samples") == 1
    assert service.collection_document_count("variants") == 0

    with pytest.raises(ValueError, match="Unsupported collection"):
        service.collection_document_count("not_a_collection")


def test_assay_file_policy_normalizes_pipeline_asp_identifier(monkeypatch):
    store_stub = _store_stub()
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "asp_id": "hema_gmsv1",
            "asp_group": "hematology",
            "is_active": True,
            "asp_category": "dna",
            "expected_files": ["vcf_files", "cnv"],
            "required_files": ["vcf_files"],
        }
    ]
    service = _use_store(monkeypatch, store_stub)

    expected, required = service._assay_file_policy(
        assay_name="hema_GMSv1",
        asp_category="DNA",
    )

    assert expected == {"vcf_files", "cnv"}
    assert required == {"vcf_files"}


def test_ingest_rejects_file_keys_outside_asp_expected_files(monkeypatch, tmp_path):
    store_stub = _store_stub()
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "is_active": True,
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
        "asp_family": "panel-dna",
        "asp_category": "dna",
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


@pytest.mark.parametrize("declared", [True, False])
def test_ingest_proceeds_with_missing_expected_files(monkeypatch, tmp_path, caplog, declared):
    store_stub = _store_stub()
    store_stub.coyote_db["asp_configs"].docs = [
        {
            "_id": "aspc-1",
            "aspc_id": "assay_1_base_production",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
            "environment": "production",
            "is_active": True,
            "analysis_types": ["SNV", "TRANSLOCATION"],
            "filters": {},
        }
    ]
    store_stub.coyote_db["assay_specific_panels"].docs = [
        {
            "asp_id": "assay_1",
            "is_active": True,
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
        "asp_family": "panel-dna",
        "asp_category": "dna",
        "pipeline": "SomaticPanelPipeline",
        "pipeline_version": "1.0.0",
        "vcf_files": str(vcf_path),
        "transloc": str(tmp_path / "missing.annotated.vcf"),
    }

    if not declared:
        payload.pop("transloc")
    parser_inputs = []
    audit_events = []
    notifications = []
    groups = []
    service.audit_service = SimpleNamespace(
        record=lambda *args, **kw: audit_events.append((args, kw))
    )
    service.notification_service = SimpleNamespace(
        user_repository=SimpleNamespace(
            list_active_users_for_notifications=lambda **kw: (
                groups.append(kw) or [{"username": "monitor_user"}]
            )
        ),
        create_notification=lambda **kw: notifications.append(kw),
    )
    monkeypatch.setattr(
        service, "_parse_preload", lambda data: parser_inputs.append(data) or {"snvs": []}
    )
    result = service.ingest_sample_bundle(payload)
    assert result["status"] == "ok"
    assert result["missing_expected_files"] == ["transloc"]
    saved = service.collection_gateway.sample_collection().inserted_one[-1]
    assert saved["missing_expected_files"] == ["transloc"]
    assert ("transloc" in saved["files"]) == declared
    assert "transloc" not in parser_inputs[0].get("files", {})
    assert "translocations" not in result["data_counts"]
    assert audit_events[0][0][0] == "ingest.expected_files_missing"
    assert audit_events[0][1]["outcome"] == "warning"
    assert groups == [{"role_ids": ["monitoring_group"]}]
    assert notifications[0]["recipients"] == ["monitor_user"]
    assert "transloc" in notifications[0]["message"]
    assert any(
        getattr(record, "event_type", None) == "ingest.expected_files_missing"
        for record in caplog.records
    )
    transloc_path = tmp_path / "available.vcf"
    transloc_path.write_text("synthetic")
    payload["transloc"] = str(transloc_path)
    monkeypatch.setattr(service, "_parse_preload", lambda data: {"snvs": [], "transloc": []})
    updated = service.ingest_sample_bundle(payload, allow_update=True)
    assert updated["missing_expected_files"] == []
    assert updated["data_counts"]["transloc"] == 0
    assert len(notifications) == 1
    assert any(
        update["$set"].get("missing_expected_files") == []
        for _, update, _ in service.collection_gateway.sample_collection().updated
    )


def test_aspc_enabled_analysis_does_not_add_asp_file_requirements(tmp_path, monkeypatch):
    store_stub = _store_stub()
    store_stub.coyote_db["asp_configs"].docs = [
        {
            "_id": "aspc-1",
            "aspc_id": "assay_1_base_production",
            "asp_id": "assay_1",
            "diagnosis_id": "base",
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
            "asp_category": "dna",
            "vcf_files": str(vcf_path),
        }
    )

    service._validate_declared_file_resources(payload)


def test_next_unique_name(monkeypatch):
    stub = _store_stub([{"name": "CASE"}, {"name": "CASE-2"}])
    service = _use_store(monkeypatch, stub)

    with pytest.raises(ValueError):
        service._next_unique_name("CASE", increment=False)

    assert service._next_unique_name("NEW", increment=False) == "NEW"
    assert service._next_unique_name("CASE", increment=True) == "CASE-3"


def test_duplicate_is_rejected_before_analysis_processing(monkeypatch):
    service = _use_store(monkeypatch, _store_stub([{"name": "CASE"}]))
    monkeypatch.setattr(
        service,
        "_validate_payload_file_keys",
        lambda *_: pytest.fail("File policy ran before duplicate check"),
    )
    monkeypatch.setattr(
        service, "_parse_preload", lambda *_: pytest.fail("Analysis files were parsed")
    )
    with pytest.raises(ValueError, match="increment=true"):
        service.ingest_sample_bundle({"name": "CASE"})
    service.preflight_sample_name({"name": "CASE"}, increment=True)
    service.preflight_sample_name({"name": "CASE"}, allow_update=True)


def test_parse_yaml_payload():
    service = ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            context=audit_context(), collections={"samples": _Col(), "anno_vep": _Col()}
        ),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_metrics=lambda: None,
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
        "name: S1\nassay: hema_GMSv1\ndiagnosis: Hem\nprofile: production\n"
        "sequencing_technology: Illumina\n"
    )
    assert parsed["asp_id"] == "hema_GMSv1"
    assert parsed["diagnosis_id"] == "Hem"
    assert parsed["environment"] == "production"
    assert parsed["platform"] == "Illumina"
    assert "assay" not in parsed

    parsed = service.parse_yaml_payload(
        "diagnosis: Hem\nname: SAMPLE_1\nclarity_case_id: CASE_CLARITY\n"
        "clarity_control_id: CONTROL_CLARITY\ngenome_build: 38\n"
        "vcf_files: /srv/coyote4-data/case.vcf\nsample_no: 2\n"
        "case_id: CASE_1\ncontrol_id: CONTROL_1\nprofile: production\n"
        "assay: hema_GMSv1\nsequencing_scope: panel\nomics_layer: DNA\n"
        "sequencing_technology: Illumina\npipeline: SomaticPanelPipeline\n"
        "pipeline_version: 3.2.0\ncase_purity: null\ncontrol_purity: 'null'\n"
        "paired: true\ncnv: /srv/coyote4-data/case.cnvs.json\n"
        "cnvprofile: /srv/coyote4-data/case.profile.png\n"
        "cov: /srv/coyote4-data/case.coverage.json\n"
    )
    assert parsed["asp_id"] == "hema_GMSv1"
    assert parsed["diagnosis_id"] == "Hem"
    assert parsed["environment"] == "production"
    assert parsed["platform"] == "Illumina"
    assert parsed["vcf_files"] == "/srv/coyote4-data/case.vcf"
    assert parsed["cnv"] == "/srv/coyote4-data/case.cnvs.json"
    assert parsed["cnvprofile"] == "/srv/coyote4-data/case.profile.png"
    assert parsed["cov"] == "/srv/coyote4-data/case.coverage.json"
    assert parsed["case_purity"] is None
    assert parsed["control_purity"] is None

    with pytest.raises(ValueError, match="conflicting values"):
        service.parse_yaml_payload("name: S1\nassay: assay_a\nasp_id: assay_b\n")

    with pytest.raises(ValueError):
        service.parse_yaml_payload("- 1\n- 2\n")


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

    monkeypatch.setattr(DnaIngestParser, "parse", lambda self, args: {"snvs": [args]})
    assert "snvs" in service._parse_preload({"asp_category": "dna", "vcf_files": "x"})

    monkeypatch.setattr(RnaIngestParser, "parse", lambda args: {"fusions": [args]})
    assert "fusions" in service._parse_preload({"asp_category": "rna", "fusion_files": "x"})

    with pytest.raises(ValueError):
        service._parse_preload({})


def test_write_and_ingest_dependents(monkeypatch):
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)
    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))
    monkeypatch.setattr(
        "coyote.application.ingest.dependent_writes.ensure_variant_identity_fields",
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


def test_replace_declared_dependents_and_counts(monkeypatch):
    sid = "507f1f77bcf86cd799439014"
    cov_col = _Col([{"_id": "x", "SAMPLE_ID": str(sid), "a": 1}])
    stub = _store_stub()
    stub.coyote_db["d4_coverage"] = cov_col
    stub.d4_coverage_repository = _Handler(cov_col)
    service = _use_store(monkeypatch, stub)

    assert service._data_counts({"snvs": [1, 2], "cov": {}, "anno_vep": [1]}) == {
        "snvs": 2,
        "cov": False,
    }

    monkeypatch.setattr(service, "_write_dependents", lambda **_: {"x": 1})
    out = service._replace_dependents(
        preload={"cov": {"genes": {}}}, sample_id=sid, sample_name="S1", session=None
    )
    assert out["x"] == 1


def test_replace_dependents_propagates_failure_to_transaction(monkeypatch):
    sid = "507f1f77bcf86cd799439015"
    stub = _store_stub()
    service = _use_store(monkeypatch, stub)

    monkeypatch.setattr(
        service, "_write_dependents", lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(RuntimeError):
        service._replace_dependents(
            preload={"snvs": []}, sample_id=sid, sample_name="S1", session=None
        )


def test_update_payload_guard_and_meta_update(monkeypatch):
    service = ingest.InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            context=audit_context(), collections={"samples": _Col(), "anno_vep": _Col()}
        ),
        anno_vep_repository=_AnnoVepRepo(),
        invalidate_dashboard_metrics=lambda: None,
    )
    out = service._prepare_update_payload(
        sample_doc={"asp_category": "rna", "fusion_files": "x"},
        payload={"name": "S1"},
    )
    assert out["asp_category"] == "rna"

    with pytest.raises(ValueError):
        service._prepare_update_payload(
            sample_doc={"asp_category": "rna", "fusion_files": "x"},
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
                "version": 1,
                "name": "S1",
                "asp_id": "assay_1",
                "diagnosis_id": "Hem",
                "environment": "production",
                "case_id": "seed_case",
                "sample_no": 1,
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "pipeline": "SomaticPanelPipeline",
                "pipeline_version": "1.0.0",
                "vcf_files": "x",
                "ingested_by": "original.submitter",
                "ingest_source": "upload",
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
            "diagnosis_id": "Hem",
            "environment": "production",
            "case_id": "seed_case",
            "sample_no": 1,
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "case_ffpe": False,
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "1.0.0",
            "vcf_files": "x",
            "ingested_by": "forged.submitter",
            "ingest_source": "watcher",
        },
    )
    monkeypatch.setattr(service, "_validate_declared_file_resources", lambda _payload: set())
    monkeypatch.setattr(service, "_parse_preload", lambda _: {"snvs": [{"a": 1}]})
    monkeypatch.setattr(service, "_replace_dependents", lambda **_: {"snvs": 1})
    metadata_updates = []
    monkeypatch.setattr(
        service, "_update_meta_fields", lambda **kwargs: metadata_updates.append(kwargs)
    )

    out = service._ingest_update({"name": "S1", "asp_id": "assay_1", "environment": "production"})
    assert out["status"] == "ok"
    assert metadata_updates[0]["payload_meta"]["ingested_by"] == "original.submitter"
    assert metadata_updates[0]["payload_meta"]["ingest_source"] == "upload"

    with pytest.raises(ValueError):
        service._ingest_update({"name": "MISSING"})

    with pytest.raises(ValueError):
        service.ingest_sample_bundle({}, allow_update=False)

    monkeypatch.setattr(service, "_ingest_update", lambda _, **kwargs: {"status": "ok"})
    update_payload = {
        "name": "S1",
        "asp_id": "assay_1",
        "diagnosis_id": "Hem",
        "environment": "production",
        "case_id": "seed_case",
        "sample_no": 1,
        "asp_family": "panel-dna",
        "asp_category": "dna",
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
        {"name": "S1", "asp_id": "A", "asp_category": "dna"}, allow_update=False
    )
    assert out["status"] == "ok"

    monkeypatch.setattr(
        service, "_write_dependents", lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    with pytest.raises(RuntimeError):
        service.ingest_sample_bundle(
            {"name": "S2", "asp_id": "A", "asp_category": "dna"}, allow_update=False
        )
    assert not hasattr(service, "_cleanup")

    monkeypatch.setattr(ingest, "normalize_collection_document", lambda _c, doc: dict(doc))

    one = service.insert_collection_document(collection="variants", document={"a": 1})
    assert one["inserted_count"] == 1

    many = service.insert_collection_documents(
        collection="variants", documents=[{"a": 1}, {"b": 2}]
    )
    assert many["inserted_count"] == 2

    zero = service.insert_collection_documents(collection="variants", documents=[])
    assert zero["inserted_count"] == 0


@pytest.mark.parametrize("bam,bai", [(None, None), ("/case.bam", "/index.bai")])
def test_ingest_sample_bundle_persists_meaningful_null_metadata(monkeypatch, bam, bai):
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
            "diagnosis_id": "base",
            "environment": "production",
            "case_id": "C2",
            "case_bam": bam,
            "case_bai": bai,
            "sample_no": 1,
            "paired": False,
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "not provided",
            "files": {"vcf_files": {"path": "x"}},
            "ingested_by": "forged.actor",
            "ingest_source": "watcher",
        },
        ingested_by="synthetic.submitter",
        ingest_source="upload",
    )

    assert result["status"] == "ok"
    inserted = sample_col.inserted_one[0]
    assert inserted["ingested_by"] == "synthetic.submitter"
    assert inserted["ingest_source"] == "upload"
    assert inserted["pipeline_version"] is None
    assert inserted["control"] is None
    assert inserted["case"]["purity"] is None
    assert inserted["case"]["bam"] == (bam or "")
    assert inserted["case"]["bai"] == (bai or "")
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
            "aspc_id": "assay_1_hem_production",
            "analysis_types": ["SNV", "CNV"],
            "diagnosis_id": "hem",
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
            "diagnosis_id": "hem",
            "environment": "production",
            "case_id": "seed_case",
            "sample_no": 1,
            "asp_family": "panel-dna",
            "asp_category": "dna",
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
