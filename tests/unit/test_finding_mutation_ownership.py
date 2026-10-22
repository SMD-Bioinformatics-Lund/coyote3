"""Finding mutations reject cross-sample identifiers before changing data."""

from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from api.application.classification.tiering import ResourceClassificationService
from api.application.classification.variant_annotation import ResourceAnnotationService
from api.application.common.finding_access import require_sample_finding
from api.application.dna.variant_analysis import DnaService
from api.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from api.application.rna.expression_analysis import RnaService
from api.domain.common.errors import AppError
from api.infra.mongo.repositories.base import BaseRepository
from api.interfaces.http.clinical.common.change_helpers import resource_change
from api.interfaces.http.clinical.dna import small_variants as annotation_routes
from api.security import access
from tests.fixtures.api.permission_catalog import PermissionCatalog


@pytest.mark.parametrize("scope", ["local", "global"])
@pytest.mark.parametrize("global_allowed", [False, True])
def test_annotation_route_requires_the_extra_global_permission(monkeypatch, scope, global_allowed):
    """An own-comment grant alone cannot authorize a shared annotation write."""
    permissions = ["variant.comment:add:own"]
    if global_allowed:
        permissions.append("variant.comment:add:global")
    roles = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "commenter", "permissions": permissions}]
    )
    monkeypatch.setattr(access, "get_roles_repository", lambda: roles)
    monkeypatch.setattr(access, "get_permissions_repository", PermissionCatalog)
    principal = SimpleNamespace(
        username="reviewer",
        roles=["commenter"],
        is_superuser=False,
        asp_ids=["*"],
        asp_groups=["*"],
        envs=["testing"],
    )
    sample = {"_id": "sample"}
    monkeypatch.setattr(annotation_routes, "_get_sample_for_api", lambda *_args: sample)
    service = Mock()
    service.create_annotation.return_value = "variant_comment"
    arguments = {
        "payload": {"id": "finding", "form_data": {"global": scope, "text": "note"}},
        "user": principal,
        "service": service,
    }
    if scope == "global" and not global_allowed:
        with pytest.raises(HTTPException) as failure:
            annotation_routes.add_variant_comment_change("sample", **arguments)
        assert failure.value.status_code == 403
        service.create_annotation.assert_not_called()
    else:
        annotation_routes.add_variant_comment_change("sample", **arguments)
        assert service.create_annotation.call_args.kwargs["sample"] == sample


@pytest.mark.parametrize("finding", [None, {}, {"SAMPLE_ID": "other"}])
def test_finding_owner_is_required(finding):
    """Missing ownership and another sample's identity both produce not-found."""
    with pytest.raises(AppError):
        require_sample_finding({"_id": "sample"}, "finding", lambda _: finding)


@pytest.mark.parametrize("kind", ["variant", "fusion"])
def test_bulk_rejects_foreign_last_item_before_any_write(kind):
    """A mixed selection cannot partially update the authorized first finding."""
    sample = {"_id": "sample"}
    loader = Mock(side_effect=[{"SAMPLE_ID": "sample"}, {"SAMPLE_ID": "other"}])
    write = Mock()
    if kind == "variant":
        service = object.__new__(DnaService)
        service.variant_repository = SimpleNamespace(
            get_variant=loader, set_sample_finding_flag=write
        )
        mutate = partial(
            service.set_variant_bulk_flag,
            sample=sample,
            resource_ids=["own", "foreign"],
            apply=True,
            flag="false_positive",
        )
    else:
        service = object.__new__(RnaService)
        service.fusion_repository = SimpleNamespace(
            get_fusion=loader, set_sample_finding_flag=write
        )
        mutate = partial(
            service.set_fusion_bulk_flag,
            sample=sample,
            fusion_ids=["own", "foreign"],
            apply=True,
            flag="false_positive",
        )
    with pytest.raises(AppError):
        mutate()
    write.assert_not_called()


def test_custom_validator_cannot_skip_sample_authorization(monkeypatch):
    """Custom finding validation never replaces the sample scope check."""
    access = Mock(side_effect=PermissionError("denied"))
    monkeypatch.setattr("api.security.access._get_sample_for_api", access)
    mutate = Mock()
    validate = Mock()
    with pytest.raises(PermissionError):
        resource_change(
            "sample",
            "finding",
            SimpleNamespace(),
            SimpleNamespace(),
            resource="cnv",
            action="mark",
            mutate=mutate,
            validate=validate,
        )
    validate.assert_not_called()
    mutate.assert_not_called()


