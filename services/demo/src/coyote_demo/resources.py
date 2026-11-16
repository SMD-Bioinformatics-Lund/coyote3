# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Locate installed synthetic resources without loading the application host."""

from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent / "data"
WORKFLOW_BUNDLE = DATA_ROOT / "clinical_workflows"
DEMO_CENTER = DATA_ROOT / "demo_center"
GROUPS_PATH = DATA_ROOT / "assay_groups.seed.ndjson"
