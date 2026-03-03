"""Flask-side bridge for report preview rendering and save orchestration."""

from __future__ import annotations

from typing import Any

from flask import render_template

from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.base import ApiPayload


def _sample_report_endpoint(analyte: str, sample_id: str, action: str) -> str:
    analyte_norm = str(analyte).strip().lower()
    if analyte_norm == "dna":
        return api_endpoints.dna_sample(sample_id, "report", action)
    if analyte_norm == "rna":
        return api_endpoints.rna_sample(sample_id, "report", action)
    raise ApiRequestError(f"Unsupported report analyte: {analyte}")


def render_template_from_api_payload(payload: ApiPayload) -> str:
    template_name = payload.report.get("template")
    context = payload.report.get("context") or {}
    if not template_name:
        raise ApiRequestError("API response missing report template")
    if not isinstance(context, dict):
        raise ApiRequestError("API response missing report context")
    return render_template(str(template_name), **context)


def fetch_preview_payload(
    analyte: str,
    sample_id: str,
    *,
    include_snapshot: bool = False,
    save: bool = False,
) -> ApiPayload:
    endpoint = _sample_report_endpoint(analyte, sample_id, "preview")
    params: dict[str, Any] = {"save": 1 if save else 0}
    if include_snapshot:
        params["include_snapshot"] = 1
    return get_web_api_client().get_json(endpoint, headers=forward_headers(), params=params)


def persist_rendered_report(
    analyte: str,
    sample_id: str,
    *,
    html: str,
    snapshot_rows: list[dict[str, Any]] | None = None,
) -> ApiPayload:
    endpoint = _sample_report_endpoint(analyte, sample_id, "save")
    return get_web_api_client().post_json(
        endpoint,
        headers=forward_headers(),
        json_body={"html": html, "snapshot_rows": snapshot_rows or []},
    )
