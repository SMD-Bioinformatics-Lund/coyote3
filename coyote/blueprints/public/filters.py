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
This module defines custom Jinja2 template filters for Flask applications in the Coyote3
framework. These filters facilitate the formatting, annotation, and transformation of
genomic variant and clinical data for presentation in web-based reports.
"""

from flask import current_app as app
import random


def get_color(color_map: dict, item: str) -> str:
    """Get color class for a given item from the color map or return a random color.
    Args:
        color_map (dict): Mapping of items to color classes.
        item (str): The item to get the color for.
    Returns:
        str: The color class for the item.
    """
    random_colors = ["bg-green-600", "bg-red-300", "bg-brown-300", "bg-teal-700", "bg-indigo-500"]
    key = item.lower().strip()
    if key in color_map:
        return color_map[key]
    return random.choice(random_colors)


@app.template_filter()
def format_input_material(input_material: list) -> str:
    """
    Format input material string for display.

    Args:
        input_material (list): List of input material strings.
    Returns:
        str: Formatted input material string.
    """
    color_map = {
        "blood": "bg-orange-600",
        "bone marrow": "bg-yellow-600",
        "ffpe": "bg-purple-500",
        "ft": "bg-blue-600",
        "skin": "bg-pink-500",
        "csf": "bg-gray-600",
        "plasma": "bg-gray-800",
        "saliva": "bg-brown-300",
    }

    formatted_items = []
    for item in input_material:
        color_class = get_color(color_map, item)
        formatted_items.append(
            f'<span class="text-white px-2 py-1 rounded-full mr-2 text-xs {color_class}">{item}</span>'
        )

    return " ".join(formatted_items)
