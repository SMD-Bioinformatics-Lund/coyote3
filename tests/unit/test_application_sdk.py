"""Local SDK authorization, ownership, context and use-case delegation contracts."""

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.security.policy import build_access_policy
from coyote3.application.common.execution_context import (
    current_request_id,
    current_user,
    reset_current_user,
    set_current_user,
)
from coyote3.application.operations import (
    AnalysisQuery,
    ApplicationRuntime,
    ClinicalServices,
    FlagChange,
)
from coyote3.application.operations.clinical_rules import ClinicalRules
from coyote3.application.operations.governance import ConfigurationProfiles, QueryRules
from coyote3.application.operations.ingest import Ingestion
from coyote3.application.operations.models import TierChange
from coyote3.application.operations.reporting import ReportingServices, Reports
from coyote3.application.operations.samples import Samples
from coyote3.application.reporting.presentation import ReportPresentation
from coyote3.contracts.operations import OperationResult
from coyote3.domain.exceptions import AppError


@pytest.fixture
def sdk():
    actor = SimpleNamespace(
        username="synthetic-reviewer",
        fullname="Synthetic Reviewer",
        roles=["reviewer"],
        is_superuser=False,
        must_change_password=False,
        permissions=["*"],
        asp_ids=["synthetic"],
        asp_groups=["synthetic-group"],
        envs=["testing"],
    )
    grants = {
        "sample:view",
        "snv:manage",
        "cnv:manage",
        "fusion:manage",
        "translocation:manage",
        "tier:assign",
        "tier:remove:own",
        "annotation:publish",
        "report:preview",
        "report:create",
        "internal.ingest:manage",
        "sample:edit:own",
        "query_rules:view",
        "query_rules:draft",
        "query_rules:publish",
        "query_rules:retire",
        "assay.config:list",
        "assay.config:create",
        "configuration:publish",
    }
    roles = SimpleNamespace(
        get_all_roles=lambda: [
            {"role_id": "reviewer", "is_active": True, "permissions": sorted(grants)}
        ]
    )
    permissions = SimpleNamespace(
        get_all_permissions=lambda **kwargs: [
            {"permission_id": permission, "is_active": True} for permission in grants
        ]
    )
    sample = {
        "_id": "sample-1",
        "name": "SYNTHETIC_001",
        "asp_id": "synthetic",
        "asp_category": "dna",
        "environment": "testing",
    }
    identity = Mock(return_value=actor)
    lookup = Mock(
        side_effect=lambda identifier: sample if identifier in {"demo", "sample-1"} else None
    )
    events = []
    runtime = ApplicationRuntime(
        authenticate=identity,
        policy_factory=lambda user: build_access_policy(
            user=user, roles_repository=roles, permissions_repository=permissions
        ),
        sample_loader=lookup,
        assay_loader=lambda identifier: {"asp_group": "synthetic-group"},
        audit_access=events.append,
        correlation_id="synthetic-correlation",
    )
    finding = {"_id": "finding-1", "SAMPLE_ID": "sample-1"}
    classifier = Mock()
    classifier.require_resource_for_sample.return_value = finding
    dna = Mock()
    dna.list_variants_payload.return_value = {
        "variants": [finding],
        "meta": {"tiered": [finding], "page": 1, "total": 1},
    }
    dna.set_variant_flag.return_value = OperationResult(matched_count=1, modified_count=1)
    services = ClinicalServices(
        dna=lambda: dna,
        structural=Mock(),
        rna=Mock(),
        classification=lambda: classifier,
        classification_document=Mock(),
        annotations=Mock(),
        public_annotations=Mock(),
        catalog=Mock(),
        fields=Mock(),
        common_queries=Mock(),
        coverage=Mock(),
        biomarkers=Mock(),
        artifacts=Mock(),
    )
    return SimpleNamespace(
        actor=actor,
        grants=grants,
        runtime=runtime,
        identity=identity,
        lookup=lookup,
        sample=sample,
        events=events,
        dna=dna,
        classifier=classifier,
        services=services,
        samples=Samples(runtime, services),
        finding=finding,
    )


