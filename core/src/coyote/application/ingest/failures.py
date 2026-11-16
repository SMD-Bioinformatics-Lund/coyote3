# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Public failure explanations for durable ingestion jobs."""

from pathlib import Path

from pydantic import ValidationError

from coyote.domain.exceptions import AppError


def ingest_failure_message(exc: Exception, *, retryable: bool) -> str:
    """Expose validation explanations without serializing internal exception details.

    Args:
        exc: Failure raised during validation, input access or execution.
        retryable: Whether to return the generic temporary-failure explanation.

    Returns:
        Bounded validation text or a generic operational error. Pydantic input values
        and internal errors are excluded; permission failures name only the basename.
    """
    if retryable:
        return "Temporary service failure; ingestion will be retried"
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
            for item in exc.errors(include_input=False, include_context=False, include_url=False)
        )[:450]
    if isinstance(exc, FileNotFoundError):
        return str(exc)[:450]
    if isinstance(exc, PermissionError):
        return f"Permission denied reading or writing '{Path(exc.filename).name if exc.filename else 'ingest storage'}'; check application UID/GID and directory permissions."
    if isinstance(exc, ValueError) or (isinstance(exc, AppError) and exc.status_code < 500):
        return str(exc)[:450] or "Ingest validation failed"
    return "Ingest write failed; contact an administrator with the task ID"
