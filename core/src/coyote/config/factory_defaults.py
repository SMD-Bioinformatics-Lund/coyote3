# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Release-owned defaults for the reusable core library and its contracts.

Host deployment settings belong to coyote_api.config; presentation defaults belong to
frontend. This loader never imports either owner or consults center selection.
"""

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

from coyote.contracts.manifests import MANIFEST_FILE_KEYS

FACTORY_CATALOG_PATH = Path(__file__).with_name("factory_defaults.toml")
_SECTIONS = {
    "accounts",
    "capabilities",
    "clinical_queries",
    "contracts",
    "platforms",
    "notation",
    "knowledgebases",
    "records",
    "assay_defaults",
    "reporting",
    "filters",
    "controls",
    "governance_defaults",
    "starter_defaults",
    "pagination",
}


def load_factory_catalog(path: Path = FACTORY_CATALOG_PATH) -> dict[str, Any]:
    """Read core defaults and reject missing sections or inconsistent bindings.

    Args:
        path: Packaged catalog, or an explicit file for validation.

    Returns:
        Core settings without API runtime or frontend presentation values.

    Raises:
        OSError: The catalog cannot be read.
        ValueError: Required sections, analysis bindings or pagination bounds are invalid.
        tomllib.TOMLDecodeError: The document is malformed.
    """
    with path.open("rb") as handle:
        values = tomllib.load(handle)
    if set(values) != _SECTIONS or any(not isinstance(value, dict) for value in values.values()):
        raise ValueError("Core factory catalog must contain exactly its declared sections")
    if (
        type(values["pagination"]["max_page_size"]) is not int
        or values["pagination"]["max_page_size"] < 1
    ):
        raise ValueError("Core pagination maximum must be a positive integer")
    values["capabilities"]["files"] = {
        category: {"keys": list(keys)} for category, keys in MANIFEST_FILE_KEYS.items()
    }
    for omics in values["capabilities"]["assay"]["categories"]:
        analysis = values["capabilities"]["analysis"][omics]
        stored = set(values["contracts"]["analysis_preload"][omics])
        external = set(values["contracts"]["non_database_analyses"][omics])
        if stored & external or stored | external != set(analysis["types"]):
            raise ValueError(f"Factory analysis preload bindings must cover {omics} exactly once")
    return values


_CATALOG = load_factory_catalog()


def factory_value(path: str) -> Any:
    """Return an isolated core default; missing keys never receive hidden fallbacks.

    Args:
        path: Dotted catalog path, for example filters.snv.min_depth.

    Returns:
        A copy of the scalar, list or mapping so callers cannot mutate the catalog.

    Raises:
        KeyError: A consumer references an undeclared core default.
    """
    value: Any = _CATALOG
    for part in path.split("."):
        value = value[part]
    return deepcopy(value)
