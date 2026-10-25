"""Report path/id generation helpers."""

from uuid import uuid4

from coyote3.domain.common.reporting import utc_now


def get_report_timestamp() -> str:
    """Return UTC timestamp suffix used in report ids."""
    return f"{utc_now():%y%m%d%H%M%S}-{uuid4().hex}"
