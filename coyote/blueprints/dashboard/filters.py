from flask import current_app as app

from coyote.filters.shared import shorten_number as shared_shorten_number


@app.template_filter("shorten_number")
def shorten_number(n: int) -> str:
    """
    Shortens a large number using metric suffixes (K, M, B, T, P).

    Args:
        n (float or int): The number to shorten.

    Returns:
        str: The shortened number as a string with an appropriate suffix.
    """
    return shared_shorten_number(n)
