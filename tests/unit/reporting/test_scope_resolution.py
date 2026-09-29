"""Published scope selection, Base fallback and preserved report-source identity."""

from types import SimpleNamespace

import mongomock
import pytest

from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.resolution import resolve_published_rule_set
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.application.reporting.clinical_rules.validation import content_hash
from api.infra.mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from tests.unit.reporting.test_clinical_rules import _context, _document


def release(subpanel="base", *, language="sv", analyte="dna", **changes):
    """Make a synthetic published release with a valid content digest."""
    doc = _document(status="published", active=True).model_copy(deep=True)
    doc.scope.subpanel_id = subpanel
    doc.scope.language = language
    doc.scope.analyte = analyte
    doc.rule_set_id = f"assay_1__{subpanel}__{language}"
    doc.content_hash = content_hash(doc)
    return dict(doc.model_dump(mode="python", by_alias=True), **changes)


def resolve(rows, subpanel="named", language="sv", analyte="dna"):
    """Resolve synthetic releases without a database connection."""
    return resolve_published_rule_set(
        SimpleNamespace(list_active_for_assay=lambda _asp, **_scope: rows),
        asp_id="assay_1",
        subpanel_id=subpanel,
        language=language,
        analyte=analyte,
    )


def test_exact_scope_wins_independent_of_order():
    base, named = release(), release("named")
    assert resolve([base, named]).scope.subpanel_id == "named"
    assert resolve([named, base]).scope.subpanel_id == "named"


def test_repository_limits_candidates_to_assay_scope_analyte_and_language():
    """Mongo filtering retains exact/Base candidates without concealing duplicates."""
    db = mongomock.MongoClient().test
    rows = [
        release(),
        release("named"),
        release("other"),
        release("named", language="en"),
        release("named", analyte="rna"),
        release("named", active=False),
        release("named", status="draft"),
    ]
    for row in rows:
        row.pop("_id", None)
        db.rules.insert_one(row)
    duplicate = release("named")
    duplicate.pop("_id", None)
    db.rules.insert_one(duplicate)
    other_assay = release()
    other_assay.pop("_id", None)
    other_assay["scope"]["asp_id"] = "other-assay"
    db.rules.insert_one(other_assay)
    repository = ClinicalRuleSetRepository(
        SimpleNamespace(
            clinical_rule_sets_collection=db.rules,
            clinical_rule_revisions_collection=db.revisions,
        )
    )
    found = repository.list_active_for_assay(
        "assay_1",
        subpanel_id="named",
        analyte="dna",
        language="sv",
    )
    assert [row["scope"]["subpanel_id"] for row in found] == ["base", "named", "named"]


@pytest.mark.parametrize(
    "changes", [{"status": "draft"}, {"status": "approved"}, {"active": False}]
)
def test_unpublished_or_inactive_exact_scope_does_not_replace_base(changes):
    assert resolve([release(), release("named", **changes)]).scope.subpanel_id == "base"


@pytest.mark.parametrize("scope", ["", "base"])
def test_implicit_base_is_not_treated_as_duplicate(scope):
    assert resolve([release()], subpanel=scope).scope.subpanel_id == "base"


@pytest.mark.parametrize(
    "rows", [[], [release("other")], [release(language="en")], [release(analyte="rna")]]
)
def test_never_crosses_subpanel_language_or_analyte(rows):
    with pytest.raises(ValueError, match="No active published"):
        resolve(rows)


def test_never_crosses_assay():
    row = release()
    row["scope"]["asp_id"] = "another"
    with pytest.raises(ValueError, match="No active published"):
        resolve([row])


@pytest.mark.parametrize("scope", ["base", "named"])
def test_ambiguous_selected_scope_fails_closed(scope):
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve([release(scope), release(scope)])


def test_published_exact_release_is_used_without_aspc_changes_and_source_is_preserved():
    rows = [release()]
    service = ClinicalRuleService(
        SimpleNamespace(list_active_for_assay=lambda _asp, **_scope: rows)
    )
    context = _context()
    context.sample.subpanel_id = "named"
    prior = service.evaluate(aspc={}, context=context)
    rows.append(release("named"))
    current = service.evaluate(aspc={}, context=context)
    assert prior.source.rule_set_id == "assay_1__base__sv"
    assert prior.source.resolved_subpanel_id == "base"
    assert current.source.rule_set_id == "assay_1__named__sv"
    assert current.source.requested_subpanel_id == "named"
    assert current.source.content_hash == rows[-1]["content_hash"]


def test_corrupt_exact_release_never_falls_back_to_valid_base():
    context = _context()
    context.sample.subpanel_id = "named"
    rows = [release(), release("named", content_hash="invalid")]
    with pytest.raises(ValueError, match="integrity"):
        ClinicalRuleService(
            SimpleNamespace(list_active_for_assay=lambda _asp, **_scope: rows)
        ).resolve(context=context)


@pytest.mark.parametrize("subpanel", [None, "", "base"])
def test_unscoped_sample_never_inherits_a_named_configuration_scope(subpanel):
    context = prepare_report_context(
        sample={"name": "SYNTHETIC", "asp_id": "assay_1", "subpanel_id": subpanel},
        asp={"asp_id": "assay_1"},
        aspc={"aspc_id": "config", "asp_id": "assay_1", "subpanel_id": "named"},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={},
    )
    assert context.sample.subpanel_id == "base"
