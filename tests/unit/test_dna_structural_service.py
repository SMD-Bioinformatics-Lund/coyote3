"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import api.application.dna.structural_variants as service_module
from api.application.common.change_payload import change_payload
from api.application.dna.structural_variants import DnaStructuralService
from api.domain.core.exceptions import AppError


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
        self.sample_translocations_payload = [{"_id": "t1", "SAMPLE_ID": "S1"}]

    def get_sample_translocations(self, _query=None, **_kwargs):
        return self.sample_translocations_payload

    def get_transloc(self, _transloc_id: str):
        return self.doc

    def get_transloc_annotations(self, _doc: dict):
        return [{"annotation": "t"}]

    def hidden_transloc_comments(self, _transloc_id: str):
        return [{"text": "hidden"}]


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
            get_bams=lambda sample_ids: {"ids": sample_ids}
        )
        self.vep_metadata_repository = SimpleNamespace(
            get_conseq_translations=lambda _vep: {"A": "B"}
        )
        self.cosmic_repository = SimpleNamespace(
            get_cnv_evidence=lambda _cnv: {"kind": "copy_number", "records": []},
            get_translocation_evidence=lambda _transloc: {
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
        get_case_and_control_sample_ids=lambda _sample: ["S1", "S2"],
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


def _request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path))


