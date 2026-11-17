# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Immutable operational and integration contracts owned by Coyote4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from coyote.config.factory_defaults import factory_value


@dataclass(frozen=True)
class NotificationContract:
    """Stable notification values shared by API validation and the UI."""

    tones: frozenset[str]
    categories: frozenset[str]


APP_CONTROLS_ID: Final = factory_value("contracts.app_controls_id")
NOTIFICATIONS: Final = NotificationContract(
    tones=frozenset(factory_value("contracts.notifications.tones")),
    categories=frozenset(factory_value("contracts.notifications.categories")),
)