def test_references_are_lazy_and_snapshots_are_detached(sdk):
    sample = sdk.samples.ref("demo")
    sdk.identity.assert_not_called()
    sdk.lookup.assert_not_called()
    snapshot = sample.read()
    assert snapshot.id == "sample-1"
    snapshot.attributes["environment"] = "different"
    assert sdk.sample["environment"] == "testing"
    assert sdk.events[-1].allowed


def test_tiered_selection_is_unpaginated_and_uses_the_existing_service(sdk):
    sample = sdk.samples.ref("demo")
    query = AnalysisQuery(parameters={"intent": "germline", "q": "GENE", "page": "9"})
    assert sample.variants.tiered_variants(query) == [sdk.finding]
    sdk.dna.list_variants_payload.assert_called_once_with(
        sample=sdk.sample, query=query, paginate=False
    )


@pytest.mark.parametrize("change", ["session", "permission", "scope", "group", "password"])
def test_retained_handle_rechecks_identity_and_current_grants(sdk, change):
    sample = sdk.samples.ref("demo")
    sample.variants.tiered_variants()
    sdk.dna.list_variants_payload.reset_mock()
    if change == "session":
        sdk.identity.return_value = None
    elif change == "permission":
        sdk.grants.remove("sample:view")
    elif change == "scope":
        sdk.actor.envs = ["production"]
    elif change == "group":
        sdk.actor.asp_groups = ["different"]
    else:
        sdk.actor.must_change_password = True
    with pytest.raises(AppError) as error:
        sample.variants.tiered_variants()
    assert error.value.status_code == (401 if change == "session" else 403)
    sdk.dna.list_variants_payload.assert_not_called()
    assert not sdk.events[-1].allowed


def test_missing_sample_and_empty_identifier(sdk):
    with pytest.raises(ValueError):
        sdk.samples.ref(" ")
    with pytest.raises(AppError) as error:
        sdk.samples.get("absent")
    assert error.value.status_code == 404
    sdk.dna.assert_not_called()


def test_permission_denial_happens_before_loading_clinical_data(sdk):
    sdk.grants.clear()
    with pytest.raises(AppError):
        sdk.samples.get("demo")
    sdk.lookup.assert_not_called()


def test_context_is_bound_during_service_work_and_restored_on_failure(sdk):
    outer = SimpleNamespace(username="outer")
    token = set_current_user(outer)

    def fail(**kwargs):
        assert current_user() is sdk.actor
        assert current_request_id() == "synthetic-correlation"
        raise ValueError("synthetic service failure")

    sdk.dna.list_variants_payload.side_effect = fail
    try:
        with pytest.raises(ValueError, match="synthetic service failure"):
            sdk.samples.ref("demo").variants.tiered_variants()
        assert current_user() is outer
        assert current_request_id() != "synthetic-correlation"
    finally:
        reset_current_user(token)


def test_audit_failure_prevents_service_execution_and_restores_context(sdk):
    sdk.runtime.audit_access = Mock(side_effect=OSError("synthetic unavailable audit"))
    before = current_user()
    with pytest.raises(OSError):
        sdk.samples.ref("demo").variants.tiered_variants()
    sdk.dna.list_variants_payload.assert_not_called()
    assert current_user() is before


def test_all_finding_ownership_is_validated_before_any_flag_write(sdk):
    sdk.classifier.require_resource_for_sample.side_effect = [
        sdk.finding,
        AppError(404, "Finding not found for sample"),
    ]
    with pytest.raises(AppError):
        sdk.samples.ref("demo").variants.set_flags(
            FlagChange(
                resource_ids=["finding-1", "foreign"],
                flag="interesting",
                value=True,
            )
        )
    sdk.dna.set_variant_flag.assert_not_called()


def test_flags_preserve_the_existing_sample_scoped_write(sdk):
    result = sdk.samples.ref("demo").variants.set_flags(
        FlagChange(
            resource_ids=["finding-1"],
            flag="false_positive",
            value=False,
        )
    )
    assert result[0].modified_count == 1
    sdk.dna.set_variant_flag.assert_called_once_with(
        sample=sdk.sample,
        var_id="finding-1",
        apply=False,
        flag="false_positive",
    )


