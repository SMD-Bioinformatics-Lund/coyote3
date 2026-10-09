"""Synthetic tests for hierarchical query-policy governance and query isolation."""

from types import SimpleNamespace

import mongomock
import pytest
from pydantic import ValidationError

from api.application.query_rules import QueryRuleService
from api.contracts.schemas.query_rules import (
    QueryRuleContent,
    QueryRuleDoc,
    QueryRuleDraft,
    QueryRulePreview,
    QueryRuleScope,
    QueryRuleTransition,
    QueryRuleUpdate,
)
from api.domain.core.exceptions import AppError
from api.domain.query_conditions import condition_catalog
from api.infra.mongo.repositories import query_rules as persistence


def test_condition_choices_expose_references_without_loading_or_copying_values():
    choices = QueryRuleService(None).condition_options()
    assert "gene_lists" not in choices
    snv = {field["path"]: field for field in choices["fields"]["snv"]}
    assert snv["INFO.selected_CSQ.SYMBOL"]["value_role"] == "gene"
    assert snv["INFO.selected_CSQ.SYMBOL"]["filter_references"][0]["key"] == "snvlists"
    assert snv["GT.DP"]["filter_references"][0]["key"] == "min_depth"
    assert snv["INFO.selected_CSQ.CADD_PHRED"]["kind"] == "string"
    assert "SAMPLE_ID" not in snv
    assert all("suggestions" not in field for field in condition_catalog()["fields"]["snv"])
    fusion = {field["path"]: field for field in choices["fields"]["fusion"]}
    assert "value_role" not in fusion["genes"]
    assert fusion["gene1"]["value_role"] == "gene"


@pytest.fixture
def service(monkeypatch):
    """Use only an in-memory Mongo substitute, never an installed database."""
    collection = mongomock.MongoClient().synthetic.query_rule_sets
    repository = persistence.QueryRuleRepository(
        SimpleNamespace(
            query_rule_sets_collection=collection,
            query_rule_revisions_collection=collection.database.query_rule_revisions,
        )
    )
    repository.ensure_indexes()
    monkeypatch.setattr(persistence, "run_transaction", lambda client, operation: operation(None))
    monkeypatch.setattr(persistence, "enqueue_audit", lambda *args, **kwargs: None)
    return QueryRuleService(
        repository,
        groups=SimpleNamespace(get=lambda key: {"group_id": key} if key == "example" else None),
        assays=SimpleNamespace(
            get_asp=lambda key: (
                {"asp_id": key, "asp_group": "example", "asp_category": "dna"}
                if key == "panel"
                else None
            )
        ),
        subpanels=SimpleNamespace(
            get_current=lambda assay, panel: (
                {"subpanel_id": panel, "is_active": True, "definition_is_active": True}
                if panel == "myeloid"
                else None
            )
        ),
    )


def scope(**values):
    """Create a synthetic clinical scope with explicit overrides."""
    return QueryRuleScope(assay_group="example", analysis="snv", **values)


def draft(selected=None, **content):
    """Build a valid editable version with a documented synthetic purpose."""
    return QueryRuleDraft(
        scope=selected or scope(),
        name="Example",
        reason="Validation",
        content=QueryRuleContent(**content),
    )


def release(service, selected=None, **content):
    """Exercise creation, independent approval and publication in memory."""
    row = service.create(draft(selected, **content), "author")
    identifier = str(row["_id"])
    service.transition(
        identifier,
        "approve",
        QueryRuleTransition(expected_revision=1, reason="Reviewed"),
        "reviewer",
    )
    return service.transition(
        identifier,
        "publish",
        QueryRuleTransition(expected_revision=2, reason="Validated"),
        "publisher",
    )


