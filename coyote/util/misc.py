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
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from typing import Any

from flask import Response, flash, redirect, url_for
from flask_login import current_user, login_required

from coyote.extensions import store, util


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
    """
    Generate a dynamic navigation structure for assays.

    This function retrieves the user's accessible assay map (`asp_map`) and organizes it into a nested dictionary.
    Each entry includes metadata such as the group name, panel type, technology, and associated assays.

    The resulting structure is suitable for rendering navigation menus or other UI components.

    Returns:
        dict: A dictionary with the following structure:
            {
                "panel_type": {
                    "panel_tech": {
                        "group_name": {
                            "label": str,  # Uppercase group name
                            "url": str,    # URL for navigation
                            "group": str,  # Group name
                            "panel_type": str,  # Panel type
                            "panel_technology": str,  # Panel technology
                            "assays": list  # List of assays
                        }
                    }
                }
    """

    user_asp_map = current_user.asp_map  # or `assay_map`

    nav = defaultdict(lambda: defaultdict(dict))

    for panel_type, tech_dict in user_asp_map.items():
        for panel_tech, group_dict in tech_dict.items():
            for group_name, assays in group_dict.items():
                nav[panel_type][panel_tech][group_name] = {
                    "label": group_name.upper(),
                    "url": "home_bp.samples_home",
                    "group": group_name,
                    "panel_type": panel_type,
                    "panel_technology": panel_tech,
                    "assays": assays,
                }

    return dict(dynamic_assay_nav=nav)


def get_sample_and_assay_config(sample_id: str) -> tuple:
    """
    Fetches the sample, its assay configuration, and the formatted config schema for a given `sample_id`.

    Validates the presence of the sample and its configuration. If either is missing, flashes an error and returns a redirect response.

    Returns:
        tuple: (sample, formatted_assay_config, assay_config_schema)
        If a redirect is needed due to missing data, returns a Flask redirect response instead.
    """
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        flash(f"Sample '{sample_id}' not found.", "red")
        return redirect(url_for("home_bp.samples_home"))

    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )

    if not assay_config:
        flash(
            f"No config found for assay '{sample.get("assay")}' ({sample.get("profile", "production")})",
            "red",
        )
        return redirect(url_for("home_bp.samples_home"))

    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    formatted_config = util.common.format_assay_config(
        deepcopy(assay_config), assay_config_schema
    )

    return sample, formatted_config, assay_config_schema
