"""Synthetic authenticated application runtime for API boundary tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.operations import ApplicationRuntime, ClinicalServices
from coyote.application.operations.samples import Samples
from coyote.contracts.operations import OperationResult
from coyote_api.security.policy import build_access_policy


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
        assay_access=[{"asp_id": "synthetic", "environments": ["testing"]}],
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
