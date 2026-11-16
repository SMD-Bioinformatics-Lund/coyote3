"""Published scope selection, Base fallback and preserved report-source identity."""

from types import SimpleNamespace

import mongomock
from coyote.application.reporting.clinical_rules.validation import content_hash
from coyote_mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from mongo_test_support.clinical_rules import _document
from mongo_test_support.settings import mongo_runtime


def release(diagnosis="base", *, language="sv", analyte="dna", **changes):
    """Make a synthetic published release with a valid content digest."""
    doc = _document(status="published", active=True).model_copy(deep=True)
    doc.scope.diagnosis_id = diagnosis
    doc.scope.language = language
    doc.scope.analyte = analyte
    doc.rule_set_id = f"assay_1__{diagnosis}__{language}"
    doc.content_hash = content_hash(doc)
    return dict(doc.model_dump(mode="python", by_alias=True), **changes)


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
            app=mongo_runtime(),
            clinical_rule_sets_collection=db.rules,
            clinical_rule_revisions_collection=db.revisions,
        )
    )
    found = repository.list_active_for_assay(
        "assay_1",
        diagnosis_id="named",
        analyte="dna",
        language="sv",
    )
    assert [row["scope"]["diagnosis_id"] for row in found] == ["base", "named", "named"]
