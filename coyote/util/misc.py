#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#


"""
Coyote3 Miscellaneous Utilities
=====================================

This module provides miscellaneous classes and utilities for the Coyote3
application, such as the `EnhancedJSONEncoder` for custom JSON encoding
and other helper functions.

It serves as a central point for managing these utility classes and
functions used across the application.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import json
from datetime import datetime
from typing import Any
from collections import defaultdict
from coyote.extensions import store, util
from flask_login import current_user
from flask import flash, redirect, url_for
from flask import current_app as app
from copy import deepcopy


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
            return obj.isoformat()  # or use obj.strftime(...) for a custom format
        return super().default(obj)


# -------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------
def get_dynamic_assay_nav() -> dict:
    """
    Generates a dynamic navigation structure for assays.

    Retrieves the current user's accessible assay map (`asp_map`) and organizes it into a nested dictionary structure.
    Each entry contains metadata such as the group name, panel type, technology, and associated assays.

    The resulting dictionary is suitable for rendering navigation menus or other UI components.

    Returns:
        dict: A dictionary with the structure:
            {
                "dynamic_assay_nav": {
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

    # Convert to a sorted dict at each level
    def sort_nested_dict(d):
        """
        Recursively sorts a nested dictionary by keys.
        """
        if isinstance(d, dict):
            return dict(sorted((k, sort_nested_dict(v)) for k, v in d.items()))
        return d

    sorted_nav = sort_nested_dict(nav)

    app.logger.info(sorted_nav)

    return dict(dynamic_assay_nav=sorted_nav)


def get_sample_and_assay_config(sample_id: str) -> tuple:
    """
    Fetches the sample, its assay configuration, and the formatted config schema for a given `sample_id`.

    Checks if the sample exists using the provided `sample_id`. If not found, flashes an error and redirects to the samples home page.

    If the sample exists, retrieves its assay configuration. If the configuration is missing, flashes an error and redirects to the samples home page.

    If both the sample and its configuration are found, fetches the associated schema and formats the configuration.

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
    formatted_config = util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)

    return sample, formatted_config, assay_config_schema
