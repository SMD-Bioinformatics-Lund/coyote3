"""Assay ownership, retirement, concurrency and migration regression coverage."""

import pytest
from coyote.contracts.schemas.assay import InsilicoGenelistsDoc
from coyote.contracts.schemas.diagnoses import DiagnosisCreate
from pydantic import ValidationError


@pytest.mark.parametrize(
    "values",
    [
        {"diagnosis_id": "bad/id", "display_name": "Test"},
        {"diagnosis_id": "test", "display_name": "   "},
        {"diagnosis_id": "test", "display_name": "Test", "asp_id": "other"},
    ],
)
def test_invalid_metadata_is_rejected(values):
    with pytest.raises(ValidationError):
        DiagnosisCreate(**values)


def test_isgl_aliases_are_labels_not_scope_identifiers():
    doc = InsilicoGenelistsDoc(
        isgl_id="breast-panel",
        name="Breast panel",
        displayname="Breast cancer",
        aliases=[" BC ", "Breast Cancer Panel", "bc", ""],
        diagnosis=["breast"],
        list_type=["snv"],
    )
    assert doc.aliases == ["BC", "Breast Cancer Panel"]
    assert doc.diagnosis == ["breast"]
    with pytest.raises(ValidationError):
        InsilicoGenelistsDoc(
            isgl_id="test",
            name="Test",
            displayname="Test",
            aliases=[123],
        )


def test_shared_definition_can_precede_its_assays():
    from unittest.mock import Mock

    from coyote.application.resources.diagnoses import DiagnosisService
    from coyote.contracts.schemas.diagnoses import SharedDiagnosisCreate

    panels, diagnoses = Mock(), Mock()
    panels.get_asp.return_value = None
    result = DiagnosisService(panels=panels, diagnoses=diagnoses).create_definition(
        SharedDiagnosisCreate(diagnosis_id="named", display_name="Named", asp_ids=["future"]),
        actor="installer",
    )
    assert diagnoses.create_definition.call_args.args[1] == ["future"]
    assert result["meta"]["unresolved_asp_ids"] == ["future"]
