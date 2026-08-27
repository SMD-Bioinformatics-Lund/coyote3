"""Common HTTP-layer helpers for the API."""

from __future__ import annotations

from api.app.container import store
from api.application.common.assay_config import (
    get_formatted_assay_config as resolve_formatted_assay_config,
)
from api.contracts.http import ApiListPayload, ApiMutationPayload, ApiPageMeta, ApiSuccessPayload
from api.domain.common.errors import api_error


def api_success(payload, *, meta: dict | None = None) -> dict:
    """Return the standard success envelope for new HTTP routes."""
    return ApiSuccessPayload(payload=payload, meta=meta or {}).model_dump(mode="json")


def api_list(
    items: list,
    *,
    page: int = 1,
    per_page: int = 50,
    total: int | None = None,
    has_next: bool = False,
    has_previous: bool = False,
    meta: dict | None = None,
) -> dict:
    """Return the standard list envelope for new HTTP routes."""
    return ApiListPayload(
        items=items,
        pagination=ApiPageMeta(
            page=page,
            per_page=per_page,
            total=len(items) if total is None else total,
            has_next=has_next,
            has_previous=has_previous,
        ),
        meta=meta or {},
    ).model_dump(mode="json")


def api_mutation(
    *,
    resource: str,
    action: str,
    resource_id: str | None = None,
    message: str | None = None,
    meta: dict | None = None,
) -> dict:
    """Return the standard mutation envelope for new HTTP routes."""
    return ApiMutationPayload(
        resource=resource,
        resource_id=resource_id,
        action=action,
        message=message,
        meta=meta or {},
    ).model_dump(mode="json")


def get_formatted_assay_config(sample: dict):
    """Resolve one sample's ASPC through the shared application service."""
    return resolve_formatted_assay_config(
        sample,
        assay_panel_repository=store.assay_panel_repository,
        assay_configuration_repository=store.assay_configuration_repository,
    )


__all__ = [
    "api_error",
    "api_list",
    "api_mutation",
    "api_success",
    "get_formatted_assay_config",
]
