# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Report path/id generation helpers."""

from coyote.domain.common.reporting import utc_now


def get_report_timestamp() -> str:
    """Return the UTC report-name suffix in YYMMDDhhmmss format, to the second."""
    return f"{utc_now():%y%m%d%H%M%S}"