def _service_from_repo(repo: _RepoStub) -> DnaStructuralService:
    return DnaStructuralService(
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
        lambda sample_id, filters, include_normal=False: {
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

    def _get_isgl_by_ids(ids):
        captured["ids"] = list(ids)
        return {"GL1": {"genes": ["TP53"], "list_type": ["cnv"]}}

    repo.gene_list_repository = SimpleNamespace(get_isgl_by_ids=_get_isgl_by_ids)
    service = DnaStructuralService(
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
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    def _load_cnvs_for_sample(**kwargs):
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(service, "load_cnvs_for_sample", _load_cnvs_for_sample)

    service.list_cnvs_payload(
        request=_request("/api/v1/cnvs/S1"), sample=sample, util_module=_UtilModule
    )

    assert captured["ids"] == ["GL1"]
    assert captured["kwargs"]["filter_genes"] == ["TP53"]


def test_list_cnvs_payload_raises_when_assay_config_missing(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(service_module, "get_formatted_assay_config", lambda _sample: None)

    with pytest.raises(AppError) as exc:
        service.list_cnvs_payload(
            request=_request("/api/v1/cnvs/S1"), sample=_sample(), util_module=_UtilModule
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "ASPC could not be resolved for the sample"
    assert exc.value.detail["category"] == "setup"


def test_list_cnvs_payload_returns_count(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
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
    assert payload["sample"]["files"]["cnvprofile"]["path"] == "/data/sample1.cnv.png"


def test_show_cnv_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.copy_number_variant_repository.cnv_doc = {"_id": "cnv1", "SAMPLE_ID": "S2"}
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    with pytest.raises(AppError) as exc:
        service.show_cnv_payload(sample=_sample(), cnv_id="cnv1", util_module=_UtilModule)

    assert exc.value.status_code == 404


def test_show_cnv_payload_returns_detail(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    payload = service.show_cnv_payload(sample=_sample(), cnv_id="cnv1", util_module=_UtilModule)

    assert payload["sample_summary"]["assay_group"] == "dna"
    assert payload["has_hidden_comments"]


def test_list_translocations_payload_returns_count(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"filters": {}}
    )
    payload = service.list_translocations_payload(
        request=_request("/api/v1/translocations/S1"), sample=_sample()
    )
    assert payload["meta"]["count"] == 1
    assert payload["vep_conseq_translations"] == {"A": "B"}


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
        service_module, "get_formatted_assay_config", lambda _sample: {"filters": {}}
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        request=_request("/api/v1/translocations/S1"),
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
        service_module, "get_formatted_assay_config", lambda _sample: {"filters": {}}
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        request=_request("/api/v1/translocations/S1"),
        sample=_sample(),
    )

    assert [row["_id"] for row in payload["translocations"]] == ["keep"]


def test_list_translocations_is_unrestricted_without_list_or_asp_scope(monkeypatch):
    repo = _RepoStub()
    repo.translocation_repository.sample_translocations_payload = [
        {"_id": "one", "SAMPLE_ID": "S1", "gene1": "NPM1"},
        {"_id": "two", "SAMPLE_ID": "S1", "gene1": "KMT2A"},
    ]
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"filters": {}}
    )

    payload = _service_from_repo(repo).list_translocations_payload(
        request=_request("/api/v1/translocations/S1"),
        sample=_sample(),
    )

    assert [row["_id"] for row in payload["translocations"]] == ["one", "two"]


def test_show_translocation_payload_rejects_cross_sample(monkeypatch):
    repo = _RepoStub()
    repo.translocation_repository.doc = {"_id": "t1", "SAMPLE_ID": "S2"}
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    with pytest.raises(AppError) as exc:
        service.show_translocation_payload(
            sample=_sample(), transloc_id="t1", util_module=_UtilModule
        )

    assert exc.value.status_code == 404


def test_show_translocation_payload_returns_detail(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    monkeypatch.setattr(
        service_module, "get_formatted_assay_config", lambda _sample: {"asp_group": "dna"}
    )

    payload = service.show_translocation_payload(
        sample=_sample(), transloc_id="t1", util_module=_UtilModule
    )

    assert payload["translocation"]["_id"] == "t1"
    assert payload["vep_conseq_translations"] == {"A": "B"}


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
    monkeypatch.setattr(service, "_get_formatted_assay_config", lambda _sample: {"filters": {}})
    monkeypatch.setattr(service, "load_cnvs_for_sample", lambda **_kwargs: rows)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/samples/S1/cnvs"),
        query_params={"q": "BRAF", "sort": "genes:desc"},
    )

    payload = service.list_cnvs_payload(
        request=request,
        sample=_sample(),
        util_module=_UtilModule,
        paginate=False,
    )

    assert [row["_id"] for row in payload["cnvs"]] == ["b"]
    assert payload["meta"]["search"] == "BRAF"
    assert payload["meta"]["sort"] == "genes:desc"
    assert payload["meta"]["page_count"] == 1


def test_translocation_list_search_sort_and_pagination(monkeypatch):
    repo = _RepoStub()
    repo.translocation_repository.sample_translocations_payload = [
        {"_id": "b", "SAMPLE_ID": "S1", "gene1": "NTRK1", "gene2": "TPM3"},
        {"_id": "a", "SAMPLE_ID": "S1", "gene1": "ALK", "gene2": "EML4"},
    ]
    service = _service_from_repo(repo)
    monkeypatch.setattr(service, "_get_formatted_assay_config", lambda _sample: {"filters": {}})
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/samples/S1/translocations"),
        query_params={"q": "NTRK1", "sort": "gene1:asc", "page": "1", "per_page": "1"},
    )

    payload = service.list_translocations_payload(request=request, sample=_sample())

    assert [row["_id"] for row in payload["translocations"]] == ["b"]
    assert payload["meta"]["total"] == 1
    assert payload["meta"]["sort"] == "gene1:asc"


def test_cnv_detail_handles_missing_records_and_legacy_membership(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    repo.copy_number_variant_repository.cnv_doc = None
    with pytest.raises(AppError, match="CNV not found"):
        service.show_cnv_payload(sample=_sample(), cnv_id="missing", util_module=_UtilModule)

    repo.copy_number_variant_repository.cnv_doc = {"_id": "legacy", "genes": []}
    repo.copy_number_variant_repository.sample_cnvs_payload = [{"_id": "other"}]
    with pytest.raises(AppError, match="CNV not found for sample"):
        service.show_cnv_payload(sample=_sample(), cnv_id="legacy", util_module=_UtilModule)

    repo.copy_number_variant_repository.sample_cnvs_payload = [{"_id": "legacy"}]
    monkeypatch.setattr(service, "_get_formatted_assay_config", lambda _sample: {})
    payload = service.show_cnv_payload(sample=_sample(), cnv_id="legacy", util_module=_UtilModule)
    assert payload["assay_group"] == "unknown"


@pytest.mark.parametrize("flag", ["interesting", "false_positive", "noteworthy"])
@pytest.mark.parametrize("apply", [True, False])
def test_cnv_flag_commands_dispatch_to_repository(flag, apply):
    repo = _RepoStub()
    handler = repo.copy_number_variant_repository
    methods = {
        ("interesting", True): "mark_interesting_cnv",
        ("interesting", False): "unmark_interesting_cnv",
        ("false_positive", True): "mark_false_positive_cnv",
        ("false_positive", False): "unmark_false_positive_cnv",
        ("noteworthy", True): "noteworthy_cnv",
        ("noteworthy", False): "unnoteworthy_cnv",
    }
    for method_name in methods.values():
        setattr(handler, method_name, Mock())

    _service_from_repo(repo).set_cnv_flag(cnv_id="cnv1", apply=apply, flag=flag)

    getattr(handler, methods[(flag, apply)]).assert_called_once_with("cnv1")


def test_cnv_flag_and_comment_validation_and_dispatch():
    repo = _RepoStub()
    handler = repo.copy_number_variant_repository
    handler.hide_cnvs_comment = Mock()
    handler.unhide_cnvs_comment = Mock()
    service = _service_from_repo(repo)

    with pytest.raises(ValueError, match="Unsupported flag"):
        service.set_cnv_flag(cnv_id="cnv1", apply=True, flag="unknown")
    service.set_cnv_comment_hidden(cnv_id="cnv1", comment_id="comment1", hidden=True)
    service.set_cnv_comment_hidden(cnv_id="cnv1", comment_id="comment1", hidden=False)

    handler.hide_cnvs_comment.assert_called_once_with("cnv1", "comment1")
    handler.unhide_cnvs_comment.assert_called_once_with("cnv1", "comment1")


def test_translocation_detail_handles_missing_records_and_legacy_membership(monkeypatch):
    repo = _RepoStub()
    service = _service_from_repo(repo)
    repo.translocation_repository.doc = None
    with pytest.raises(AppError, match="Translocation not found"):
        service.show_translocation_payload(
            sample=_sample(), transloc_id="missing", util_module=_UtilModule
        )

    repo.translocation_repository.doc = {"_id": "legacy"}
    repo.translocation_repository.sample_translocations_payload = [{"_id": "other"}]
    with pytest.raises(AppError, match="Translocation not found for sample"):
        service.show_translocation_payload(
            sample=_sample(), transloc_id="legacy", util_module=_UtilModule
        )

    repo.translocation_repository.sample_translocations_payload = [{"_id": "legacy"}]
    monkeypatch.setattr(service, "_get_formatted_assay_config", lambda _sample: {})
    payload = service.show_translocation_payload(
        sample=_sample(), transloc_id="legacy", util_module=_UtilModule
    )
    assert payload["assay_group"] == "unknown"


@pytest.mark.parametrize("flag", ["interesting", "false_positive"])
@pytest.mark.parametrize("apply", [True, False])
def test_translocation_boolean_flag_commands_dispatch_to_repository(flag, apply):
    repo = _RepoStub()
    handler = repo.translocation_repository
    methods = {
        ("interesting", True): "mark_interesting_transloc",
        ("interesting", False): "unmark_interesting_transloc",
        ("false_positive", True): "mark_false_positive_transloc",
        ("false_positive", False): "unmark_false_positive_transloc",
    }
    for method_name in methods.values():
        setattr(handler, method_name, Mock())

    _service_from_repo(repo).set_translocation_flag(transloc_id="t1", apply=apply, flag=flag)

    getattr(handler, methods[(flag, apply)]).assert_called_once_with("t1")


def test_translocation_flags_comments_and_validation_dispatch():
    repo = _RepoStub()
    handler = repo.translocation_repository
    handler.mark_irrelevant = Mock()
    handler.mark_blacklisted = Mock()
    handler.hide_transloc_comment = Mock()
    handler.unhide_transloc_comment = Mock()
    service = _service_from_repo(repo)

    service.set_translocation_flag(transloc_id="t1", apply=True, flag="irrelevant")
    service.set_translocation_flag(transloc_id="t1", apply=False, flag="blacklisted")
    with pytest.raises(ValueError, match="Unsupported flag"):
        service.set_translocation_flag(transloc_id="t1", apply=True, flag="unknown")
    service.set_translocation_comment_hidden(transloc_id="t1", comment_id="comment1", hidden=True)
    service.set_translocation_comment_hidden(transloc_id="t1", comment_id="comment1", hidden=False)

    handler.mark_irrelevant.assert_called_once_with("t1", True)
    handler.mark_blacklisted.assert_called_once_with("t1", False)
    handler.hide_transloc_comment.assert_called_once_with("t1", "comment1")
    handler.unhide_transloc_comment.assert_called_once_with("t1", "comment1")
