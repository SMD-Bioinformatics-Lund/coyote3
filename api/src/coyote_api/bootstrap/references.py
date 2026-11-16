# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Discover the reviewed reference bundle supplied by an installed data package."""

from importlib.metadata import entry_points
from typing import Any


def reference_bundle() -> Any:
    """Load the installed Atlas bundle without a required server dependency.

    Returns:
        A bundle providing checked documents, diagram assets and an installation plan.

    Raises:
        RuntimeError: Atlas is absent, ambiguously registered or cannot validate its bundle.

    Notes:
        Only explicit reference installation reads this package; ordinary API
        startup and reads of already installed reference data do not require it.
    """
    entries = [
        entry for entry in entry_points(group="coyote.reference_bundles") if entry.name == "atlas"
    ]
    if len(entries) != 1:
        raise RuntimeError(
            "Reference installation requires exactly one installed Coyote Atlas bundle"
        )
    return entries[0].load()()
