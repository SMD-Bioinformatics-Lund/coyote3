"""Home blueprint API-call helpers.

These helpers keep Flask view functions thin by centralizing API request building
and payload extraction for home/sample/report flows.
"""

from __future__ import annotations

from pathlib import Path

from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import forward_headers, get_web_api_client
from coyote.services.api_client.base import ApiPayload


def fetch_samples(
    *,
    status: str,
    search_str: str,
    search_mode: str,
    sample_view: str,
    page: int,
    per_page: int,
    live_page: int,
    done_page: int,
    live_per_page: int,
    done_per_page: int,
    profile_scope: str,
    panel_type: str | None,
    panel_tech: str | None,
    assay_group: str | None,
) -> ApiPayload:
    params = {
        "status": status,
        "search_str": search_str,
        "search_mode": search_mode,
        "sample_view": sample_view,
        "page": page,
        "per_page": per_page,
        "live_page": live_page,
        "done_page": done_page,
        "live_per_page": live_per_page,
        "done_per_page": done_per_page,
        "profile_scope": profile_scope,
        "panel_type": panel_type,
        "panel_tech": panel_tech,
        "assay_group": assay_group,
    }
    return get_web_api_client().get_json(
        api_endpoints.home("samples"),
        headers=forward_headers(),
        params=params,
    )


def fetch_edit_context(sample_id: str) -> ApiPayload:
    return get_web_api_client().get_json(
        api_endpoints.home_sample(sample_id, "edit_context"),
        headers=forward_headers(),
    )


def apply_isgl(sample_id: str, isgl_ids: list[str]) -> ApiPayload:
    return get_web_api_client().put_json(
        api_endpoints.home_sample(sample_id, "genes", "apply-isgl"),
        headers=forward_headers(),
        json_body={"isgl_ids": isgl_ids},
    )


def save_adhoc_genes(sample_id: str, *, genes: str, label: str) -> ApiPayload:
    return get_web_api_client().put_json(
        api_endpoints.home_sample(sample_id, "adhoc_genes", "save"),
        headers=forward_headers(),
        json_body={"genes": genes, "label": label},
    )


def clear_adhoc_genes(sample_id: str) -> ApiPayload:
    return get_web_api_client().delete_json(
        api_endpoints.home_sample(sample_id, "adhoc_genes", "clear"),
        headers=forward_headers(),
    )


def fetch_report_path(sample_id: str, report_id: str) -> Path:
    payload = get_web_api_client().get_json(
        api_endpoints.home_sample(sample_id, "reports", report_id, "context"),
        headers=forward_headers(),
    )
    return Path(str(payload.get("filepath") or ""))
