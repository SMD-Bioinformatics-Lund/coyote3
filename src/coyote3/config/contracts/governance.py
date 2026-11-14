"""Application-owned governance configuration contracts."""

from __future__ import annotations

from dataclasses import dataclass

from coyote3.config.factory_defaults import factory_value


@dataclass(frozen=True)
class PermissionCatalog:
    """Fixed permission categories supplied by the COYOTE3 application."""

    categories: tuple[str, ...]


PERMISSION_CATALOG = PermissionCatalog(
    categories=tuple(factory_value("contracts.permission_categories"))
)
