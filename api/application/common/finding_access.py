"""Ownership checks shared by finding mutation workflows."""

from collections.abc import Callable
from typing import Any

from bson.errors import InvalidId

from api.domain.common.errors import api_error


def require_sample_finding(
    sample: dict[str, Any],
    resource_id: str,
    loader: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    """Resolve a finding only when it belongs to the authorized sample.

    Args:
        sample: Authorized sample with its canonical database identifier.
        resource_id: Finding identifier submitted by the caller.
        loader: Repository lookup for the finding type.

    Returns:
        The finding owned by the sample.

    Raises:
        AppError: If the finding is absent or belongs to another sample.
    """
    try:
        finding = loader(resource_id)
    except InvalidId as exc:
        raise api_error(404, "Finding not found for sample") from exc
    sample_id = sample.get("_id")
    if not sample_id or not finding or str(finding.get("SAMPLE_ID", "")) != str(sample_id):
        raise api_error(404, "Finding not found for sample")
    return finding
