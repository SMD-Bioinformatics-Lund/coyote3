"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import coyote.application.dna.structural_variants as service_module
import pytest
from coyote.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote.application.dna.structural_variants import DnaStructuralService
from coyote.contracts.dna import DnaTranslocationsPayload
from coyote.domain.exceptions import AppError
from coyote_api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request


class _CnvHandlerStub:
    def __init__(self) -> None:
        self.sample_cnvs_payload = [{"_id": "cnv1", "SAMPLE_ID": "S1"}]
        self.cnv_doc: dict | None = {"_id": "cnv1", "SAMPLE_ID": "S1", "genes": []}

    def get_sample_cnvs(self, _query, *, stream=False):
        return self.sample_cnvs_payload

    def get_cnv(self, _cnv_id: str):
        return self.cnv_doc

    def get_cnv_annotations(self, _cnv: dict, *, sample_context):
        assert sample_context["environment"] == "production"
        return [{"annotation": "x"}]

    def hidden_cnv_comments(self, _cnv_id: str):
        return [{"text": "hidden"}]


class _TranslocHandlerStub:
    def __init__(self) -> None:
        self.doc: dict | None = {"_id": "t1", "SAMPLE_ID": "S1"}
        self.sample_translocations_payload = [{"_id": "t1", "SAMPLE_ID": "S1"}]

    def get_sample_translocations(self, _query=None, **_kwargs):
        return self.sample_translocations_payload

    def get_transloc(self, _transloc_id: str):
        return self.doc

    def get_transloc_annotations(self, _doc: dict, *, sample_context):
        assert sample_context["environment"] == "production"
        return [{"annotation": "t"}]

    def hidden_transloc_comments(self, _transloc_id: str):
        return True


class _RepoStub:
    def __init__(self) -> None:
        self.copy_number_variant_repository = _CnvHandlerStub()
        self.translocation_repository = _TranslocHandlerStub()
        self.asp_doc = {"_id": "WGS", "covered_genes": []}
        self.gene_lists: dict[str, dict] = {}
        self.assay_panel_repository = SimpleNamespace(get_asp=lambda **_kwargs: self.asp_doc)
        self.gene_list_repository = SimpleNamespace(
            get_isgl_by_ids=lambda ids: {
                list_id: self.gene_lists[list_id] for list_id in ids if list_id in self.gene_lists
            }
        )
        self.bam_record_repository = SimpleNamespace(
            get_bams=lambda sample_ids: {sid: [f"/{sid}.bam"] for sid in sample_ids.values()}
        )
        self.vep_metadata_repository = SimpleNamespace(
            get_conseq_translations=lambda _vep: {"A": "B"}
        )
        self.cosmic_repository = SimpleNamespace(
            get_cnv_evidence=lambda _cnv, **_kwargs: {"kind": "copy_number", "records": []},
            get_translocation_evidence=lambda _transloc, **_kwargs: {
                "kind": "translocation",
                "records": [],
            },
        )


def _sample() -> dict:
    return {
        "_id": "S1",
        "name": "sample1",
        "asp_id": "WGS",
        "environment": "production",
        "database_versions": {"vep": "103"},
        "analysis_intents": ["somatic"],
        "filters": {"somatic": {}},
        "files": {
            "cnvprofile": {
                "path": "/data/sample1.cnv.png",
                "size_bytes": 1024,
            }
        },
    }


def _release(repo: _RepoStub) -> dict:
    """Capture synthetic eligibility once for the structural workflow under test."""
    panel = {"asp_id": "WGS", "asp_group": "dna", **repo.asp_doc}
    return {
        "asp_id": "WGS",
        "asp_group": "dna",
        "filters": {},
        "assay_resource_release": capture_assay_resource(panel),
        "gene_list_release": capture_gene_lists(
            [{"isgl_id": key, "version": 1, **row} for key, row in repo.gene_lists.items()]
        ),
        "aspc_resolution": {
            "context": {
                "assay_id": "WGS",
                "group_id": "dna",
                "environment": "production",
                "diagnosis_id": "base",
            }
        },
    }


def _request(path: str):
    return SimpleNamespace(query_params={}, url=SimpleNamespace(path=path))