def test_default_and_field_inheritance(service):
    target = scope(asp_id="panel", subpanel_id="myeloid")
    assert service.resolve(target).evidence_mode == "paired"
    exception = {"id": "example", "mode": "exclude", "genes": ["TP53"]}
    release(service, evidence_mode="case_only", exceptions=[exception])
    release(service, scope(asp_id="panel"), exceptions=[])
    result = service.resolve(target)
    assert result.evidence_mode == "case_only"
    assert result.exceptions == []
    release(service, target, evidence_mode="exception_only")
    result = service.resolve(target)
    assert result.evidence_mode == "exception_only"
    assert result.exceptions == []
    assert len(result.lineage) == 4
    sibling = service.resolve(scope(asp_id="different"))
    assert sibling.evidence_mode == "case_only"
    assert sibling.exceptions == [exception]


def test_somatic_snv_composes_germline_exceptions_without_replacing_evidence(service):
    release(service, evidence_mode="case_only", exceptions=[])
    parent = {"id": "marker", "mode": "admit", "filter_values": ["GERMLINE"]}
    release(
        service,
        QueryRuleScope(analysis="snv", intent="germline"),
        evidence_mode="exception_only",
        exceptions=[parent],
    )
    result = service.resolve(scope())
    assert result.evidence_mode == "case_only"
    assert result.exceptions == [{**parent, "id": "germline__marker"}]
    assert any(row.get("application") == "somatic_snv_exceptions" for row in result.lineage)
    # A somatic replacement does not silently remove the independently governed germline set.
    assert service.resolve(scope(), QueryRuleContent(exceptions=[])).exceptions == result.exceptions
    assert service.resolve(QueryRuleScope(analysis="cnv", assay_group="example")).exceptions == []
    release(service, scope(intent="germline"), exceptions=[])
    assert service.resolve(scope()).exceptions == []


def test_draft_deletion_retains_audit_but_removes_private_history(service):
    row = service.create(draft(), "author")
    oid = str(row["_id"])
    assert len(service.revisions(oid)) == 1
    service.delete_draft(
        oid, QueryRuleTransition(expected_revision=1, reason="Unused draft"), "author"
    )
    assert service.repository.get(oid) is None
    assert service.repository.history.list_for_version(oid) == []


def test_published_versions_have_immutable_history_and_cannot_be_deleted(service):
    row = release(service)
    oid = str(row["_id"])
    assert [r["action"] for r in service.revisions(oid)] == ["published", "approved", "created"]
    with pytest.raises(AppError, match="Only an unchanged draft"):
        service.delete_draft(
            oid,
            QueryRuleTransition(expected_revision=row["revision"], reason="Forbidden"),
            "author",
        )
    snapshot = service.repository.revisions.find_one({"rule_oid": oid})
    service.repository.revisions.update_one(
        {"_id": snapshot["_id"]}, {"$set": {"document.name": "tampered"}}
    )
    with pytest.raises(RuntimeError, match="integrity"):
        service.revisions(oid)


def test_extension_keeps_parent_rules_and_replacement_can_redefine_them(service):
    parent = {"id": "parent", "mode": "exclude", "genes": ["TP53"]}
    extra = {"id": "extra", "mode": "exclude", "genes": ["BRAF"]}
    release(service, exceptions=[parent])
    child = scope(asp_id="panel")
    release(service, child, exception_mode="extend", exceptions=[extra])
    assert service.resolve(child).exceptions == [parent, extra]
    assert service.resolve(scope()).exceptions == [parent]
    assert service.resolve(
        child, QueryRuleContent(exception_mode="extend", exceptions=[])
    ).exceptions == [parent]
    refined = {**parent, "genes": ["KRAS"]}
    assert service.resolve(child, QueryRuleContent(exceptions=[refined])).exceptions == [refined]
    with pytest.raises(AppError, match="identifiers distinct"):
        service.create(draft(child, exception_mode="extend", exceptions=[refined]), "author")