def test_production_tiering_requires_the_publication_grant(sdk):
    sdk.sample["environment"] = "production"
    sdk.actor.envs = ["production"]
    sdk.grants.remove("annotation:publish")
    with pytest.raises(AppError):
        sdk.samples.ref("demo").set_tiers(
            TierChange(
                resource_type="small_variant",
                resource_ids=["finding-1"],
                tier=2,
            )
        )
    sdk.classifier.set_tier_bulk.assert_not_called()


def test_tiering_prevalidates_ownership_and_retains_clinical_workflow(sdk):
    change = TierChange(resource_type="small_variant", resource_ids=["finding-1"], tier=2)
    sdk.samples.ref("demo").set_tiers(change)
    sdk.classifier.require_resource_for_sample.assert_called_once()
    assert sdk.classifier.set_tier_bulk.call_args.kwargs["class_num"] == 2


def test_annotation_preview_keeps_assignment_permissions_and_ownership_checks(sdk):
    """A read-only preview cannot bypass tier assignment grants or sample ownership."""
    change = TierChange(
        resource_type="small_variant",
        resource_ids=["finding-1"],
        tier=2,
        include_automatic_text=True,
    )
    sdk.grants.remove("tier:assign")
    with pytest.raises(AppError):
        sdk.samples.ref("demo").set_tiers(change, preview=True)
    sdk.classifier.set_tier_bulk.assert_not_called()
    sdk.grants.add("tier:assign")
    sdk.classifier.set_tier_bulk.return_value = [{"resource_id": "finding-1", "text": None}]
    result = sdk.samples.ref("demo").set_tiers(change, preview=True)
    assert result == [{"resource_id": "finding-1", "text": None}]
    sdk.classifier.require_resource_for_sample.assert_called_once()
    assert sdk.classifier.set_tier_bulk.call_args.kwargs["preview_only"] is True


def test_annotation_template_preview_requires_rule_view_permission(sdk):
    """Synthetic previews still require permission to inspect the rule version."""
    from coyote3.contracts.schemas.clinical_rules import BulkAnnotationPreviewRequest

    service = Mock()
    service.preview_bulk_annotation.return_value = {"rule_id": None, "text": None}
    rules = ClinicalRules(sdk.runtime, lambda: service, Mock())
    facts = BulkAnnotationPreviewRequest(tier=2, gene="GENE_A")
    with pytest.raises(AppError):
        rules.preview_bulk_annotation("version", facts)
    service.preview_bulk_annotation.assert_not_called()
    sdk.grants.add("clinical_rules:view")
    assert rules.preview_bulk_annotation("version", facts) == {"rule_id": None, "text": None}


def test_group_deactivation_requires_global_removal_grant(sdk):
    change = TierChange(
        resource_type="small_variant",
        resource_ids=["finding-1"],
        tier=2,
        apply=False,
        deactivation_scope="group",
    )
    with pytest.raises(AppError) as error:
        sdk.samples.ref("demo").set_tiers(change)
    assert error.value.status_code == 403
    sdk.classifier.set_tier_bulk.assert_not_called()
    sdk.grants.add("tier:remove:global")
    sdk.samples.ref("demo").set_tiers(change)
    assert sdk.classifier.set_tier_bulk.call_args.kwargs["deactivation_scope"] == "group"


def test_group_deactivation_rejects_assignment_intent():
    with pytest.raises(ValueError, match="Group deactivation requires apply=false"):
        TierChange(
            resource_type="small_variant",
            resource_ids=["finding-1"],
            tier=2,
            apply=True,
            deactivation_scope="group",
        )


def test_finding_page_and_lookup_return_detached_values(sdk):
    variants = sdk.samples.ref("demo").variants
    page = variants.list()
    assert page.pagination == {"page": 1, "total": 1}
    record = variants.get("finding-1")
    record["SAMPLE_ID"] = "changed"
    assert sdk.finding["SAMPLE_ID"] == "sample-1"


def test_transcript_selection_checks_ownership_before_mutation(sdk):
    sdk.dna.require_variant_for_sample.side_effect = AppError(404, "Finding not found for sample")
    with pytest.raises(AppError):
        sdk.samples.ref("demo").variants.select_transcript("foreign", "synthetic-feature")
    sdk.dna.select_variant_transcript.assert_not_called()