def _service_from_repo(repo: _RepoStub) -> DnaStructuralService:
    return DnaStructuralService(
        annotation_repository=SimpleNamespace(
            get_global_annotations=lambda *args, **kwargs: ([], None, [], {})
        ),
        copy_number_variant_repository=repo.copy_number_variant_repository,
        translocation_repository=repo.translocation_repository,
        assay_panel_repository=repo.assay_panel_repository,
        gene_list_repository=repo.gene_list_repository,
        bam_record_repository=repo.bam_record_repository,
        vep_metadata_repository=repo.vep_metadata_repository,
        cosmic_repository=repo.cosmic_repository,
    )


def test_list_cnvs_payload_uses_selected_cnvlists_for_effective_genes(monkeypatch):
    repo = _RepoStub()
    captured: dict[str, object] = {}

    repo.asp_doc["covered_genes"] = ["TP53"]
    repo.gene_lists = {"GL1": {"genes": ["TP53"], "is_active": True, "list_type": ["cnv"]}}
    repo.gene_list_repository = SimpleNamespace(
        get_isgl_by_ids=Mock(side_effect=AssertionError("Sample reads must use captured lists"))
    )
    service = DnaStructuralService(
        annotation_repository=SimpleNamespace(
            get_global_annotations=lambda *args, **kwargs: ([], None, [], {})
        ),
        copy_number_variant_repository=repo.copy_number_variant_repository,
        translocation_repository=repo.translocation_repository,
        assay_panel_repository=repo.assay_panel_repository,
        gene_list_repository=repo.gene_list_repository,
        bam_record_repository=repo.bam_record_repository,
        vep_metadata_repository=repo.vep_metadata_repository,
        cosmic_repository=repo.cosmic_repository,
    )
    sample = _sample()
    sample["filters"] = {"somatic": {"cnv": {"cnvlists": ["GL1"], "cnveffects": ["gain"]}}}

    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    def _load_cnvs_for_sample(**kwargs):
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(service, "load_cnvs_for_sample", _load_cnvs_for_sample)

    service.list_cnvs_payload(
        query=analysis_query_from_request(_request("/api/v1/cnvs/S1")), sample=sample
    )

    repo.gene_list_repository.get_isgl_by_ids.assert_not_called()
    assert captured["kwargs"]["filter_genes"] == ["TP53"]


def test_list_cnvs_payload_raises_when_assay_config_missing(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: None
    )

    with pytest.raises(AppError) as exc:
        service.list_cnvs_payload(
            query=analysis_query_from_request(_request("/api/v1/cnvs/S1")), sample=_sample()
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "ASPC could not be resolved for the sample"
    assert exc.value.detail["category"] == "setup"


def test_list_cnvs_payload_returns_count(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )
    monkeypatch.setattr(
        service, "load_cnvs_for_sample", lambda **_: [{"_id": "cnv1"}, {"_id": "cnv2"}]
    )

    payload = service.list_cnvs_payload(
        query=analysis_query_from_request(_request("/api/v1/cnvs/S1")), sample=_sample()
    )

    assert payload["meta"]["count"] == 2
    assert payload["sample"]["id"] == "S1"
    assert payload["sample"]["files"]["cnvprofile"]["path"] == "/data/sample1.cnv.png"


def test_list_translocations_payload_returns_count(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )
    payload = service.list_translocations_payload(
        query=analysis_query_from_request(_request("/api/v1/translocations/S1")), sample=_sample()
    )
    assert payload["meta"]["count"] == 0
    assert "snpeff_conseq_translations" in payload
    DnaTranslocationsPayload.model_validate(payload)
    assert "vep_conseq_translations" not in payload


def test_structural_display_does_not_require_vep_metadata(monkeypatch):
    """Use embedded SnpEff terms even when the sample has no VEP version."""
    repo = _RepoStub()
    service = _service_from_repo(repo)
    service.vep_metadata_repository.get_conseq_translations = Mock(
        side_effect=AssertionError("DNA structural consequences must not use VEP")
    )
    sample = _sample()
    sample.pop("database_versions")
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _, **kwargs: _release(repo)
    )
    assert "snpeff_conseq_translations" in service.list_translocations_payload(
        query=analysis_query_from_request(_request("/api/v1/translocations/S1")), sample=sample
    )
    assert "snpeff_conseq_translations" in service.show_translocation_payload(
        sample=sample, transloc_id="t1"
    )