def test_parent_publication_cannot_introduce_collision_in_published_extension(service):
    release(service, exceptions=[])
    extra = {"id": "child-only", "mode": "exclude", "genes": ["TP53"]}
    child = scope(asp_id="panel")
    release(service, child, exception_mode="extend", exceptions=[extra])
    with pytest.raises(AppError, match="identifiers distinct"):
        release(service, exceptions=[extra])
    assert service.resolve(scope()).exceptions == []
    assert service.resolve(child).exceptions == [extra]


def test_global_publication_applies_to_groups_and_retirement_restores_base(service):
    global_scope = QueryRuleScope(analysis="snv")
    row = release(service, global_scope, evidence_mode="case_only")
    assert service.resolve(scope()).evidence_mode == "case_only"
    release(service, evidence_mode="exception_only")
    assert service.resolve(scope()).evidence_mode == "exception_only"
    assert (
        service.resolve(QueryRuleScope(analysis="snv", assay_group="other")).evidence_mode
        == "case_only"
    )
    service.transition(
        str(row["_id"]),
        "retire",
        QueryRuleTransition(expected_revision=3, reason="Withdraw"),
        "publisher",
    )
    assert (
        service.resolve(QueryRuleScope(analysis="snv", assay_group="other")).evidence_mode
        == "paired"
    )


def test_preview_inherits_parent_instead_of_previous_leaf(service):
    release(service, evidence_mode="case_only")
    child = scope(asp_id="panel")
    release(service, child, evidence_mode="exception_only")
    assert service.resolve(child, QueryRuleContent()).evidence_mode == "case_only"
    assert service.resolve(child).evidence_mode == "exception_only"


def test_drafts_and_other_intents_do_not_change_live_policy(service):
    service.create(draft(evidence_mode="case_only"), "author")
    assert service.resolve(scope()).evidence_mode == "paired"
    release(service, scope(intent="germline"), evidence_mode="case_only")
    assert service.resolve(scope()).evidence_mode == "paired"
    assert service.resolve(scope(intent="germline")).evidence_mode == "case_only"
    assert (
        service.resolve(QueryRuleScope(assay_group="other", analysis="snv")).evidence_mode
        == "paired"
    )


def test_publication_supersedes_and_retirement_restores_parent(service):
    first = release(service, evidence_mode="case_only")
    second = release(service, evidence_mode="exception_only")
    assert second["version"] == 2
    assert service.repository.get(str(first["_id"]))["status"] == "retired"
    service.transition(
        str(second["_id"]),
        "retire",
        QueryRuleTransition(expected_revision=3, reason="Retire"),
        "publisher",
    )
    assert service.resolve(scope()).evidence_mode == "paired"
    assert len(service.repository.list()) == 2


def test_independent_approval_revision_and_immutability(service):
    row = service.create(draft(), "author")
    identifier = str(row["_id"])
    transition = QueryRuleTransition(expected_revision=1, reason="Review")
    with pytest.raises(AppError) as error:
        service.transition(identifier, "approve", transition, "author")
    assert error.value.status_code == 403
    update = QueryRuleUpdate(**draft().model_dump(), expected_revision=1)
    service.update(identifier, update, "editor")
    with pytest.raises(AppError) as error:
        service.update(identifier, update, "editor")
    assert error.value.status_code == 409
    with pytest.raises(AppError):
        service.transition(
            identifier,
            "approve",
            QueryRuleTransition(expected_revision=2, reason="Review"),
            "editor",
        )
    service.transition(
        identifier, "approve", QueryRuleTransition(expected_revision=2, reason="Review"), "reviewer"
    )
    with pytest.raises(AppError):
        service.update(
            identifier, QueryRuleUpdate(**draft().model_dump(), expected_revision=3), "author"
        )


