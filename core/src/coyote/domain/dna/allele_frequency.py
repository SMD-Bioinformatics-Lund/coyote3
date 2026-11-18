# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Allele-fraction validation shared by record contracts and reporting."""

import math


def allele_fraction(value: object) -> float | None:
    """Read a finite allele fraction without converting booleans into measurements.

    Args:
        value: Numeric fraction or numeric text in the inclusive interval zero to one.

    Returns:
        Fraction, including measured zero, or None for missing or invalid evidence.
    """
    if isinstance(value, bool):
        return None
    try:
        fraction = float(value) if isinstance(value, (int, float, str)) else float(str(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return fraction if math.isfinite(fraction) and 0 <= fraction <= 1 else None
