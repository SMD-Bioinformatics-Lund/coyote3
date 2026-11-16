# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Copy-number and read-support calculations shared by DNA workflows."""

from __future__ import annotations

import math


def normalize_copy_number_ratio(value: object) -> float | None:
    """Parse the numeric or symbolic copy-number ratio used by ingest and storage.

    Args:
        value: Numeric ratio, numeric text, or DEL/LOSS/AMP/DUP/GAIN label.

    Returns:
        Numeric ratio; DEL/LOSS maps to -1, AMP to 1 and DUP/GAIN to 0.5.
        Missing, empty and unparseable values produce None.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().upper()
    symbolic = {"DEL": -1.0, "LOSS": -1.0, "AMP": 1.0, "DUP": 0.5, "GAIN": 0.5}
    if raw in symbolic:
        return symbolic[raw]
    try:
        return float(raw)
    except ValueError:
        return None


def copy_number_from_log2(ratio: float) -> float:
    """Convert a log2 ratio to an unrounded diploid copy-number estimate.

    Args:
        ratio: Log2 ratio relative to a diploid baseline; zero represents two copies.

    Returns:
        Twice two raised to the supplied ratio, without purity correction.

    Raises:
        OverflowError: The estimate exceeds floating-point range.
    """
    return 2 * (2**ratio)


def supporting_read_percent(value: object) -> float | None:
    """Calculate alternate-read support from a reference/alternate count pair.

    Args:
        value: Two counts separated by a comma or slash, or a two-element sequence.
            Counts must be finite, nonnegative integers with a positive total.

    Returns:
        Alternate reads divided by total reads, rounded to three fractional decimal
        places before conversion to percent, matching established report precision.
        Missing, malformed and zero-total evidence returns None; zero alternate
        reads returns 0.0 rather than an unknown value.
    """
    if isinstance(value, str):
        counts = value.replace("/", ",").split(",")
    elif isinstance(value, (list, tuple)):
        counts = list(value)
    else:
        return None
    if len(counts) != 2 or any(isinstance(count, bool) for count in counts):
        return None
    try:
        reference, alternate = (float(count) for count in counts)
    except (TypeError, ValueError, OverflowError):
        return None
    if any(
        not math.isfinite(count) or count < 0 or not count.is_integer()
        for count in (reference, alternate)
    ):
        return None
    total = reference + alternate
    if total == 0 or not math.isfinite(total):
        return None
    return round(round(alternate / total, 3) * 100, 1)
