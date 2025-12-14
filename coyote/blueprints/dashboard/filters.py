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

from flask import current_app as app

@app.template_filter("shorten_number")
def shorten_number(n: int) -> str:
    """
    Shortens a large number using metric suffixes (K, M, B, T, P).

    Args:
        n (float or int): The number to shorten.

    Returns:
        str: The shortened number as a string with an appropriate suffix.
    """
    for unit in ['', 'K', 'M', 'B', 'T']:
        if abs(n) < 1000:
            if float(n).is_integer():
                return f"{int(n)}{unit}"
            else:
                return f"{n:.1f}{unit}".rstrip('0').rstrip('.')
        n /= 1000
    if float(n).is_integer():
        return f"{int(n)}P"
    else:
        return f"{n:.1f}P".rstrip('0').rstrip('.')