def test_governance_actor_is_the_authenticated_identity_and_errors_propagate(sdk):
    service = Mock()
    profiles = ConfigurationProfiles(sdk.runtime, lambda: service)
    draft = SimpleNamespace(content={"synthetic": True})
    service.create.return_value = {"revision": 1}
    assert profiles.create(draft) == {"revision": 1}
    service.create.assert_called_once_with(draft, actor=sdk.actor.username)
    service.publish.side_effect = AppError(409, "Synthetic stale reviewed hash")
    with pytest.raises(AppError) as error:
        profiles.publish("synthetic", SimpleNamespace(content_hash="x", reason="reviewed"))
    assert error.value.status_code == 409
    sdk.grants.remove("configuration:publish")
    service.publish.reset_mock()
    with pytest.raises(AppError) as error:
        profiles.publish("synthetic", SimpleNamespace(content_hash="x", reason="reviewed"))
    assert error.value.status_code == 403
    service.publish.assert_not_called()


def test_query_policy_preview_validates_scope_and_keeps_lifecycle_author(sdk):
    service = Mock()
    rules = QueryRules(sdk.runtime, lambda: service, Mock())
    request = SimpleNamespace(scope="synthetic", content={})
    service.resolve.return_value = {"synthetic": True}
    assert rules.preview(request) == {"synthetic": True}
    service.validate_scope.assert_called_once_with("synthetic")
    transition = SimpleNamespace(expected_revision=2)
    rules.publish("synthetic", transition)
    service.transition.assert_called_once_with(
        "synthetic", "publish", transition, sdk.actor.username
    )


def test_ingest_preserves_transactional_service_and_verified_attribution(sdk):
    service = Mock()
    service.ingest_sample_bundle.return_value = {
        "status": "created",
        "sample_id": "sample-1",
        "sample_name": "SYNTHETIC_001",
        "data_counts": {"variants": 1},
    }
    request = {
        "name": "SYNTHETIC_001",
        "ingested_by": "spoofed",
        "asp_id": "synthetic",
        "environment": "testing",
    }
    result = Ingestion(sdk.runtime, lambda: service, Mock()).sample_bundle(request)
    assert result.sample_id == "sample-1"
    assert service.ingest_sample_bundle.call_args.kwargs["ingested_by"] == sdk.actor.username
    assert service.ingest_sample_bundle.call_args.args[0] is not request


def test_report_save_rejects_stale_preview_before_any_artifact_or_number(sdk):
    workflow = Mock()
    workflow.build_report_payload.return_value = ("dna_report.html", {"sample": {}}, [])
    renderer = Mock(return_value="<p>synthetic</p>")
    reports = Reports(
        sdk.runtime,
        ReportingServices(
            library=Mock(),
            render_pdf=Mock(return_value=b"synthetic-pdf"),
            workflow=lambda analyte: workflow,
            configuration=lambda sample: {"synthetic": True},
            render_html=renderer,
            organization_name="Synthetic",
            reports_base_path="reports",
            logger=Mock(),
        ),
    )
    preview = reports.preview("demo", "dna")
    assert len(preview.fingerprint) == 64
    with pytest.raises(AppError) as error:
        reports.save("demo", "dna", fingerprint="0" * 64)
    assert error.value.status_code == 409
    workflow.next_report_num.assert_not_called()
    workflow.prepare_report_output.assert_not_called()
    workflow.persist_report.assert_not_called()


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_report_trial_generates_matching_outputs_without_persistence(sdk, analyte):
    sdk.sample["asp_category"] = analyte
    workflow = Mock()
    workflow.build_report_payload.return_value = (
        "dna_report.html",
        {"sample": {"name": "SYNTHETIC"}},
        [{"gene": "TP53"}],
    )
    html = "<html><body>Same clinical findings</body></html>"
    render_pdf = Mock(return_value=b"%PDF-synthetic")
    trial_renderer = Mock(return_value=html)
    reports = Reports(
        sdk.runtime,
        ReportingServices(
            library=Mock(),
            workflow=lambda modality: workflow,
            configuration=lambda sample: {"synthetic": True},
            render_html=Mock(return_value="Established clinical content"),
            render_trial_html=trial_renderer,
            render_pdf=render_pdf,
            organization_name="Synthetic",
            reports_base_path="never-used",
            logger=Mock(),
        ),
    )
    result = reports.try_new("demo", analyte)
    assert result.html == html
    assert result.pdf == b"%PDF-synthetic"
    assert result.snapshot_count == 1
    assert "without an automatically generated summary" in result.reporting_warning
    render_pdf.assert_called_once_with(result.html)
    assert trial_renderer.call_count == 1
    assert trial_renderer.call_args.kwargs["snapshot_rows"] == [{"gene": "TP53"}]
    assert trial_renderer.call_args.kwargs["preview"] is True
    assert workflow.build_report_payload.call_args.kwargs["save"] == 0
    workflow.next_report_num.assert_not_called()
    workflow.build_report_location.assert_not_called()
    workflow.prepare_report_output.assert_not_called()
    workflow.persist_report.assert_not_called()
    sdk.grants.remove("report:preview")
    with pytest.raises(AppError) as error:
        reports.try_new("demo", analyte)
    assert error.value.status_code == 403
    assert render_pdf.call_count == 1


