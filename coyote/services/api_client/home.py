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
    """Fetch sample-list data for the UI sample home screen.

    Args:
        status: Selected sample status filter.
        search_str: Free-text search value.
        search_mode: Search mode selector.
        sample_view: Requested sample view mode.
        page: Requested page number.
        per_page: Requested page size.
        live_page: Current live-sample page.
        done_page: Current completed-sample page.
        live_per_page: Live-sample page size.
        done_per_page: Completed-sample page size.
        profile_scope: Profile-scope filter.
        panel_type: Optional panel-type filter.
        panel_tech: Optional panel-technology filter.
        assay_group: Optional assay-group filter.

    Returns:
        The decoded API payload for the sample list view.
    """
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
    """Fetch the edit-context payload for a sample.

    Args:
        sample_id: Sample identifier.

    Returns:
        The decoded API payload for the sample edit page.
    """
    return get_web_api_client().get_json(
        api_endpoints.home_sample(sample_id, "edit_context"),
        headers=forward_headers(),
    )


def apply_isgl(sample_id: str, isgl_ids: list[str]) -> ApiPayload:
    """Apply selected genelists to a sample.

    Args:
        sample_id: Sample identifier.
        isgl_ids: Selected genelist identifiers.

    Returns:
        The decoded API payload for the mutation result.
    """
    return get_web_api_client().put_json(
        api_endpoints.home_sample(sample_id, "genes", "apply-isgl"),
        headers=forward_headers(),
        json_body={"isgl_ids": isgl_ids},
    )


def save_adhoc_genes(sample_id: str, *, genes: str, label: str) -> ApiPayload:
    """Persist an ad hoc gene selection for a sample.

    Args:
        sample_id: Sample identifier.
        genes: Raw gene input string.
        label: User-facing label for the ad hoc gene set.

    Returns:
        The decoded API payload for the mutation result.
    """
    return get_web_api_client().put_json(
        api_endpoints.home_sample(sample_id, "adhoc_genes", "save"),
        headers=forward_headers(),
        json_body={"genes": genes, "label": label},
    )


def clear_adhoc_genes(sample_id: str) -> ApiPayload:
    """Remove ad hoc genes from a sample.

    Args:
        sample_id: Sample identifier.

    Returns:
        The decoded API payload for the mutation result.
    """
    return get_web_api_client().delete_json(
        api_endpoints.home_sample(sample_id, "adhoc_genes", "clear"),
        headers=forward_headers(),
    )


def fetch_report_path(sample_id: str, report_id: str) -> Path:
    """Fetch the on-disk report path for a sample report.

    Args:
        sample_id: Sample identifier.
        report_id: Report identifier.

    Returns:
        The resolved filesystem path returned by the API context payload.
    """
    payload = get_web_api_client().get_json(
        api_endpoints.home_sample(sample_id, "reports", report_id, "context"),
        headers=forward_headers(),
    )
    return Path(str(payload.get("filepath") or ""))