@pytest.mark.parametrize(
    "exception",
    [
        {"id": "unsafe", "mode": "admit", "$where": "true"},
        {"id": "unsafe", "mode": "admit", "info_equals": {"DP": {"$gt": 0}}},
        {"id": "unsafe", "mode": "admit", "info_equals": []},
        {"id": "unsafe", "mode": "admit", "asp_ids": ["other"], "genes": ["TP53"]},
        {"id": "empty", "mode": "admit"},
        {"id": "fraction", "mode": "admit", "position_min": 1.5},
        {"id": "negative", "mode": "admit", "position_min": -1},
        {"id": "object", "mode": "admit", "genes": [{"$ne": "TP53"}]},
    ],
)
def test_unsafe_or_unbounded_criteria_rejected(exception):
    with pytest.raises(ValidationError):
        draft(exceptions=[exception])


def test_invalid_preview_is_request_validation_error():
    with pytest.raises(ValidationError):
        QueryRulePreview(scope=scope(), content={"exceptions": [{"id": "x", "mode": "invalid"}]})


def test_invalid_hierarchy_and_registry_membership(service):
    with pytest.raises(ValidationError):
        scope(subpanel_id="myeloid")
    with pytest.raises(AppError):
        service.create(draft(scope(asp_id="other")), "author")
    with pytest.raises(AppError):
        service.create(draft(scope(asp_id="panel", subpanel_id="unregistered")), "author")
    with pytest.raises(ValidationError):
        QueryRuleScope(assay_group="example", analysis="cnv", intent="germline")


def test_compiled_policy_preserves_scoping_and_literal_exceptions(service):
    from api.domain.core.dna.varqueries import build_query

    release(
        service,
        evidence_mode="case_only",
        exceptions=[{"id": "exclude", "mode": "exclude", "genes": ["TP53"]}],
    )
    policy = service.policy(
        analysis="snv", assay_group="example", asp_id="panel", subpanel_id="myeloid"
    )
    assert policy.exceptions[0].genes == ("TP53",)
    # The typed policy cannot modify identity predicates supplied by the query builder.
    from tests.unit.test_dna_varqueries import _settings

    query = build_query("example", _settings(id="sample-one"), policy=policy)
    assert "sample-one" in str(query)
    assert "TP53" in str(query)


def test_document_identity_is_serializable_and_scope_is_checked(service):
    row = service.create(draft(), "author")
    assert QueryRuleDoc.model_validate(row).model_dump(mode="json", by_alias=True)["_id"] == str(
        row["_id"]
    )
    with pytest.raises(ValidationError):
        QueryRuleDoc.model_validate({**row, "scope_key": "wrong"})


def test_base_scope_does_not_require_a_named_subpanel_record(service):
    release(service, scope(asp_id="panel", subpanel_id="base"), evidence_mode="case_only")
    assert service.resolve(scope(asp_id="panel", subpanel_id="base")).evidence_mode == "case_only"
    assert (
        service.resolve(scope(asp_id="panel", subpanel_id="myeloid")).evidence_mode == "case_only"
    )


def test_generated_identity_normalizes_base_and_separates_analysis():
    assert scope().key() == "example__all__base__somatic_snvs"
    assert scope(asp_id="panel", subpanel_id="base").key() == "example__panel__base__somatic_snvs"
    assert (
        scope(asp_id="panel", subpanel_id="myeloid").key()
        == "example__panel__myeloid__somatic_snvs"
    )
    assert (
        QueryRuleScope(analysis="cnv", assay_group="example").key()
        == "example__all__base__somatic_cnvs"
    )
    assert (
        QueryRuleScope(analysis="snv", intent="germline").key()
        == "default__all__base__germline_snvs"
    )


@pytest.mark.parametrize("analysis", ["cnv", "translocation", "fusion"])
def test_structural_rules_compile_and_remain_analysis_specific(service, analysis):
    selected = QueryRuleScope(assay_group="example", analysis=analysis)
    release(service, selected, exceptions=[{"id": "exclude", "mode": "exclude", "genes": ["TP53"]}])
    policy = service.policy(
        analysis=analysis, assay_group="example", asp_id="panel", subpanel_id="myeloid"
    )
    assert policy.exceptions[0].criteria["genes"] == ("TP53",)
    assert service.resolve(scope()).exceptions == []


