# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Application-owned governance configuration contracts."""

from __future__ import annotations

from dataclasses import dataclass

from coyote.config.factory_defaults import factory_value


@dataclass(frozen=True)
class PermissionCatalog:
    """Fixed permission categories supplied by the COYOTE4 application."""

    categories: tuple[str, ...]


PERMISSION_CATALOG = PermissionCatalog(
    categories=tuple(factory_value("contracts.permission_categories"))
)
