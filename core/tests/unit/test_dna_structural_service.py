"""Unit tests for DNA structural service workflows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import coyote.application.dna.structural_variants as service_module
import pytest
from coyote.application.common.change_payload import change_payload
from coyote.application.common.release_resources import capture_assay_resource, capture_gene_lists
from coyote.application.dna.structural_variants import DnaStructuralService
from coyote.contracts.dna import DnaTranslocationContextPayload
from coyote.domain.exceptions import AppError


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
