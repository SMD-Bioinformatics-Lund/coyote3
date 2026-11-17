"""Resource reads always authenticate, audit and authorize before persistence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.operations.resource_reads import ResourceReads
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.contracts.retrieval import ReadResource, ResourceReadPage, ResourceReadQuery
from coyote.domain.exceptions import AppError


@pytest.fixture
def boundary():
    actor = SimpleNamespace(
        is_superuser=False,
        roles=[],
        asp_groups=["dna"],
        assay_access=[{"asp_id": "panel", "environments": ["production"]}],
        permissions={"sample:view"},
    )
    policy = SimpleNamespace(
        permission_allowed=lambda user, permission, context=None: permission in user.permissions,
        scope_allowed=lambda user, context=None: True,
    )
    events = []
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=lambda actor: policy,
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: None,
        audit_access=events.append,
    )
    repository = Mock()
    repository.query.return_value = ResourceReadPage()
    return ResourceReads(runtime, lambda: repository), actor, repository, events, runtime


@pytest.mark.parametrize("operation", ["list", "ids", "count", "exists", "distinct"])
def test_permissions_checked_for_every_operation(boundary, operation):
    reads, actor, repository, events, _ = boundary
    actor.permissions.clear()
    options = {"operation": operation}
    if operation == "distinct":
        options["field"] = "asp_id"
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, ResourceReadQuery(**options))
    assert error.value.status_code == 403
    repository.query.assert_not_called()
    assert events[-1].allowed is False


@pytest.mark.parametrize("operation", ["list", "count", "ids", "exists", "distinct"])
def test_related_filters_require_related_view_permission(boundary, operation):
    reads, actor, repository, _, _ = boundary
    options = {"operation": operation, "related_filters": {"configuration": {"is_active": True}}}
    if operation == "distinct":
        options["field"] = "asp_id"
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, ResourceReadQuery.model_validate(options))
    assert error.value.status_code == 403
    repository.query.assert_not_called()
    actor.permissions.add("assay.config:view")
    reads.query(ReadResource.SAMPLES, ResourceReadQuery.model_validate(options))
    assert repository.query.call_count == 1


def test_include_permissions_and_grants_refreshed_between_calls(boundary):
    reads, actor, repository, events, _ = boundary
    query = ResourceReadQuery(include=["assay"])
    with pytest.raises(AppError):
        reads.query(ReadResource.SAMPLES, query)
    actor.permissions.add("assay.panel:view")
    reads.query(ReadResource.SAMPLES, query)
    scope = repository.query.call_args.args[2]
    assert scope.grants == actor.assay_access
    assert scope.groups == ("dna",)
    actor.assay_access = []
    reads.query(ReadResource.SAMPLES, query)
    assert repository.query.call_args.args[2].grants == []
    assert events[-1].permissions == ("sample:view", "assay.panel:view")


def test_invalid_fields_and_credentials_do_not_reach_storage(boundary):
    reads, _, repository, _, runtime = boundary
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, ResourceReadQuery(fields=["credentials"]))
    assert error.value.status_code == 422
    runtime.authenticate = lambda: None
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, ResourceReadQuery())
    assert error.value.status_code == 401
    repository.query.assert_not_called()


def test_fixed_machine_audience_cannot_read_resources(boundary):
    reads, _, repository, _, runtime = boundary
    runtime.allowed_operations = frozenset({"ingest.execute_job"})
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, ResourceReadQuery(operation="count"))
    assert error.value.status_code == 403
    repository.query.assert_not_called()


@pytest.mark.parametrize(
    "resource,permission",
    [
        (ReadResource.ASP, "assay.panel"),
        (ReadResource.ASPC, "assay.config"),
        (ReadResource.ISGL, "gene_list.insilico"),
    ],
)
def test_catalog_queries_preserve_list_and_view_permissions(boundary, resource, permission):
    reads, actor, repository, _, _ = boundary
    actor.permissions = {permission + ":view"}
    with pytest.raises(AppError):
        reads.query(resource, ResourceReadQuery(operation="ids"))
    repository.query.assert_not_called()
    actor.permissions.add(permission + ":list")
    reads.query(resource, ResourceReadQuery(operation="ids"))
    assert repository.query.call_count == 1


@pytest.mark.parametrize(
    "update",
    [
        {"per_page": 1000000},
        {"filters": {"reported": {"$ne": True}}},
        {"filters": {"reported": "false"}},
    ],
)
def test_in_process_model_copy_cannot_bypass_input_validation(boundary, update):
    reads, _, repository, _, _ = boundary
    query = ResourceReadQuery().model_copy(update=update)
    with pytest.raises(AppError) as error:
        reads.query(ReadResource.SAMPLES, query)
    assert error.value.status_code == 422
    repository.query.assert_not_called()
