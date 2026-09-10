"""Issue pipeline credentials only after recording the authenticated issuer."""

from datetime import datetime, timezone
from typing import Any

from api.application.audit.service import AuditService
from api.security.ingest_tokens import issue_token, verify_token


def issue_audited_ingest_token(
    *, secret: str, environment: str, hours: int, actor: Any, audit: AuditService
) -> dict:
    """Return an expiring credential after its issuance audit has been persisted.

    Args:
        secret: Deployment signing key, never included in the response or audit.
        environment: Server-selected deployment audience.
        hours: Requested lifetime within the supported limit.
        actor: Authenticated user authorized by the HTTP access dependency.
        audit: Durable audit writer.

    Returns:
        Credential and expiry metadata for a single issuance response.

    Raises:
        RuntimeError: Issuance could not be recorded; no token may be returned.
    """
    token = issue_token(secret, environment, hours, issued_by=str(actor.id))
    claims = verify_token(token, secret, environment)
    expires = datetime.fromtimestamp(claims["expires"], timezone.utc)
    event = audit.record(
        "ingest.token.issued",
        "Issued an expiring sample ingestion credential",
        category="security",
        actor=actor,
        resource_type="ingest_credential",
        resource_id=claims["id"],
        retention_class="traceability",
        metadata={
            "credential_id": claims["id"],
            "environment": claims["environment"],
            "expires_at": expires.isoformat(),
            "scope": claims["scope"],
        },
        tags=["ingest", "security"],
    )
    if not event:
        raise RuntimeError("Token issuance audit could not be persisted")
    return {
        "token": token,
        "token_id": claims["id"],
        "expires_at": expires,
        "environment": claims["environment"],
        "scope": claims["scope"],
        "header": "X-Coyote-Ingest-Token",
    }
