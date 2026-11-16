"""Finding mutations reject cross-sample identifiers before changing data."""

from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.classification.tiering import ResourceClassificationService
from coyote.application.classification.variant_annotation import ResourceAnnotationService
from coyote.application.common.finding_access import require_sample_finding
from coyote.application.dna.variant_analysis import DnaService
from coyote.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote.application.rna.expression_analysis import RnaService
from coyote.domain.common.errors import AppError


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


def test_malformed_finding_id_is_not_found():
    """A malformed identifier is rejected without exposing database parsing errors."""
    with pytest.raises(AppError) as error:
        require_sample_finding({"_id": "sample"}, "invalid", Mock(side_effect=ValueError()))
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
    service = ResourceAnnotationService(
        annotation_repository=annotations,
        assay_configuration_repository=Mock(),
        assay_panel_repository=Mock(),
        **repositories,
    )
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
        assay_diagnosis_repository=object(),
        user_repository=object(),
        roles_repository=roles,
    )
    notifications = SimpleNamespace()
    service = ClinicalRuleAuthoringService.from_store(store, notification_service=notifications)
    assert service.assignments.role_repository is roles
    assert service.assignments.notification_service is notifications
