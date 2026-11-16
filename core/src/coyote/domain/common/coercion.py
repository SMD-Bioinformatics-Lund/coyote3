# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Plain-value parsing shared by application workflows and transport adapters."""


def coerce_bool(value: object, default: bool = True) -> bool:
    """Interpret the existing flag-input spellings without changing fallback behavior.

    Args:
        value: Boolean or case-insensitive true/false, 1/0, yes/no or on/off text.
            Whitespace is ignored for text. Other values use the supplied default.
        default: Fallback for unsupported inputs, including None; defaults to True.

    Returns:
        Parsed boolean, or the explicit fallback when the input is unsupported.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def coerce_nonnegative_int(value: object, default: int = 0) -> int:
    """Parse a nonnegative read count using the caller's explicit missing-value policy.

    Args:
        value: Count text or number supplied by a supported input source.
        default: Value used for malformed, negative or overflowing input.

    Returns:
        Nonnegative integer, or the explicit default.
    """
    try:
        if not isinstance(value, (str, int, float, bytes, bytearray)):
            return default
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError, OverflowError):
        return default
