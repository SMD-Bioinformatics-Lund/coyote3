# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Coyote-owned VEP reference labels and grouping policy, independent of installation."""

import json
from pathlib import Path
from typing import Any

VEP_METADATA_POLICY_PATH = Path(__file__).with_name("vep_metadata_policy.json")


def load_vep_metadata_policy() -> dict[str, Any]:
    """Read a fresh copy of the reviewed consequence and variant-class policy.

    Returns:
        Group membership and display labels used when validating imported VEP releases.
        This policy contains no downloaded release definitions or database settings.

    Raises:
        OSError: The packaged policy cannot be read.
        ValueError: The policy is not valid JSON or lacks a required mapping.
    """
    policy = json.loads(VEP_METADATA_POLICY_PATH.read_text(encoding="utf-8"))
    required = {"consequence_groups", "consequence_labels", "variant_labels"}
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError("VEP reference policy must contain its three declared mappings")
    if any(not isinstance(policy[key], dict) for key in required):
        raise ValueError("VEP reference policy sections must be mappings")
    return policy
