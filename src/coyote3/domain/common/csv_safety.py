"""Spreadsheet-safe text for CSV exports without changing numeric measurements."""

import re

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def spreadsheet_text(value: object) -> str:
    """Prevent a text cell from being interpreted as a spreadsheet formula.

    Args:
        value: Export cell; None becomes empty and numeric measurements stay numeric.

    Returns:
        Text prefixed with an apostrophe for formula/control prefixes, otherwise unchanged.
        CSV delimiter and quote escaping remains the serializer's responsibility.
    """
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if _NUMBER.fullmatch(stripped):
        return text
    if text.startswith(("\t", "\r", "\n")) or stripped.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
