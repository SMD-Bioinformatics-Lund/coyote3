"""Display names for compact resource selectors and full resource cards."""

from collections.abc import Mapping


def short_resource_name(resource: Mapping[str, object], identifier: str) -> str:
    """Choose a compact name without changing the resource's stable identifier.

    Args:
        resource: Resource metadata with optional name and display-name fields.
        identifier: Stable identifier used if all readable names are absent or blank.

    Returns:
        Trimmed short name, then full display name, then the identifier.
    """
    for key in ("name", "display_name", "displayname"):
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return identifier


def full_resource_name(resource: Mapping[str, object], identifier: str) -> str:
    """Choose the full name used on resource cards and detail headings.

    Args:
        resource: Resource metadata with optional display-name and name fields.
        identifier: Stable identifier used if no readable name is present.

    Returns:
        Trimmed full display name, then the short name, then the identifier.
    """
    for key in ("display_name", "displayname", "name"):
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return identifier