def test_scoped_flag_write_cannot_match_another_sample():
    """The database predicate keeps sample ownership even after service validation."""
    repository = object.__new__(BaseRepository)
    repository.update_many_atomic = Mock(
        return_value=SimpleNamespace(matched_count=1, modified_count=1, acknowledged=True)
    )
    repository._invalidate_dashboard_on_change = lambda result: result
    finding_id = str(ObjectId())
    repository.set_sample_finding_flag(
        sample_id="authorized-sample", resource_ids=[finding_id], flag="fp", value=True
    )
    repository.update_many_atomic.assert_called_once_with(
        {"_id": {"$in": [ObjectId(finding_id)]}, "SAMPLE_ID": "authorized-sample"},
        {"$set": {"fp": True}},
    )


def test_malformed_bulk_identifier_prevents_every_write():
    """Invalid selections must never silently update just the valid subset."""
    repository = object.__new__(BaseRepository)
    repository.update_many_atomic = Mock()
    with pytest.raises(InvalidId):
        repository.set_sample_finding_flag(
            sample_id="sample", resource_ids=[str(ObjectId()), "invalid"], flag="fp", value=True
        )
    repository.update_many_atomic.assert_not_called()


def test_malformed_finding_id_is_not_found():
    """A malformed identifier is rejected without exposing database parsing errors."""
    with pytest.raises(AppError) as error:
        require_sample_finding({"_id": "sample"}, "invalid", Mock(side_effect=InvalidId()))
    assert error.value.status_code == 404


def _foreign_repositories():
    """Return finding repositories whose every lookup belongs to another sample."""
    foreign = Mock(return_value={"_id": "finding", "SAMPLE_ID": "other"})
    return {
        "variant_repository": SimpleNamespace(get_variant=foreign, add_var_comment=Mock()),
        "fusion_repository": SimpleNamespace(get_fusion=foreign, add_fusion_comment=Mock()),
        "copy_number_variant_repository": SimpleNamespace(get_cnv=foreign, add_cnv_comment=Mock()),
        "translocation_repository": SimpleNamespace(
            get_transloc=foreign, add_transloc_comment=Mock()
        ),
    }


@pytest.mark.parametrize("resource_type", ["small_variant", "fusion", "cnv", "translocation"])
def test_classification_rejects_foreign_finding(resource_type):
    """Single classify/remove requests cannot target another sample's finding."""
    service = object.__new__(ResourceClassificationService)
    for name, repository in _foreign_repositories().items():
        setattr(service, name, repository)
    with pytest.raises(AppError) as error:
        service.require_resource_for_sample(
            sample={"_id": "sample"}, resource_type=resource_type, resource_id="finding"
        )
    assert error.value.status_code == 404


@pytest.mark.parametrize("nomenclature", ["p", "f", "t", "cn"])
@pytest.mark.parametrize("scope", ["local", "global"])
def test_annotation_rejects_foreign_finding_before_any_write(nomenclature, scope):
    """Local and global comments require the target finding to belong to the sample."""
    repositories = _foreign_repositories()
    annotations = SimpleNamespace(add_anno_comment=Mock())
    service = ResourceAnnotationService(annotation_repository=annotations, **repositories)
    with pytest.raises(AppError):
        service.create_annotation(
            form_data={"text": "note", "global": scope},
            target_id="finding",
            get_variant_nomenclature_fn=lambda _form: (nomenclature, "variant"),
            create_comment_doc_fn=lambda *_args, **_kwargs: {"text": "note"},
            sample={"_id": "sample"},
        )
    annotations.add_anno_comment.assert_not_called()
    for repository in repositories.values():
        for name, method in vars(repository).items():
            if name.startswith("add_"):
                method.assert_not_called()


def test_rule_authoring_binds_runtime_roles_repository():
    """Reviewer eligibility uses the store's canonical roles repository."""
    roles = object()
    store = SimpleNamespace(
        clinical_rule_set_repository=object(),
        clinical_rule_revision_repository=object(),
        assay_panel_repository=object(),
        assay_subpanel_repository=object(),
        user_repository=object(),
        roles_repository=roles,
    )
    assert ClinicalRuleAuthoringService.from_store(store).role_repository is roles
