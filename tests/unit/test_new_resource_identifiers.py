"""Creation policy for clinical identities without renaming existing references."""

from unittest.mock import Mock

import pytest

from api.application.resources.asp import AspService
from api.application.resources.assay_groups import AssayGroupService
from api.application.resources.helpers import require_new_identifier
from api.application.resources.isgl import IsglService
from api.application.resources.subpanels import SubpanelService
from api.config.constants import normalize_clinical_identifier
from api.contracts.schemas.assay_groups import AssayGroupCreate
from api.contracts.schemas.subpanels import SharedSubpanelCreate
from api.domain.core.exceptions import AppError


@pytest.mark.parametrize("value", ["solid_gmsv3", "breast_cancer", "mpn", "panel_2"])
def test_new_identifier_is_not_rewritten(value):
    assert require_new_identifier(value, label="asp_id") == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        None,
        "breast-cancer",
        "BREAST",
        "breast cancer",
        "_breast",
        "breast_",
        "breast__cancer",
        "breast.cancer",
        "bröst",
        " breast",
        "breast\n",
    ],
)
def test_new_identifier_rejects_noncanonical_spelling(value):
    with pytest.raises(AppError) as caught:
        require_new_identifier(value, label="asp_id")
    assert caught.value.status_code == 422
    assert "asp_id" in str(caught.value)


def test_existing_reference_separator_is_preserved():
    assert normalize_clinical_identifier("breast-cancer") == "breast-cancer"
    assert normalize_clinical_identifier("breast_cancer") == "breast_cancer"


def test_assay_creation_rejects_hyphen_before_repository_write():
    repository = Mock()
    service = AspService(assay_panel_repository=repository)
    with pytest.raises(AppError, match="Invalid asp_id"):
        service.create(payload={"config": {"asp_id": "new-assay"}})
    repository.create_panel.assert_not_called()


def test_group_creation_rejects_hyphen_before_repository_write():
    repository = Mock()
    service = AssayGroupService(repository)
    with pytest.raises(AppError, match="Invalid group_id"):
        service.create(AssayGroupCreate(group_id="new-group", display_name="New"), actor="author")
    repository.create.assert_not_called()


def test_shared_subpanel_creation_rejects_hyphen_before_repository_write():
    repository = Mock()
    service = SubpanelService(panels=Mock(), subpanels=repository)
    with pytest.raises(AppError, match="Invalid subpanel_id"):
        service.create_definition(
            SharedSubpanelCreate(subpanel_id="new-scope", display_name="New"), actor="author"
        )
    repository.create_definition.assert_not_called()


def test_genelist_creation_rejects_hyphen_before_repository_write():
    service = object.__new__(IsglService)
    service.gene_list_repository = Mock()
    with pytest.raises(AppError, match="Invalid isgl_id"):
        service.create(payload={"config": {"isgl_id": "new-list"}})
    service.gene_list_repository.create_genelist.assert_not_called()
