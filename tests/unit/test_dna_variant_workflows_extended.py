"""Extended tests for DNA classification, state, and comment workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.dna.variant_classification import (
    classify_variant,
    remove_classified_variant,
    set_variant_tier_bulk,
)
from api.application.dna.variant_comments import add_variant_comment
from api.application.dna.variant_state import (
    blacklist_variant,
    coerce_bool,
    load_cnvs_for_sample,
    require_variant_for_sample,
    set_variant_bulk_flag,
    set_variant_comment_hidden,
    set_variant_flag,
    set_variant_override_blacklist,
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


def test_bulk_tiering_skips_missing_and_foreign_variants() -> None:
    annotations = Recorder()
    variants = {
        "owned": _variant("owned"),
        "foreign": _variant("foreign", sample_id="other"),
    }
    service = SimpleNamespace(
        variant_repository=Recorder(get_variant=lambda variant_id: variants.get(variant_id)),
        annotation_repository=annotations,
    )

    def make_doc(**kwargs):
        return kwargs

    set_variant_tier_bulk(
        service,
        sample={"_id": "sample-1"},
        resource_ids=["missing", "foreign", "owned"],
        assay_group="hematology",
        subpanel="myeloid",
        apply=True,
        class_num=3,
        create_classified_variant_doc_fn=make_doc,
    )

    inserted = annotations.calls[-1][1][0]
    assert len(inserted) == 1
    assert inserted[0]["variant"] == "p.Arg1Cys"
    assert inserted[0]["nomenclature"] == "p"
    assert inserted[0]["variant_data"]["genomic_hash"] == "hash"


@pytest.mark.parametrize(
    ("csq", "expected_variant", "expected_nomenclature"),
    [
        ({"HGVSp": "", "HGVSc": "c.2A>G"}, "c.2A>G", "c"),
        ({"HGVSp": None, "HGVSc": None}, "17:10:C/T", "g"),
    ],
)
def test_bulk_tiering_uses_coding_then_genomic_nomenclature(
    csq, expected_variant, expected_nomenclature
) -> None:
    annotations = Recorder()
    service = SimpleNamespace(
        variant_repository=Recorder(get_variant=_variant("owned", **csq)),
        annotation_repository=annotations,
    )
    set_variant_tier_bulk(
        service,
        sample={"_id": "sample-1"},
        resource_ids=["owned"],
        assay_group="solid",
        subpanel=None,
        apply=True,
        class_num=2,
        create_classified_variant_doc_fn=lambda **kwargs: kwargs,
    )
    doc = annotations.calls[-1][1][0][0]
    assert (doc["variant"], doc["nomenclature"]) == (
        expected_variant,
        expected_nomenclature,
    )


def test_bulk_tiering_removes_classification() -> None:
    annotations = Recorder()
    service = SimpleNamespace(
        variant_repository=Recorder(get_variant=_variant("owned")),
        annotation_repository=annotations,
    )
    set_variant_tier_bulk(
        service,
        sample={"_id": "sample-1"},
        resource_ids=["owned"],
        assay_group="solid",
        subpanel="colon",
        apply=False,
        class_num=3,
        create_classified_variant_doc_fn=lambda **kwargs: kwargs,
    )
    name, _, kwargs = annotations.calls[-1]
    assert name == "delete_classified_variant"
    assert kwargs["annotation_text"] is None
    assert kwargs["class_num"] == 3


def test_single_classification_insert_remove_and_zero_class() -> None:
    annotations = Recorder()
    service = SimpleNamespace(annotation_repository=annotations)
    form = {"tier": 2}
    classify_variant(
        service,
        form_data=form,
        get_tier_classification_fn=lambda value: value["tier"],
        get_variant_nomenclature_fn=lambda value: ("p", "p.Arg1Cys"),
    )
    classify_variant(
        service,
        form_data={"tier": 0},
        get_tier_classification_fn=lambda value: value["tier"],
        get_variant_nomenclature_fn=lambda value: ("p", "ignored"),
    )
    remove_classified_variant(
        service,
        form_data=form,
        get_variant_nomenclature_fn=lambda value: ("p", "p.Arg1Cys"),
    )
    assert [call[0] for call in annotations.calls] == [
        "insert_classified_variant",
        "delete_classified_variant",
    ]


@pytest.mark.parametrize(
    ("scope", "nomenclature", "repository_name", "expected"),
    [
        ("local", "f", "fusion_repository", "fusion_comment"),
        ("local", "t", "translocation_repository", "translocation_comment"),
        ("local", "cn", "copy_number_variant_repository", "cnv_comment"),
        ("local", "p", "variant_repository", "variant_comment"),
        ("global", "f", "annotation_repository", "fusion_comment"),
    ],
)
def test_add_variant_comment_routes_by_nomenclature(
    scope, nomenclature, repository_name, expected
) -> None:
    repositories = {
        name: Recorder()
        for name in (
            "annotation_repository",
            "fusion_repository",
            "translocation_repository",
            "copy_number_variant_repository",
            "variant_repository",
        )
    }
    result = add_variant_comment(
        SimpleNamespace(**repositories),
        form_data={"global": scope, "text": "reviewed"},
        target_id="finding-1",
        get_variant_nomenclature_fn=lambda value: (nomenclature, "identity"),
        create_comment_doc_fn=lambda value, **kwargs: {**value, **kwargs},
    )
    assert result == expected
    assert repositories[repository_name].calls


def test_variant_state_load_require_and_repository_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.application.dna.variant_state.build_cnv_query",
        lambda sample_id, **kwargs: {"sample": sample_id, **kwargs},
    )
    monkeypatch.setattr(
        "api.application.dna.variant_state.include_normal_cnvs", lambda sample: True
    )
    monkeypatch.setattr(
        "api.application.dna.variant_state.create_cnveffectlist", lambda values: ["gain"]
    )
    monkeypatch.setattr(
        "api.application.dna.variant_state.cnvtype_variant",
        lambda rows, effects: [{**rows[0], "effects": effects}],
    )
    monkeypatch.setattr(
        "api.application.dna.variant_state.cnv_organizegenes",
        lambda rows: [{**rows[0], "organized": True}],
    )
    variants = Recorder(get_variant=lambda variant_id: _variant(variant_id))
    cnvs = Recorder(get_sample_cnvs=[{"_id": "cnv-1"}])
    blacklist = Recorder(blacklist_variant="created")
    service = SimpleNamespace(
        variant_repository=variants,
        copy_number_variant_repository=cnvs,
        blacklist_repository=blacklist,
    )
    loaded = load_cnvs_for_sample(
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
    set_variant_override_blacklist(service, var_id="variant-1", override=True)
    set_variant_comment_hidden(service, var_id="variant-1", comment_id="comment-1", hidden=True)
    set_variant_comment_hidden(service, var_id="variant-1", comment_id="comment-1", hidden=False)
    assert {call[0] for call in variants.calls} >= {
        "set_override_blacklist",
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
        mark_false_positive_var_bulk=result,
        unmark_false_positive_var_bulk=result,
        mark_irrelevant_var_bulk=result,
        unmark_irrelevant_var_bulk=result,
    )
    observed = set_variant_bulk_flag(
        SimpleNamespace(variant_repository=repository),
        resource_ids=["v1"],
        apply=apply,
        flag=flag,
    )
    assert observed.modified_count == 1


def test_bulk_flags_empty_and_unknown() -> None:
    service = SimpleNamespace(variant_repository=Recorder())
    assert (
        set_variant_bulk_flag(
            service, resource_ids=[], apply=True, flag="irrelevant"
        ).modified_count
        == 0
    )
    with pytest.raises(ValueError, match="Unsupported flag"):
        set_variant_bulk_flag(service, resource_ids=["v1"], apply=True, flag="unknown")


@pytest.mark.parametrize("flag", ["false_positive", "interesting", "irrelevant"])
@pytest.mark.parametrize("apply", [True, False])
def test_single_flags_cover_apply_and_remove(flag, apply) -> None:
    repository = Recorder()
    set_variant_flag(
        SimpleNamespace(variant_repository=repository),
        var_id="v1",
        apply=apply,
        flag=flag,
    )
    assert len(repository.calls) == 1


def test_single_flag_unknown_and_boolean_coercion() -> None:
    with pytest.raises(ValueError, match="Unsupported flag"):
        set_variant_flag(
            SimpleNamespace(variant_repository=Recorder()),
            var_id="v1",
            apply=True,
            flag="unknown",
        )
    assert coerce_bool(True) is True
    assert coerce_bool(" yes ") is True
    assert coerce_bool("OFF") is False
    assert coerce_bool(None, default=False) is False