def test_changed_modern_wording_requires_a_new_preview_before_save(sdk):
    """Reject changed host wording before allocating a report number or writing artifacts."""
    workflow = Mock()
    workflow.build_report_payload.return_value = ("modern/dna_report.html", {"sample": {}}, [])
    wording = {"empty_results": {"SNV": "First reviewed message"}}
    reports = Reports(
        sdk.runtime,
        ReportingServices(
            library=Mock(),
            render_pdf=Mock(),
            workflow=lambda analyte: workflow,
            configuration=lambda sample: {"synthetic": True},
            render_html=Mock(return_value=""),
            organization_name="Synthetic",
            reports_base_path="reports",
            logger=Mock(),
            presentation=lambda: ReportPresentation.model_validate(wording),
        ),
    )
    preview = reports.preview("demo", "dna")
    assert (
        preview.context["report_presentation"]["empty_results"]["SNV"] == "First reviewed message"
    )
    wording["empty_results"]["SNV"] = "Changed message"
    with pytest.raises(AppError, match="Refresh and review"):
        reports.save("demo", "dna", fingerprint=preview.fingerprint)
    workflow.next_report_num.assert_not_called()
    workflow.prepare_report_output.assert_not_called()
    workflow.persist_report.assert_not_called()


def test_report_save_retains_snapshot_receipt_and_authenticated_author(sdk):
    from coyote3.application.common.release_resources import capture_assay_resource

    workflow = Mock()
    panel = {"asp_id": "synthetic", "asp_group": "synthetic-group"}
    configuration = {**panel, "assay_resource_release": capture_assay_resource(panel)}
    context = {
        "sample": {},
        "assay_config": configuration,
        "clinical_rule_evaluation": {
            "source": {"version": 1},
            "trace": [{"matched": True, "rule_id": "synthetic-rule"}],
        },
    }
    workflow.build_report_payload.return_value = ("dna_report.html", context, [{"synthetic": True}])
    workflow.next_report_num.return_value = 2
    workflow.build_report_location.return_value = ("synthetic-report", "reports", "synthetic.html")
    workflow.persist_report.return_value = ("synthetic-storage-id", "synthetic.pdf")
    reports = Reports(
        sdk.runtime,
        ReportingServices(
            library=Mock(),
            render_pdf=Mock(return_value=b"synthetic-pdf"),
            workflow=lambda analyte: workflow,
            configuration=lambda sample: {"synthetic": True},
            render_html=Mock(return_value="<p>synthetic</p>"),
            organization_name="Synthetic",
            reports_base_path="reports",
            logger=Mock(),
        ),
    )
    preview = reports.preview("demo", "dna", include_snapshot=True)
    saved = reports.save("demo", "dna", fingerprint=preview.fingerprint)
    assert saved.storage_id == "synthetic-storage-id"
    values = workflow.persist_report.call_args.kwargs
    assert values["created_by"] == sdk.actor.username
    assert values["snapshot_rows"] == [{"synthetic": True}]
    assert values["rule_provenance"]["matched_rule_ids"] == ["synthetic-rule"]
    assert isinstance(values["resolution_snapshot"], dict)