def test_list_translocations_uses_selected_translocation_list(monkeypatch):
    repo = _RepoStub()
    repo.asp_doc = {"_id": "WGS", "covered_genes": ["KMT2A", "NPM1"]}
    repo.gene_lists = {
        "STRUCTURAL": {
            "displayname": "Structural genes",
            "is_active": True,
            "list_type": ["snv", "cnv", "fusion"],
            "genes": ["KMT2A"],
        }
    }
    repo.translocation_repository.sample_translocations_payload = [
        {
            "_id": "keep",
            "SAMPLE_ID": "S1",
            "INFO": {"MANE_ANN": {"Gene_Name": "KMT2A"}},
        },
        {"_id": "drop", "SAMPLE_ID": "S1", "gene1": "NPM1", "gene2": "ALK"},
    ]
    sample = _sample()
    sample["filters"] = {"somatic": {"translocation": {"fusionlists": ["STRUCTURAL"]}}}
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        query=analysis_query_from_request(_request("/api/v1/translocations/S1")),
        sample=sample,
    )

    assert [row["_id"] for row in payload["translocations"]] == ["keep"]


def test_list_translocations_falls_back_to_asp_covered_genes(monkeypatch):
    repo = _RepoStub()
    repo.asp_doc = {"_id": "WGS", "covered_genes": ["NPM1"]}
    repo.translocation_repository.sample_translocations_payload = [
        {"_id": "keep", "SAMPLE_ID": "S1", "gene1": "NPM1"},
        {"_id": "drop", "SAMPLE_ID": "S1", "gene1": "KMT2A"},
    ]
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        query=analysis_query_from_request(_request("/api/v1/translocations/S1")),
        sample=_sample(),
    )

    assert [row["_id"] for row in payload["translocations"]] == ["keep"]


def test_list_translocations_returns_none_without_resolved_scope(monkeypatch):
    repo = _RepoStub()
    repo.translocation_repository.sample_translocations_payload = [
        {"_id": "one", "SAMPLE_ID": "S1", "gene1": "NPM1"},
        {"_id": "two", "SAMPLE_ID": "S1", "gene1": "KMT2A"},
    ]
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        query=analysis_query_from_request(_request("/api/v1/translocations/S1")),
        sample=_sample(),
    )

    assert payload["translocations"] == []


def test_cnv_list_search_sort_and_unpaginated_metadata(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    rows = [
        {"_id": "b", "chr": "2", "genes": [{"gene": "BRAF"}]},
        {"_id": "a", "chr": "1", "genes": [{"gene": "ALK"}]},
    ]
    monkeypatch.setattr(
        service, "_get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )
    monkeypatch.setattr(service, "load_cnvs_for_sample", lambda **_kwargs: rows)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/samples/S1/cnvs"),
        query_params={"q": "BRAF", "sort": "genes:desc"},
    )

    payload = service.list_cnvs_payload(
        query=analysis_query_from_request(request),
        sample=_sample(),
        paginate=False,
    )

    assert [row["_id"] for row in payload["cnvs"]] == ["b"]
    assert payload["meta"]["search"] == "BRAF"
    assert payload["meta"]["sort"] == "genes:desc"
    assert payload["meta"]["page_count"] == 1


def test_translocation_list_search_sort_and_pagination(monkeypatch):
    repo = _RepoStub()
    repo.asp_doc["covered_genes"] = ["NTRK1", "ALK"]
    repo.translocation_repository.sample_translocations_payload = [
        {"_id": "b", "SAMPLE_ID": "S1", "gene1": "NTRK1", "gene2": "TPM3"},
        {"_id": "a", "SAMPLE_ID": "S1", "gene1": "ALK", "gene2": "EML4"},
    ]
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service, "_get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/samples/S1/translocations"),
        query_params={"q": "NTRK1", "sort": "gene1:asc", "page": "1", "per_page": "1"},
    )

    payload = service.list_translocations_payload(
        query=analysis_query_from_request(request), sample=_sample()
    )

    assert [row["_id"] for row in payload["translocations"]] == ["b"]
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["sort"] == "gene1:asc"
