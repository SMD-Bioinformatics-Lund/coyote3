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