def test_clinical_rule_publication_requires_grant_and_retains_reviewer_checks(sdk):
    service = Mock()
    rules = ClinicalRules(sdk.runtime, lambda: service, Mock())
    transition = SimpleNamespace(reason="synthetic review")
    with pytest.raises(AppError) as denied:
        rules.publish("synthetic", transition)
    assert denied.value.status_code == 403
    service.publish.assert_not_called()
    sdk.grants.add("clinical_rules:publish")
    service.publish.side_effect = AppError(409, "This publication is assigned to another user")
    with pytest.raises(AppError) as conflict:
        rules.publish("synthetic", transition)
    assert conflict.value.status_code == 409
    service.publish.assert_called_once_with("synthetic", transition, actor=sdk.actor.username)


def test_worker_identity_is_distinct_from_the_original_submitter(sdk):
    from api.app.application_factory import ingest_job_executor

    def ingest(payload, *, ingested_by, record_completion, **kwargs):
        assert current_user().username == "celery-ingest"
        assert ingested_by == "original-synthetic-submitter"
        result = {"status": "ok"}
        record_completion(result, "synthetic-transaction")
        return result

    service = SimpleNamespace(ingest_sample_bundle=ingest)
    observer, completion = Mock(), Mock()
    executor = ingest_job_executor(service, audit_access=observer)
    before = current_user()
    assert executor.execute(
        {
            "kind": "sample_bundle",
            "source_payload": {},
            "update_existing": False,
            "increment": False,
            "submitted_by": "original-synthetic-submitter",
        },
        record_completion=completion,
    ) == {"status": "ok"}
    completion.assert_called_once_with({"status": "ok"}, "synthetic-transaction")
    assert current_user() is before
    with pytest.raises(AppError) as denied:
        Samples(executor._runtime, sdk.services).get("demo")
    assert denied.value.status_code == 403
    sdk.lookup.assert_not_called()


def test_deployment_factory_revalidates_session_and_does_not_audit_credentials(sdk, monkeypatch):
    from api.app import application_factory as composition
    from api.app.deps import repositories, services

    sessions = SimpleNamespace(get=Mock(return_value=SimpleNamespace(user=sdk.actor)))
    audit = SimpleNamespace(record=Mock(return_value="synthetic-audit-id"))
    monkeypatch.setattr(services, "get_api_session_repository", lambda: sessions)
    monkeypatch.setattr(services, "get_audit_service", lambda: audit)
    monkeypatch.setattr(
        repositories,
        "get_sample_repository",
        lambda: SimpleNamespace(get_sample=sdk.lookup, get_sample_by_id=Mock(return_value=None)),
    )
    monkeypatch.setattr(
        repositories,
        "get_assay_panel_repository",
        lambda: SimpleNamespace(get_asp=lambda identity: {"asp_group": "synthetic-group"}),
    )
    monkeypatch.setattr(repositories, "get_roles_repository", lambda: None)
    monkeypatch.setattr(repositories, "get_permissions_repository", lambda: None)
    monkeypatch.setattr(
        "api.security.policy.build_access_policy",
        lambda **values: sdk.runtime.policy_factory(values["user"]),
    )
    monkeypatch.setattr(
        composition,
        "application_services",
        lambda: SimpleNamespace(
            clinical=sdk.services,
            administration=Mock(),
            public=Mock(),
            change_password=Mock(),
            password_recovery=Mock(),
            operations=Mock(),
            knowledgebase=Mock(),
            notifications=Mock(),
            knowledgebase_search_limit=1000,
            reporting=Mock(),
            ingest=Mock(),
            ingest_submission=Mock(),
            internal_references=Mock(),
            query_rules=Mock(),
            clinical_rules=Mock(),
            query_rule_testing=Mock(),
            clinical_rule_testing=Mock(),
            configuration_profiles=Mock(),
            configuration_promotions=Mock(),
        ),
    )
    app = composition.open_application("synthetic-session-secret")
    ref = app.samples.ref("demo")
    assert ref.read().name == "SYNTHETIC_001"
    sessions.get.return_value = None
    with pytest.raises(AppError) as denied:
        ref.read()
    assert denied.value.status_code == 401
    assert sessions.get.call_count == 2
    assert "synthetic-session-secret" not in repr(audit.record.call_args_list)


