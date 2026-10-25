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
