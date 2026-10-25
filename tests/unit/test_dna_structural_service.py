"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import coyote3.application.dna.structural_variants as service_module
from api.infra.mongo.selection import compile_selection
from api.interfaces.http.v1.clinical.common.analysis_query import analysis_query_from_request
from coyote3.application.common.change_payload import change_payload
from coyote3.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote3.application.dna.structural_variants import DnaStructuralService
from coyote3.contracts.dna import DnaTranslocationContextPayload, DnaTranslocationsPayload
from coyote3.domain.exceptions import AppError


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


class _UtilModule:
    common = SimpleNamespace(
        merge_sample_settings_with_assay_config=lambda sample, _cfg: sample,
        get_sample_effective_genes=lambda sample, _panel, _checked, target="snv": (
            {"genes": []},
            ["TP53"],
        ),
        get_case_and_control_sample_ids=lambda _sample: {"case": "S1", "control": "S2"},
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


def test_change_payload_shape():
    payload = change_payload(sample_id="S1", resource="cnv", resource_id="c1", action="update")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["meta"]["status"] == "updated"


def test_load_cnvs_for_sample_applies_query_and_filter(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module,
        "build_cnv_query",
        lambda sample_id, filters, include_normal=False, policy=None: {
            "sample": sample_id,
            "include_normal": include_normal,
            **filters,
        },
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


def test_show_cnv_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.copy_number_variant_repository.cnv_doc = {"_id": "cnv1", "SAMPLE_ID": "S2"}
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    with pytest.raises(AppError) as exc:
        service.show_cnv_payload(sample=_sample(), cnv_id="cnv1")

    assert exc.value.status_code == 404


def test_show_cnv_payload_returns_detail(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    payload = service.show_cnv_payload(sample=_sample(), cnv_id="cnv1")

    assert payload["sample_summary"]["assay_group"] == "dna"
    assert payload["has_hidden_comments"]


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


def test_show_translocation_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.translocation_repository.doc = {"_id": "t1", "SAMPLE_ID": "S2"}
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    with pytest.raises(AppError) as exc:
        service.show_translocation_payload(sample=_sample(), transloc_id="t1")

    assert exc.value.status_code == 404


def test_show_translocation_payload_returns_detail(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample, **kwargs: _release(repo)
    )

    payload = service.show_translocation_payload(sample=_sample(), transloc_id="t1")

    assert payload["translocation"]["_id"] == "t1"
    DnaTranslocationContextPayload.model_validate(payload)
    assert "snpeff_conseq_translations" in payload
    assert "vep_conseq_translations" not in payload


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [(None, None), ("invalid", None), (0, 2.0), (1, 4.0)],
)
def test_cnv_copy_number_handles_missing_invalid_and_numeric_ratios(ratio, expected):
    assert service_module._cnv_copy_number({"ratio": ratio}) == expected


def test_cnv_table_value_helpers_cover_supported_columns():
    cnv = {
        "_id": "cnv-1",
        "chr": "7",
        "start": "10",
        "end": 20,
        "ratio": 1,
        "callers": ["MANTA", "CNVKIT"],
        "genes": [{"gene": "BRAF"}, "ignored", {"gene": "KIAA1549"}],
        "SR": "4,9",
        "fp": True,
        "interesting": False,
        "noteworthy": True,
        "NORMAL": False,
        "AFRQ_a": "0.2",
        "AFRQ_b": 0.7,
    }

    assert service_module._cnv_gene_text(cnv) == "BRAF KIAA1549"
    assert service_module._cnv_gene_text({"genes": "BRAF"}) == ""
    assert service_module._cnv_sort_value(cnv, "genes") == "braf kiaa1549"
    assert service_module._cnv_sort_value(cnv, "region") == ("7", 10.0, 20.0)
    assert service_module._cnv_sort_value(cnv, "callers") == "manta, cnvkit"
    assert service_module._cnv_sort_value({"callers": "MANTA"}, "callers") == "manta"
    assert service_module._cnv_sort_value(cnv, "copy_number") == 4.0
    assert service_module._cnv_sort_value(cnv, "purity") == 4.0
    assert service_module._cnv_sort_value(cnv, "sr") == "4,9"
    assert "true" in service_module._cnv_sort_value(cnv, "status")
    assert service_module._cnv_sort_value(cnv, "artefact") == 0.7
    assert service_module._cnv_sort_value(cnv, "unsupported") is None
    assert "BRAF KIAA1549" in service_module._cnv_search_text(cnv)


def test_translocation_table_value_helpers_cover_supported_columns():
    translocation = {
        "_id": "t-1",
        "gene1": "NTRK1",
        "gene2": "TPM3",
        "fp": False,
        "interesting": True,
        "POS": "1:10-1:20",
        "SVTYPE": "fusion",
        "annotations": ["p.Ala1Val", "frameshift"],
        "in_panel": "intersection",
        "classification": "2",
        "breakpoints": "1:10,1:20",
        "HGVS": "t(1;1)",
    }

    assert "true" in service_module._translocation_sort_value(translocation, "badges")
    assert service_module._translocation_sort_value(translocation, "gene1") == "ntrk1"
    assert service_module._translocation_sort_value(translocation, "gene2") == "tpm3"
    assert service_module._translocation_sort_value(translocation, "positions") == "1:10-1:20"
    assert service_module._translocation_sort_value(translocation, "type") == "fusion"
    assert service_module._translocation_sort_value(translocation, "hgvs") == "p.ala1val frameshift"
    assert service_module._translocation_sort_value(translocation, "panel") == "intersection"
    assert service_module._translocation_sort_value(translocation, "tier") == 2.0
    assert service_module._translocation_sort_value(translocation, "unsupported") is None
    assert service_module._translocation_sort_value({}, "gene1") is None
    assert service_module._translocation_sort_value({}, "gene2") is None
    assert service_module._translocation_sort_value({"annotations": "single"}, "hgvs") == "single"
    assert "NTRK1 TPM3" in service_module._translocation_search_text(translocation)


def test_service_factory_and_config_resolution_use_injected_repositories(monkeypatch):
    store = SimpleNamespace(
        annotation_repository=object(),
        query_rule_repository=SimpleNamespace(describe_selection=compile_selection),
        assay_group_repository=object(),
        assay_diagnosis_repository=object(),
        copy_number_variant_repository=object(),
        translocation_repository=object(),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
        gene_list_repository=object(),
        bam_record_repository=object(),
        vep_metadata_repository=object(),
        cosmic_repository=object(),
    )
    service = DnaStructuralService.from_store(store)
    captured: dict[str, object] = {}

    def _resolve(sample, **repositories):
        captured["sample"] = sample
        captured.update(repositories)
        return {"resolved": True}

    monkeypatch.setattr(service_module, "get_formatted_assay_config", _resolve)

    assert service._get_formatted_assay_config({"_id": "S1"}) == {"resolved": True}
    assert captured["assay_panel_repository"] is store.assay_panel_repository
    assert captured["assay_configuration_repository"] is store.assay_configuration_repository


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


def test_cnv_detail_rejects_missing_owner_even_when_listed_for_sample(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    repo.copy_number_variant_repository.cnv_doc = None
    with pytest.raises(AppError, match="CNV not found"):
        service.show_cnv_payload(sample=_sample(), cnv_id="missing")

    repo.copy_number_variant_repository.cnv_doc = {"_id": "legacy", "genes": []}
    repo.copy_number_variant_repository.sample_cnvs_payload = [{"_id": "other"}]
    with pytest.raises(AppError, match="CNV not found for sample"):
        service.show_cnv_payload(sample=_sample(), cnv_id="legacy")

    repo.copy_number_variant_repository.sample_cnvs_payload = [{"_id": "legacy"}]
    with pytest.raises(AppError, match="CNV not found for sample"):
        service.show_cnv_payload(sample=_sample(), cnv_id="legacy")


@pytest.mark.parametrize("flag", ["interesting", "false_positive", "noteworthy"])
@pytest.mark.parametrize("apply", [True, False])
def test_cnv_flag_commands_dispatch_to_repository(flag, apply):
    repo = _RepoStub()
    handler = repo.copy_number_variant_repository
    handler.set_sample_finding_flag = Mock()

    _service_from_repo(repo).set_cnv_flag(
        sample={"_id": "sample-1"}, cnv_id="cnv1", apply=apply, flag=flag
    )

    handler.set_sample_finding_flag.assert_called_once_with(
        sample_id="sample-1",
        resource_ids=["cnv1"],
        flag="fp" if flag == "false_positive" else flag,
        value=apply,
    )


def test_cnv_flag_and_comment_validation_and_dispatch():
    repo = _RepoStub()
    handler = repo.copy_number_variant_repository
    handler.hide_cnvs_comment = Mock()
    handler.unhide_cnvs_comment = Mock()
    service = _service_from_repo(repo)

    with pytest.raises(ValueError, match="Unsupported flag"):
        service.set_cnv_flag(sample={"_id": "sample-1"}, cnv_id="cnv1", apply=True, flag="unknown")
    service.set_cnv_comment_hidden(cnv_id="cnv1", comment_id="comment1", hidden=True)
    service.set_cnv_comment_hidden(cnv_id="cnv1", comment_id="comment1", hidden=False)

    handler.hide_cnvs_comment.assert_called_once_with("cnv1", "comment1")
    handler.unhide_cnvs_comment.assert_called_once_with("cnv1", "comment1")


def test_translocation_detail_rejects_missing_owner_even_when_listed_for_sample(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    repo.translocation_repository.doc = None
    with pytest.raises(AppError, match="Translocation not found"):
        service.show_translocation_payload(sample=_sample(), transloc_id="missing")

    repo.translocation_repository.doc = {"_id": "legacy"}
    repo.translocation_repository.sample_translocations_payload = [{"_id": "other"}]
    with pytest.raises(AppError, match="Translocation not found for sample"):
        service.show_translocation_payload(sample=_sample(), transloc_id="legacy")

    repo.translocation_repository.sample_translocations_payload = [{"_id": "legacy"}]
    with pytest.raises(AppError, match="Translocation not found for sample"):
        service.show_translocation_payload(sample=_sample(), transloc_id="legacy")


@pytest.mark.parametrize("flag", ["interesting", "false_positive"])
@pytest.mark.parametrize("apply", [True, False])
def test_translocation_boolean_flag_commands_dispatch_to_repository(flag, apply):
    repo = _RepoStub()
    handler = repo.translocation_repository
    handler.set_sample_finding_flag = Mock()

    _service_from_repo(repo).set_translocation_flag(
        sample={"_id": "sample-1"}, transloc_id="t1", apply=apply, flag=flag
    )

    handler.set_sample_finding_flag.assert_called_once_with(
        sample_id="sample-1",
        resource_ids=["t1"],
        flag="fp" if flag == "false_positive" else flag,
        value=apply,
    )


def test_translocation_flags_comments_and_validation_dispatch():
    repo = _RepoStub()
    handler = repo.translocation_repository
    handler.set_sample_finding_flag = Mock()
    handler.hide_transloc_comment = Mock()
    handler.unhide_transloc_comment = Mock()
    service = _service_from_repo(repo)

    service.set_translocation_flag(
        sample={"_id": "sample-1"}, transloc_id="t1", apply=True, flag="irrelevant"
    )
    service.set_translocation_flag(
        sample={"_id": "sample-1"}, transloc_id="t1", apply=False, flag="blacklisted"
    )
    with pytest.raises(ValueError, match="Unsupported flag"):
        service.set_translocation_flag(
            sample={"_id": "sample-1"}, transloc_id="t1", apply=True, flag="unknown"
        )
    service.set_translocation_comment_hidden(transloc_id="t1", comment_id="comment1", hidden=True)
    service.set_translocation_comment_hidden(transloc_id="t1", comment_id="comment1", hidden=False)

    handler.set_sample_finding_flag.assert_any_call(
        sample_id="sample-1", resource_ids=["t1"], flag="irrelevant", value=True
    )
    handler.set_sample_finding_flag.assert_any_call(
        sample_id="sample-1", resource_ids=["t1"], flag="blacklisted", value=False
    )
    handler.hide_transloc_comment.assert_called_once_with("t1", "comment1")
    handler.unhide_transloc_comment.assert_called_once_with("t1", "comment1")
