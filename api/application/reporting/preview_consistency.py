"""Compare reviewed report inputs with the exact inputs used for persistence."""

import hashlib
import json
from hmac import compare_digest

from api.domain.common.errors import api_error


def preview_fingerprint(template: str, context: dict) -> str:
    """Hash report content, excluding presentation-only generation metadata.

    Args:
        template: Renderer template identity.
        context: Complete prepared report inputs, including findings and rule provenance.

    Returns:
        SHA-256 digest suitable for the subsequent save precondition.

    Notes:
        Preview/save flags and generation timestamps differ by request. All clinical
        context, including sample state, comments and the resolved rule hash, is retained.
        This is a concurrency precondition, not an authorization credential.
    """
    content = {
        key: value
        for key, value in context.items()
        if key not in {"save", "report_date", "report_timestamp"}
    }
    encoded = json.dumps(
        {"template": template, "context": content},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_current_preview(expected: str, template: str, context: dict) -> None:
    """Reject stale report inputs before artifact creation or persistence.

    Args:
        expected: Fingerprint returned by the reviewed preview.
        template: Current template identity.
        context: Prepared inputs that will be rendered and saved without re-resolution.

    Raises:
        AppError: HTTP 409 when clinical inputs or rules changed after preview.
    """
    if not compare_digest(expected, preview_fingerprint(template, context)):
        raise api_error(409, "Report inputs changed. Refresh and review the preview before saving.")
