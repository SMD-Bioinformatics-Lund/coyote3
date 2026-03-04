"""Report preview/save helpers built on the shared web API client."""

from __future__ import annotations

from typing import Any, Literal

from flask import render_template

from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.base import ApiPayload

ReportAnalyte = Literal["dna", "rna"]


def _report_endpoint(analyte: ReportAnalyte, sample_id: str, action: str) -> str:
    analyte_norm = str(analyte).strip().lower()
    if analyte_norm == "dna":
        return api_endpoints.dna_sample(sample_id, "report", action)
    if analyte_norm == "rna":
        return api_endpoints.rna_sample(sample_id, "report", action)
    raise ApiRequestError(f"Unsupported report analyte: {analyte}")


def fetch_preview_payload(
    analyte: ReportAnalyte,
    sample_id: str,
    *,
    include_snapshot: bool = False,
    save: bool = False,
) -> ApiPayload:
    params: dict[str, Any] = {"save": 1 if save else 0}
    if include_snapshot:
        params["include_snapshot"] = 1
    return get_web_api_client().get_json(
        _report_endpoint(analyte, sample_id, "preview"),
        headers=forward_headers(),
        params=params,
    )


def render_preview_html(payload: ApiPayload) -> str:
    template_name = payload.report.get("template")
    context = payload.report.get("context") or {}
    if not template_name:
        raise ApiRequestError("API response missing report template")
    if not isinstance(context, dict):
        raise ApiRequestError("API response missing report context")
    return render_template(str(template_name), **context)


def save_report_from_preview(analyte: ReportAnalyte, sample_id: str) -> ApiPayload:
    preview_payload = fetch_preview_payload(analyte, sample_id, include_snapshot=True, save=True)
    html = render_preview_html(preview_payload)
    snapshot_rows = preview_payload.report.get("snapshot_rows", [])
    return get_web_api_client().post_json(
        _report_endpoint(analyte, sample_id, "save"),
        headers=forward_headers(),
        json_body={"html": html, "snapshot_rows": snapshot_rows},
    )