def test_retirement_remains_possible_after_registry_deactivation(service):
    row = release(service, evidence_mode="case_only")
    service.groups.get = lambda key: {"is_active": False}
    service.transition(
        str(row["_id"]),
        "retire",
        QueryRuleTransition(expected_revision=3, reason="Withdraw inactive scope"),
        "publisher",
    )
    assert service.resolve(scope()).evidence_mode == "paired"


def test_cnv_workflow_uses_published_policy_and_keeps_sample_identity(service):
    from unittest.mock import Mock

    from api.application.dna.structural_variants import DnaStructuralService

    release(
        service,
        QueryRuleScope(assay_group="example", analysis="cnv"),
        exceptions=[{"id": "exclude", "mode": "exclude", "genes": ["TP53"]}],
    )
    repository = SimpleNamespace(get_sample_cnvs=Mock(return_value=[]))
    workflow = DnaStructuralService(
        copy_number_variant_repository=repository,
        translocation_repository=None,
        assay_panel_repository=None,
        gene_list_repository=None,
        bam_record_repository=None,
        vep_metadata_repository=None,
        cosmic_repository=None,
        query_rule_service=service,
    )
    workflow.load_cnvs_for_sample(
        sample={"_id": "sample-one", "asp_id": "panel"},
        sample_filters={
            "cnv_loss_cutoff": 0.5,
            "cnv_gain_cutoff": 1.5,
            "min_cnv_size": 0,
            "max_cnv_size": 1000000,
        },
        filter_genes=[],
        assay_group="example",
    )
    query = repository.get_sample_cnvs.call_args.args[0]
    assert query["SAMPLE_ID"] == "sample-one"
    assert "TP53" in str(query) and "$nor" in str(query)


def test_condition_tree_survives_publication_inheritance_and_preview(service):
    condition = {
        "type": "any",
        "children": [
            {"type": "predicate", "field": "size", "operator": "gte", "value": 1000},
            {"type": "predicate", "field": "ratio", "operator": "gte", "value": 2},
        ],
    }
    release(
        service,
        QueryRuleScope(assay_group="example", analysis="cnv"),
        exceptions=[{"id": "nested", "mode": "exclude", "condition": condition}],
    )
    leaf = QueryRuleScope(
        assay_group="example", asp_id="panel", subpanel_id="myeloid", analysis="cnv"
    )
    result = service.resolve(leaf)
    assert result.exceptions[0]["condition"] == condition
    assert result.compiled_conditions == [
        {
            "id": "nested",
            "mode": "exclude",
            "predicate": {"$or": [{"size": {"$gte": 1000}}, {"ratio": {"$gte": 2}}]},
        }
    ]
    assert service.resolve(leaf, QueryRuleContent(exceptions=[])).compiled_conditions == []
    assert service.resolve(leaf).exceptions[0]["condition"] == condition


def test_rna_workflow_uses_published_policy_and_keeps_sample_identity(service):
    from api.application.reporting.rna_workflow import RNAWorkflowService

    release(
        service,
        QueryRuleScope(assay_group="example", analysis="fusion"),
        exceptions=[{"id": "exclude", "mode": "exclude", "genes": ["TP53"]}],
    )
    query = RNAWorkflowService.build_fusion_list_query(
        "example",
        "sample-one",
        {},
        {
            "fusion_effects": [],
            "fusion_callers": [],
            "fusion_descriptions": [],
            "checked_fusionlists": [],
            "filter_genes": [],
            "restrict_to_genes": False,
        },
        asp_id="panel",
        subpanel_id="base",
        query_rule_service=service,
    )
    assert query["SAMPLE_ID"] == "sample-one"
    assert "TP53" in str(query) and "$nor" in str(query)
