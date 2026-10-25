"""Synthetic SDK composition for clinical transport/implementation regression tests."""

from inspect import signature
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.params import Param

from api.infra.registered_artifacts import FilesystemRegisteredArtifacts
from coyote3.application.interpretation import report_summary
from coyote3.application.operations import ApplicationRuntime, ClinicalServices
from coyote3.application.operations.clinical import Findings, SmallVariants
from coyote3.application.operations.coverage import Coverage
from coyote3.application.operations.samples import Sample, Samples
from tests.fixtures.api import mock_collections as records


def load_sample(sample_id, user):
    """Return the synthetic default sample; tests replace this port for specific scope scenarios."""
    return records.sample_doc()


def configuration(sample):
    """Return the synthetic applied release; tests replace this resolver for error scenarios."""
    return records.assay_config_doc()


def invoke_route(handler, *args, **kwargs):
    """Supply the plain query defaults that FastAPI passes to a transport handler over HTTP."""
    parameters = signature(handler)
    bound = parameters.bind_partial(*args, **kwargs)
    for name, parameter in parameters.parameters.items():
        if name not in bound.arguments and isinstance(parameter.default, Param):
            default = parameter.default
            bound.arguments[name] = (
                default.default_factory()
                if default.default_factory is not None
                else default.default
            )
    return handler(*bound.args, **bound.kwargs)


def finding_operations(service, kind, user, sample_id="synthetic-reference"):
    """Bind a clinical implementation to the same SDK entry points used by HTTP dependencies."""
    policy = SimpleNamespace(
        permission_allowed=lambda *args, **kwargs: True,
        scope_allowed=lambda *args, **kwargs: True,
    )
    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: policy,
        sample_loader=lambda identity: load_sample(identity, user),
        assay_loader=lambda identity: {"asp_group": "synthetic"},
        audit_access=Mock(),
    )

    def require_owned(*, sample, resource_type, resource_id):
        """Use the implementation's existing ownership check, with no unconditional bypass."""
        if resource_type == "small_variant":
            return service.require_variant_for_sample(sample=sample, var_id=resource_id)
        return service.require_resource_for_sample(
            sample=sample, resource=resource_type, resource_id=resource_id
        )

    services = ClinicalServices(
        dna=lambda: service,
        structural=lambda: service,
        rna=lambda: service,
        classification=lambda: SimpleNamespace(require_resource_for_sample=require_owned),
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
    resource = SmallVariants if kind == "small_variant" else Findings
    return resource(runtime, services, sample_id, kind)


def sample_operations(service, user, sample_id="synthetic-reference"):
    """Bind classification and annotation implementations to the canonical sample operations."""
    finding = finding_operations(service, "small_variant", user, sample_id)
    services = ClinicalServices(
        dna=lambda: SimpleNamespace(configuration_resolver=configuration),
        structural=lambda: service,
        rna=lambda: service,
        classification=lambda: service,
        classification_document=report_summary.create_classified_variant_doc,
        annotations=lambda: service,
        public_annotations=Mock(),
        catalog=lambda: service,
        fields=lambda: service,
        common_queries=lambda: service,
        coverage=lambda: service,
        biomarkers=lambda: service,
        artifacts=FilesystemRegisteredArtifacts,
    )
    return Sample(finding._runtime, services, sample_id)


def sample_catalog_operations(service, user):
    """Bind a synthetic catalog to the same global SDK search/navigation operations."""
    sample = sample_operations(service, user)
    return Samples(sample._runtime, sample._services)


def authorized_operations(resource, service, user=None):
    """Exercise real SDK operations over a supplied synthetic implementation.

    Transport tests use a permissive synthetic policy; dedicated SDK access tests
    exercise real grants, scope changes and session revocation independently.
    """
    from api.app.application_factory import enqueue_operation
    from api.services.installation import Installation
    from coyote3.application.operations.account import Account
    from coyote3.application.operations.knowledgebase import Knowledgebase
    from coyote3.application.operations.system import (
        Controls,
        Credentials,
        Dashboard,
        Traceability,
    )

    user = user or records.api_user()
    runtime = finding_operations(service, "small_variant", user)._runtime
    if resource is Account:
        from api.app.application_factory import change_account_password

        return resource(runtime, lambda: service, change_account_password)
    if resource is Knowledgebase:
        return resource(runtime, lambda: service, search_limit=1000)
    if resource in {Controls, Credentials, Dashboard, Installation, Traceability}:
        ports = SimpleNamespace(
            dashboard=lambda: service,
            controls=lambda: service,
            demo=lambda: service,
            deployment=lambda: service,
            audit=lambda: service,
            enqueue=enqueue_operation,
            issue_token=Mock(),
            schemas={},
        )
        return resource(runtime, ports)
    return resource(runtime, lambda: service)


def public_operations():
    """Build the real anonymous SDK with synthetic host services from the test harness."""
    from api.app.application_factory import open_public_application

    return open_public_application()


def public_pages():
    """Build host-owned public product pages with synthetic application configuration."""
    from api.app.deps.application import get_public_pages

    return get_public_pages()


def ingestion_operations(service, user):
    """Bind real ingestion operations to synthetic implementations and durable job ports."""
    from api.app.application_factory import ingest_submission_services
    from coyote3.application.operations.ingest import Ingestion

    runtime = finding_operations(service, "small_variant", user)._runtime
    runtime.policy_factory = lambda actor: SimpleNamespace(
        permission_allowed=lambda actor, permission_id, **kwargs: (
            permission_id != "sample:edit:own" or permission_id in actor.permissions
        ),
        scope_allowed=lambda actor, context: (
            context.get("asp_id") in actor.asp_ids and context.get("environment") in actor.envs
        ),
    )
    return Ingestion(runtime, lambda: service, ingest_submission_services())


def internal_reference_operations(*, roles=None, gene_lists=None, request):
    """Exercise SDK reference reads while retaining the static-token adapter check."""
    from api.security.access import _require_internal_token
    from coyote3.application.operations.internal_references import (
        InternalReferences,
        InternalReferenceServices,
    )

    user = records.api_user()
    runtime = finding_operations(None, "small_variant", user)._runtime
    runtime.authenticate = lambda: _require_internal_token(request) or user
    ports = InternalReferenceServices(
        role_levels=lambda: {
            role["role_id"]: role.get("level", 0)
            for role in roles.get_all_roles()
            if role.get("role_id")
        },
        gene_list_metadata=lambda identifier: {
            "is_adhoc": bool(gene_lists.is_isgl_adhoc(identifier)),
            "display_name": gene_lists.get_isgl_display_name(identifier),
        },
    )
    return InternalReferences(runtime, ports)


def coverage_operations(service, user):
    """Bind synthetic coverage dependencies to the SDK's group-owned curation operations."""
    sample = sample_operations(service, user)
    return Coverage(sample._runtime, sample._services)


def public_gene_operations(service):
    """Bind public gene reference reads without introducing clinical authentication."""
    from coyote3.application.operations.public import PublicApplication

    return PublicApplication(
        catalog=Mock(),
        controls=Mock(),
        config={},
        logger=Mock(),
        filter_flags=Mock(),
        gene_info=service.gene_info_payload,
    )
