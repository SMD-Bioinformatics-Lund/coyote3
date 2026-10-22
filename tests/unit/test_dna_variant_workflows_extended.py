"""Extended tests for DNA classification, state, and comment workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.dna.variant_analysis import DnaService
from api.application.dna.variant_state import (
    blacklist_variant,
    coerce_bool,
    require_variant_for_sample,
    set_variant_bulk_flag,
    set_variant_comment_hidden,
)
from api.contracts.operations import OperationResult
from api.domain.core.exceptions import AppError


class Recorder:
    """Record arbitrary repository method calls."""

    def __init__(self, **returns):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.returns = returns

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            value = self.returns.get(name)
            return value(*args, **kwargs) if callable(value) else value

        return method


def _variant(variant_id: str, *, sample_id: str = "sample-1", **csq) -> dict:
    selected = {
        "Feature": "NM_000001.1",
        "SYMBOL": "TP53",
        "HGVSp": "p.Arg1Cys",
        "HGVSc": "c.1C>T",
        "Consequence": ["missense_variant"],
        **csq,
    }
    return {
        "_id": variant_id,
        "SAMPLE_ID": sample_id,
        "CHROM": "17",
        "POS": 10,
        "REF": "C",
        "ALT": "T",
        "simple_id": "17:10:C:T",
        "simple_id_hash": "hash",
        "INFO": {"selected_CSQ": selected},
    }


def test_variant_state_load_require_and_repository_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.application.dna.variant_analysis.build_cnv_query",
        lambda sample_id, **kwargs: {"sample": sample_id, **kwargs},
    )
    monkeypatch.setattr(
        "api.application.dna.variant_analysis.include_normal_cnvs", lambda sample: True
    )
    monkeypatch.setattr(
        "api.application.dna.variant_analysis.create_cnveffectlist", lambda values: ["gain"]
    )
    monkeypatch.setattr(
        "api.application.dna.variant_analysis.cnvtype_variant",
        lambda rows, effects: [{**rows[0], "effects": effects}],
    )
    monkeypatch.setattr(
        "api.application.dna.variant_analysis.cnv_organizegenes",
        lambda rows: [{**rows[0], "organized": True}],
    )
    variants = Recorder(get_variant=lambda variant_id: _variant(variant_id))
    cnvs = Recorder(get_sample_cnvs=[{"_id": "cnv-1"}])
    blacklist = Recorder(blacklist_variant="created")
    service = SimpleNamespace(
        variant_repository=variants,
        copy_number_variant_repository=cnvs,
        query_rule_service=None,
        blacklist_repository=blacklist,
    )
    loaded = DnaService.load_cnvs_for_sample(
        service,
        sample={"_id": "sample-1"},
        sample_filters={"cnveffects": ["gain"]},
        filter_genes=["TP53"],
    )
    assert loaded == [{"_id": "cnv-1", "effects": ["gain"], "organized": True}]
    assert (
        require_variant_for_sample(service, sample={"_id": "sample-1"}, var_id="variant-1")["_id"]
        == "variant-1"
    )
    assert (
        blacklist_variant(service, variant={"_id": "variant-1"}, assay_group="solid") == "created"
    )
    DnaService.set_variant_override_blacklist(
        service, sample={"_id": "sample-1"}, var_id="variant-1", override=True
    )
    set_variant_comment_hidden(service, var_id="variant-1", comment_id="comment-1", hidden=True)
    set_variant_comment_hidden(service, var_id="variant-1", comment_id="comment-1", hidden=False)
    assert {call[0] for call in variants.calls} >= {
        "set_sample_finding_flag",
        "hide_var_comment",
        "unhide_variant_comment",
    }


def test_require_variant_rejects_missing_or_foreign() -> None:
    service = SimpleNamespace(variant_repository=Recorder(get_variant=None))
    with pytest.raises(AppError) as exc:
        require_variant_for_sample(service, sample={"_id": "sample-1"}, var_id="missing")
    assert exc.value.status_code == 404
    service.variant_repository = Recorder(get_variant=_variant("foreign", sample_id="other"))
    with pytest.raises(AppError):
        require_variant_for_sample(service, sample={"_id": "sample-1"}, var_id="foreign")


@pytest.mark.parametrize("flag", ["false_positive", "irrelevant"])
@pytest.mark.parametrize("apply", [True, False])
def test_bulk_flags_cover_apply_and_remove(flag, apply) -> None:
    result = OperationResult(matched_count=1, modified_count=1)
    repository = Recorder(
        set_sample_finding_flag=result,
        unmark_false_positive_var_bulk=result,
        mark_irrelevant_var_bulk=result,
        unmark_irrelevant_var_bulk=result,
    )
    observed = set_variant_bulk_flag(
        SimpleNamespace(variant_repository=repository),
        sample={"_id": "sample-1"},
        resource_ids=["v1"],
        apply=apply,
        flag=flag,
    )
    assert observed.modified_count == 1


def test_bulk_flags_empty_and_unknown() -> None:
    service = SimpleNamespace(
        variant_repository=Recorder(set_sample_finding_flag=OperationResult.empty())
    )
    assert (
        set_variant_bulk_flag(
            service, sample={"_id": "sample-1"}, resource_ids=[], apply=True, flag="irrelevant"
        ).modified_count
        == 0
    )
    with pytest.raises(ValueError, match="Unsupported flag"):
        set_variant_bulk_flag(
            service, sample={"_id": "sample-1"}, resource_ids=["v1"], apply=True, flag="unknown"
        )


@pytest.mark.parametrize("flag", ["false_positive", "interesting", "irrelevant"])
@pytest.mark.parametrize("apply", [True, False])
def test_single_flags_cover_apply_and_remove(flag, apply) -> None:
    repository = Recorder()
    DnaService.set_variant_flag(
        SimpleNamespace(variant_repository=repository),
        sample={"_id": "sample-1"},
        var_id="v1",
        apply=apply,
        flag=flag,
    )
    assert len(repository.calls) == 1


def test_single_flag_unknown_and_boolean_coercion() -> None:
    with pytest.raises(ValueError, match="Unsupported flag"):
        DnaService.set_variant_flag(
            SimpleNamespace(
                variant_repository=Recorder(set_sample_finding_flag=OperationResult.empty())
            ),
            sample={"_id": "sample-1"},
            var_id="v1",
            apply=True,
            flag="unknown",
        )
    assert coerce_bool(True) is True
    assert coerce_bool(" yes ") is True
    assert coerce_bool("OFF") is False
    assert coerce_bool(None, default=False) is False
