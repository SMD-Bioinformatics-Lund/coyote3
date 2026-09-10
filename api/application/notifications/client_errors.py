"""Record authenticated browser errors in operational logs."""

import logging


def record_client_error(*, message: str, stack: str, username: str) -> None:
    """Write bounded browser diagnostics with the authenticated reporting username."""
    logging.getLogger("coyote.ui").error(
        "Browser error: %s", message, extra={"exception": stack, "actor": username}
    )
