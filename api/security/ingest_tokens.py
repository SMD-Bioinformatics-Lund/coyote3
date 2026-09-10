"""Issue expiring, environment-bound credentials for synchronous sample ingestion."""

import secrets
import time

from itsdangerous import BadData, URLSafeSerializer


def environment_name(value: str) -> str:
    """Normalize long and short deployment names for token audience checks."""
    value = value.strip().lower()
    return {"development": "dev", "production": "prod", "testing": "test", "staging": "stage"}.get(
        value, value
    )


def issue_token(secret: str, environment: str, hours: int = 24, *, issued_by: str = "") -> str:
    """Sign an ingest-only credential valid for 1 to 720 hours.

    Args:
        secret: Deployment internal signing secret; never distribute this to clients.
        environment: Deployment environment that may accept this credential.
        hours: Lifetime in hours, defaulting to one day and limited to thirty days.
        issued_by: Authenticated issuer identifier recorded in the signed claims.

    Returns:
        Signed token for the X-Coyote-Ingest-Token header.

    Raises:
        ValueError: Signing configuration or lifetime is invalid.
    """
    if not secret or not environment or not 1 <= hours <= 720:
        raise ValueError("A signing secret, environment, and lifetime of 1–720 hours are required")
    return URLSafeSerializer(secret, salt="coyote3-sample-ingest-v1").dumps(
        {
            "scope": "sample-ingest",
            "environment": environment_name(environment),
            "expires": int(time.time()) + hours * 3600,
            "id": secrets.token_hex(12),
            "issued_by": issued_by,
        }
    )


def verify_token(token: str, secret: str, environment: str) -> dict:
    """Validate signature, expiry, purpose, and deployment audience.

    Returns:
        Verified claims used for the machine audit identity.

    Raises:
        ValueError: The token is invalid, expired, or issued for another environment.
    """
    try:
        if not secret:
            raise ValueError("Signing is not configured")
        claims = URLSafeSerializer(secret, salt="coyote3-sample-ingest-v1").loads(token)
        if (
            not isinstance(claims, dict)
            or claims.get("scope") != "sample-ingest"
            or claims.get("environment") != environment_name(environment)
            or not isinstance(claims.get("expires"), int)
            or claims["expires"] <= time.time()
            or not claims.get("id")
        ):
            raise ValueError("Invalid claims")
        return claims
    except (BadData, ValueError, TypeError) as exc:
        raise ValueError("Invalid or expired ingestion token") from exc
