"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.services.dna_structural_service as service_module
from api.services.dna_structural_service import DnaStructuralService


class _CnvHandlerStub:
    def __init__(self) -> None:
        self.sample_cnvs_payload = [{"_id": "cnv1", "SAMPLE_ID": "S1"}]
        self.cnv_doc: dict | None = {"_id": "cnv1", "SAMPLE_ID": "S1", "genes": []}

    def get_sample_cnvs(self, _query):
        return self.sample_cnvs_payload

    def get_cnv(self, _cnv_id: str):
        return self.cnv_doc

    def get_cnv_annotations(self, _cnv: dict):
        return [{"annotation": "x"}]

    def hidden_cnv_comments(self, _cnv_id: str):
        return [{"text": "hidden"}]


class _TranslocHandlerStub:
    def __init__(self) -> None:
        self.doc: dict | None = {"_id": "t1", "SAMPLE_ID": "S1"}

    def get_sample_translocations(self, sample_id: str):
        return [{"_id": "t1", "SAMPLE_ID": sample_id}]

    def get_transloc(self, _transloc_id: str):
        return self.doc

    def get_transloc_annotations(self, _doc: dict):
        return [{"annotation": "t"}]

    def hidden_transloc_comments(self, _transloc_id: str):
        return [{"text": "hidden"}]


class _RepoStub:
    def __init__(self) -> None:
        self.cnv_handler = _CnvHandlerStub()
        self.transloc_handler = _TranslocHandlerStub()
        self.asp_handler = SimpleNamespace(get_asp=lambda asp_name: {"_id": asp_name})
        self.isgl_handler = SimpleNamespace(get_isgl_by_ids=lambda ids: {i: [] for i in ids})
        self.bam_service_handler = SimpleNamespace(get_bams=lambda sample_ids: {"ids": sample_ids})
        self.vep_meta_handler = SimpleNamespace(get_conseq_translations=lambda _vep: {"A": "B"})


class _UtilModule:
    common = SimpleNamespace(
        merge_sample_settings_with_assay_config=lambda sample, _cfg: sample,
        get_sample_effective_genes=lambda sample, _panel, _checked: ({"genes": []}, ["TP53"]),
        get_case_and_control_sample_ids=lambda _sample: ["S1", "S2"],
    )


def _sample() -> dict:
    return {"_id": "S1", "name": "sample1", "assay": "WGS", "profile": "production", "filters": {}}


def _request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path))


def test_mutation_payload_shape():
    payload = DnaStructuralService.mutation_payload("S1", "cnv", "c1", "update")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["meta"]["status"] == "updated"


def test_load_cnvs_for_sample_applies_query_and_filter(monkeypatch):
    repo = _RepoStub()
    service = DnaStructuralService(repository=repo)
    monkeypatch.setattr(
        service_module,
        "build_cnv_query",
        lambda sample_id, filters: {"sample": sample_id, **filters},
    )
    monkeypatch.setattr(service_module, "create_cnveffectlist", lambda effects: effects)
    monkeypatch.setattr(
        service_module, "cnvtype_variant", lambda cnvs, effects: cnvs + [{"effects": effects}]
    )
    monkeypatch.setattr(service_module, "cnv_organizegenes", lambda cnvs: cnvs)

    cnvs = service.load_cnvs_for_sample(
        sample=_sample(), sample_filters={"cnveffects": ["gain"]}, filter_genes=["TP53"]
    )

    assert len(cnvs) == 2
    assert cnvs[1]["effects"] == ["gain"]


def test_list_cnvs_payload_raises_when_assay_config_missing(monkeypatch):
    service = DnaStructuralService(repository=_RepoStub())
    monkeypatch.setattr(service_module, "get_formatted_assay_config", lambda _sample: None)

    with pytest.raises(HTTPException) as exc:
        service.list_cnvs_payload(
            request=_request("/api/v1/cnvs/S1"), sample=_sample(), util_module=_UtilModule
        )

    assert exc.value.status_code == 404


def test_list_cnvs_payload_returns_count(monkeypatch):
    repo = _RepoStub()
    service = DnaStructuralService(repository=repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )
    monkeypatch.setattr(
        service, "load_cnvs_for_sample", lambda **_: [{"_id": "cnv1"}, {"_id": "cnv2"}]
    )

    payload = service.list_cnvs_payload(
        request=_request("/api/v1/cnvs/S1"), sample=_sample(), util_module=_UtilModule
    )

    assert payload["meta"]["count"] == 2
    assert payload["sample"]["id"] == "S1"


def test_show_cnv_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.cnv_handler.cnv_doc = {"_id": "cnv1", "SAMPLE_ID": "S2"}
    service = DnaStructuralService(repository=repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    with pytest.raises(HTTPException) as exc:
        service.show_cnv_payload(sample=_sample(), cnv_id="cnv1", util_module=_UtilModule)

    assert exc.value.status_code == 404


def test_show_cnv_payload_returns_detail(monkeypatch):
    repo = _RepoStub()
    service = DnaStructuralService(repository=repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    payload = service.show_cnv_payload(sample=_sample(), cnv_id="cnv1", util_module=_UtilModule)

    assert payload["sample_summary"]["assay_group"] == "dna"
    assert payload["has_hidden_comments"]


def test_list_translocations_payload_returns_count():
    service = DnaStructuralService(repository=_RepoStub())
    payload = service.list_translocations_payload(
        request=_request("/api/v1/translocations/S1"), sample=_sample()
    )
    assert payload["meta"]["count"] == 1


def test_show_translocation_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.transloc_handler.doc = {"_id": "t1", "SAMPLE_ID": "S2"}
    service = DnaStructuralService(repository=repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    with pytest.raises(HTTPException) as exc:
        service.show_translocation_payload(
            sample=_sample(), transloc_id="t1", util_module=_UtilModule
        )

    assert exc.value.status_code == 404


def test_show_translocation_payload_returns_detail(monkeypatch):
    service = DnaStructuralService(repository=_RepoStub())
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    payload = service.show_translocation_payload(
        sample=_sample(), transloc_id="t1", util_module=_UtilModule
    )

    assert payload["translocation"]["_id"] == "t1"
    assert payload["vep_conseq_translations"] == {"A": "B"}
