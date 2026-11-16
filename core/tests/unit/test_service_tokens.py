"""Managed credentials fail closed across lifecycle, scope and authentication boundaries."""

from datetime import datetime, timezone

import pytest
from coyote.contracts.service_tokens import ServiceTokenCreate
from pydantic import ValidationError


def payload(**changes):
    """Select one real test-registry assay and one clinical environment."""
    return ServiceTokenCreate.model_validate(
        {
            "name": "Synthetic pipeline",
            "owner": "owner",
            "asp_ids": ["assay_a"],
            "environments": ["testing"],
            "operations": ["sample_bundle"],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"asp_ids": []},
        {"asp_ids": ["*"]},
        {"environments": ["*"]},
        {"operations": ["admin"]},
        {"expires_hours": 0},
        {"expires_hours": 8761},
        {"expires_hours": True},
        {"name": " "},
        {"token_hash": "forged"},
    ],
)
def test_invalid_request_contract_rejects_overbroad_credentials(changes):
    with pytest.raises(ValidationError):
        payload(**changes)


@pytest.mark.parametrize(
    "missing", ["credential_id", "credential_owner", "credential_scope", "credential_operation"]
)
def test_durable_jobs_reject_partial_credential_references(missing):
    from coyote.contracts.schemas.ingest_jobs import IngestJobDoc

    now = datetime.now(timezone.utc)
    job = {
        "kind": "sample_bundle",
        "submitted_by": "owner",
        "created_at": now,
        "updated_at": now,
        "credential_id": "synthetic",
        "credential_owner": "owner",
        "credential_scope": {"asp_id": "assay_a", "environment": "testing"},
        "credential_operation": "sample_upload_async",
    }
    job.pop(missing)
    with pytest.raises(ValidationError, match="complete credential"):
        IngestJobDoc.model_validate(job)