def test_provider_projection_happens_after_canonical_release_validation(sdk):
    from bson import ObjectId

    from api.infra.mongo.records import application_result
    from coyote3.application.common.release_resources import assay_resource, capture_assay_resource
    from coyote3.application.operations import IngestResult

    native_id = ObjectId()
    panel = {"_id": native_id, "asp_id": "synthetic", "asp_group": "synthetic-group"}
    configuration = {**panel, "assay_resource_release": capture_assay_resource(panel)}
    sdk.sample["configuration"] = configuration
    sdk.runtime.project_result = application_result

    def read(*, sample, **kwargs):
        assert assay_resource(sample["configuration"])["_id"] == native_id
        return {"meta": {"tiered": [{"_id": native_id}]}}

    sdk.dna.list_variants_payload.side_effect = read
    selected = sdk.samples.ref("demo").variants.tiered_variants()
    assert selected == [{"_id": str(native_id)}]
    assert sdk.sample["configuration"]["assay_resource_release"]["content"]["_id"] == native_id
    result = application_result(
        IngestResult(
            status="ok", sample_id="synthetic", sample_name="synthetic", details={"id": native_id}
        )
    )
    assert isinstance(result, IngestResult)
    assert result.model_extra["details"]["id"] == str(native_id)


def test_importing_supported_sdk_does_not_load_server_or_storage_runtime():
    script = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fastapi', 'starlette', 'bson', 'pymongo', 'celery', 'redis'}:
            raise AssertionError(fullname)
        if fullname.startswith(('api.app', 'api.infra', 'api.security', 'api.interfaces', 'coyote3_client')) and not fullname.startswith('coyote3.application'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from coyote3.application.operations import CoyoteApplication, AnalysisQuery, TierChange
from coyote3.application.operations.inputs import QueryRuleDraft, ClinicalRuleTransition
assert AnalysisQuery().parameters == {}
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "form,grant",
    [
        ({"roles": []}, "user:role:edit"),
        ({"asp_ids": []}, "user:group:edit"),
        ({"asp_groups": []}, "user:group:edit"),
        ({"environments": []}, "user:group:edit"),
    ],
)
@pytest.mark.parametrize(
    "operation,base_grant", [("create_user", "user:create"), ("update_user", "user:edit")]
)
def test_account_assignments_require_dedicated_grants_for_local_callers(
    sdk, form, grant, operation, base_grant
):
    """Clearing assignments cannot bypass role/group grants through the local SDK."""
    from coyote3.application.operations import Users

    sdk.grants.add(base_grant)
    service = Mock()
    getattr(service, operation).return_value = {"status": "ok"}
    operations = Users(sdk.runtime, lambda: service)
    arguments = {"payload": {"form_data": form}}
    if operation == "update_user":
        arguments["user_id"] = "synthetic-account"
    with pytest.raises(AppError) as denied:
        getattr(operations, operation)(**arguments)
    assert denied.value.status_code == 403
    assert grant in sdk.events[-1].permissions
    assert not service.method_calls

    sdk.grants.add(grant)
    getattr(operations, operation)(**arguments)
    values = getattr(service, operation).call_args.kwargs
    assert values["actor_username"] == sdk.actor.username
    assert values["actor_is_superuser"] is False


def test_profile_operation_uses_current_actor_and_rechecks_session(sdk):
    """Authenticated-only profile edits never accept a target account or retain credentials."""
    from coyote3.application.operations import Account

    service = Mock()
    service.update_own_profile.return_value = {"status": "ok"}
    account = Account(sdk.runtime, lambda: service, Mock())
    assert account.update_profile({"fullname": "Synthetic"}) == {"status": "ok"}
    service.update_own_profile.assert_called_once_with(
        username=sdk.actor.username, payload={"fullname": "Synthetic"}
    )
    sdk.identity.return_value = None
    with pytest.raises(AppError) as denied:
        account.update_profile({"fullname": "Changed"})
    assert denied.value.status_code == 401
    assert service.update_own_profile.call_count == 1


