"""Manual biomarker review preserves measured evidence, authorization and audit history."""

import pytest
from coyote.contracts.dna import BiomarkerAssessmentRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "UNKNOWN", "expected_revision": 0},
        {"value": "HIGH", "expected_revision": -1},
        {"value": "HIGH", "expected_revision": 0, "assessed_by": "forged"},
    ],
)
def test_assessment_contract_rejects_invalid_values_and_actor_spoofing(payload):
    with pytest.raises(ValidationError):
        BiomarkerAssessmentRequest.model_validate(payload)
