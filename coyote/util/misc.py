# -*- coding: utf-8 -*-
"""
Coyote3 Miscellaneous Utilities
=====================================

This module provides miscellaneous classes and utilities for the Coyote3
application, such as the `EnhancedJSONEncoder` for custom JSON encoding
and other helper functions.

It serves as a central point for managing these utility classes and
functions used across the application.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import json
from datetime import datetime
from typing import Any
from collections import defaultdict
from coyote.extensions import store
from flask_login import login_required, current_user


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class EnhancedJSONEncoder(json.JSONEncoder):
    """
    EnhancedJSONEncoder is a custom JSON encoder that extends the default
    `json.JSONEncoder` to handle additional data types.

    This class provides support for encoding `datetime` objects into ISO 8601
    formatted strings, making it easier to serialize objects containing
    date and time information.
    """

    def default(self, obj) -> Any:
        """
        Serialize unsupported objects.

        This method overrides the `default` method of `json.JSONEncoder` to
        provide custom serialization for unsupported objects. Specifically,
        it converts `datetime` objects into ISO 8601 formatted strings.

        Args:
            obj (Any): The object to serialize.

        Returns:
            Any: The serialized representation of the object.

        Raises:
            TypeError: If the object type is not supported.
        """
        if isinstance(obj, datetime):
            return (
                obj.isoformat()
            )  # or use obj.strftime(...) for a custom format
        return super().default(obj)


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------
def get_dynamic_assay_nav() -> dict:

    user_groups = current_user.groups or []
    assays_panels = store.panel_handler.get_all_assay_panels()

    nav = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    URLS: dict[str, dict[str, str]] = {
        "DNA": {
            "WGS": "home_bp.wgs_screen",
            "Panels": "home_bp.panels_screen",
        },
        "RNA": {
            "WTS": "home_bp.rna_wts_screen",
            "Panels": "home_bp.rna_panels_screen",
        },
    }

    for assay_panel in assays_panels:
        panel_type = assay_panel.get("asp_category", "NA").upper()  # DNA / RNA
        tech = assay_panel.get(
            "asp_family", "Unknown"
        )  # WGS / WTS / Panel-based NGS

        if tech.startswith("Panel"):
            tech = "Panels"

        group = assay_panel.get(
            "asp_group", "Uncategorized"
        )  # Myeloid / Solid etc.
        panel_name = assay_panel["_id"]

        if group in user_groups or current_user.is_admin:
            nav[panel_type][tech][group].append(
                {
                    "label": group.upper(),
                    "url": URLS.get(panel_type, {}).get(
                        tech, "home_bp.panels_screen"
                    ),
                    "panel_name": panel_name,
                    "group": group,
                    "panel_type": panel_type,
                    "panel_technology": tech,
                }
            )

    return dict(dynamic_assay_nav=nav)
