"""Operational assay availability without changing historical record visibility."""

from typing import Any

from api.domain.common.errors import api_error


def require_active_group(panels: Any, group_id: str) -> None:
    """Reject new operational use of an inactive or unregistered group.

    Args:
        panels: Panel repository exposing current active registry keys.
        group_id: Group assigned to the target assay or configuration.

    Raises:
        AppError: The group is unavailable. Existing clinical records remain readable.
    """
    if group_id not in panels.group_options():
        raise api_error(409, "Assay group is inactive or unregistered; new use is unavailable")


def available_panels(panels: Any) -> list[dict]:
    """Return active assays whose parent group is also active, for new selections."""
    groups = set(panels.group_options())
    return [
        panel
        for panel in panels.get_all_asps(is_active=True) or []
        if panel.get("asp_group") in groups
    ]
