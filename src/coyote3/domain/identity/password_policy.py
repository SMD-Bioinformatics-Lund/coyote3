"""Established local password complexity rules shared by account workflows."""

import re

from coyote3.domain.common.errors import api_error


def validate_new_password(new_password: str) -> None:
    """Require ten characters plus lowercase, uppercase, numeric and symbol matches.

    Args:
        new_password: Proposed password, without trimming whitespace.

    Raises:
        AppError: The first unmet requirement, in length, lowercase, uppercase, digit
            and symbol order. ASCII letters and regex digit/symbol semantics are retained.
    """
    password = str(new_password or "")
    if len(password) < 10:
        raise api_error(400, "Password must be at least 10 characters")
    for pattern, message in (
        (r"[a-z]", "Password must include a lowercase letter"),
        (r"[A-Z]", "Password must include an uppercase letter"),
        (r"\d", "Password must include a number"),
        (r"[\W_]", "Password must include a symbol"),
    ):
        if not re.search(pattern, password):
            raise api_error(400, message)
