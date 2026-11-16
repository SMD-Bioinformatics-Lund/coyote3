# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Core-owned permission definitions and built-in role templates.

Reading this catalog performs no installation or persistence. Hosts explicitly
install the definitions; current assignments remain deployment-owned state.
"""

import json
from pathlib import Path
from typing import Any, Literal

RBAC_CATALOG_DIR = Path(__file__).with_name("catalogs") / "rbac"
_CATALOG_FILES = {
    "permissions": "permissions.seed.ndjson",
    "roles": "roles.seed.ndjson",
}


def load_governance_catalog(name: Literal["permissions", "roles"]) -> list[dict[str, Any]]:
    """Read independent copies of the shipped permission or role definitions.

    Args:
        name: ``permissions`` selects capability definitions; ``roles`` selects
            the built-in combinations of those capabilities.

    Returns:
        Catalog objects in their packaged order, without adding deployment timestamps
        or operator identities.
        Callers may modify these copies without changing subsequent reads.

    Raises:
        KeyError: The selected catalog name is not supported.
        OSError: A packaged catalog cannot be read.
        ValueError: A nonblank line is invalid JSON or is not an object.
    """
    path = RBAC_CATALOG_DIR / _CATALOG_FILES[name]
    documents: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        document = json.loads(line)
        if not isinstance(document, dict):
            raise ValueError(f"Expected a catalog object at {path.name}:{number}")
        documents.append(document)
    return documents
