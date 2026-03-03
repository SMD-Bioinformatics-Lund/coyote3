
"""Shared helpers for DNA variant list/detail routes."""

from coyote.errors.exceptions import AppError
from coyote.services.api_client.api_client import ApiRequestError


def raise_api_page_error(sample_id: str, page: str, exc: ApiRequestError) -> None:
    raise AppError(
        status_code=exc.status_code or 502,
        message=f"Failed to load {page}.",
        details=f"Sample {sample_id}: {exc}",
    )