def test_temporary_password_allows_only_its_own_replacement(sdk):
    """The direct SDK retains first-login restrictions while allowing password replacement."""
    from coyote3.application.operations import Account
    from coyote3.application.operations.inputs import ApiPasswordChangeRequest

    sdk.actor.must_change_password = True
    change = Mock(return_value={"status": "ok"})
    service = Mock()
    account = Account(sdk.runtime, lambda: service, change)
    with pytest.raises(AppError) as denied:
        account.update_ui_settings({"theme": "dark"})
    assert denied.value.status_code == 403
    with pytest.raises(AppError) as missing_confirmation:
        account.change_password(
            ApiPasswordChangeRequest(
                current_password="SyntheticOld!123", new_password="SyntheticNew!123"
            )
        )
    assert missing_confirmation.value.status_code == 400
    change.assert_not_called()
    account.change_password(
        ApiPasswordChangeRequest(
            current_password="SyntheticOld!123",
            new_password="SyntheticNew!123",
            confirm_password="SyntheticNew!123",
        )
    )
    assert change.call_args.kwargs["user_id"] == sdk.actor.username
    assert not service.method_calls
    assert all(
        "SyntheticOld!123" not in repr(event.model_dump())
        and "SyntheticNew!123" not in repr(event.model_dump())
        for event in sdk.events
    )


def test_sample_ingest_scope_is_checked_before_the_transaction(sdk):
    """A valid ingestion grant cannot authorize another environment's manifest."""
    service = Mock()
    operations = Ingestion(sdk.runtime, lambda: service, Mock())
    with pytest.raises(AppError) as denied:
        operations.sample_bundle(
            {"name": "Synthetic", "asp_id": "synthetic", "environment": "production"}
        )
    assert denied.value.status_code == 403
    service.ingest_sample_bundle.assert_not_called()


def test_machine_audience_cannot_be_reused_for_collection_ingestion(sdk):
    """Even an ingestion grant is insufficient outside the fixed credential audience."""
    sdk.runtime.allowed_operations = frozenset({"ingest.sample_bundle"})
    sdk.actor.is_superuser = True
    service = Mock()
    operations = Ingestion(sdk.runtime, lambda: service, Mock())
    with pytest.raises(AppError) as denied:
        operations.insert_document(collection="users", document={"username": "Synthetic"})
    assert denied.value.status_code == 403
    assert not sdk.events[-1].allowed
    assert not service.method_calls


def test_bearer_session_is_available_to_http_sdk_composition(monkeypatch):
    """SDK composition resolves the same bearer credential used by HTTP authorization."""
    from starlette.requests import Request

    from api.security import access

    session = SimpleNamespace(token="synthetic-bearer")
    repository = SimpleNamespace(get=Mock(return_value=session))
    monkeypatch.setattr(access, "get_api_session_repository", lambda: repository)
    request = Request({"type": "http", "headers": [(b"authorization", b"Bearer synthetic-bearer")]})
    assert access.get_request_api_session(request) is session
    repository.get.assert_called_once_with("synthetic-bearer")


def test_maintenance_worker_cannot_invoke_interactive_resources(sdk, monkeypatch):
    """A fixed maintenance identity can run its task and cannot reuse that grant for UI work."""
    from api.app.application_factory import maintenance_executor
    from api.app.deps import services

    maintenance = SimpleNamespace(run_maintenance=Mock(return_value={"removed": 2}))
    monkeypatch.setattr(services, "get_app_controls_service", lambda: maintenance)
    executor = maintenance_executor(Mock())
    assert executor.retention() == {"removed": 2}
    from api.app.runtime_state import app

    monkeypatch.setitem(app.config, "AUDIT_CHECKPOINT_DIRECTORY", "")
    assert executor.export_audit_checkpoint() == {"status": "not_configured"}
    with pytest.raises(AppError) as denied:
        Samples(executor._runtime, sdk.services).get("demo")
    assert denied.value.status_code == 403
    sdk.lookup.assert_not_called()
