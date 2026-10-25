"""Issue pipeline credentials only after recording the authenticated issuer."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from coyote3.application.audit.service import AuditService


def issue_audited_ingest_token(
    *,
    secret: str,
    environment: str,
    hours: int,
    actor: Any,
    audit: AuditService,
    token_issuer: Callable[..., str],
    token_verifier: Callable[..., dict[str, Any]],
) -> dict:
    """Return an expiring credential after its issuance audit has been persisted.

    Args:
        secret: Deployment signing key, never included in the response or audit.
        environment: Server-selected deployment audience.
        hours: Requested lifetime within the supported limit.
        actor: Authenticated user authorized by the HTTP access dependency.
        audit: Durable audit writer.
        token_issuer: Configured credential-signing adapter.
        token_verifier: Configured claims-verification adapter.

    Returns:
        Credential and expiry metadata for a single issuance response.

    Raises:
        RuntimeError: Issuance could not be recorded; no token may be returned.
    """
    token = token_issuer(secret, environment, hours, issued_by=str(actor.id))
    claims = token_verifier(token, secret, environment)
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
