"""Paired scopes never grant an environment belonging to another assay."""

import pytest
from coyote.contracts.schemas.assay_access import AssayAccessGrant
from coyote.domain.identity.assay_access import grants_for
from pydantic import ValidationError


@pytest.mark.parametrize(
    "changes",
    [
        {"roles": "not-superuser", "assay_access": []},
        {"roles": ["user"], "assay_access": [{"asp_id": "assay_a", "environments": "production"}]},
        {"roles": ["user"], "assay_access": "invalid"},
    ],
)
def test_malformed_persisted_grants_fail_closed(changes):
    assert grants_for(changes) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"asp_id": "*", "environments": ["production"]},
        {"asp_id": "assay_a", "environments": ["unknown"]},
        {"asp_id": "assay_a", "environments": ["production", "production"]},
    ],
)
def test_invalid_scope_assignments_are_rejected(payload):
    with pytest.raises(ValidationError):
        AssayAccessGrant.model_validate(payload)
