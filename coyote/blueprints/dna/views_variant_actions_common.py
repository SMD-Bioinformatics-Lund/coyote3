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

"""Shared helpers for DNA variant action routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Response, current_app as app, redirect, request, url_for

from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


def headers() -> dict[str, str]:
    return forward_headers()


def call_api(sample_id: str, log_message: str, api_call: Callable[[], Any]) -> bool:
    try:
        api_call()
        return True
    except ApiRequestError as exc:
        app.logger.error("%s for sample %s: %s", log_message, sample_id, exc)
        return False


def resolve_target_id(*keys: str) -> str:
    for key in keys:
        value = request.view_args.get(key)
        if value:
            return value
    return ""


def derive_nomenclature(form_data: dict[str, Any]) -> str:
    if form_data.get("fusionpoints"):
        return "f"
    if form_data.get("translocpoints"):
        return "t"
    if form_data.get("cnvvar"):
        return "cn"
    return "p"


def redirect_target(sample_id: str, target_id: str, nomenclature: str) -> Response:
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=target_id))
    if nomenclature == "t":
        return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=target_id))
    if nomenclature == "cn":
        return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=target_id))
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=target_id))


def bulk_toggle(
    sample_id: str,
    enabled: str | None,
    action: str | None,
    variant_ids: list[str],
    operation_label: str,
    endpoint: str,
) -> None:
    if not enabled or action not in {"apply", "remove"}:
        return

    apply = action == "apply"
    verb = "mark" if apply else "unmark"
    call_api(
        sample_id,
        f"Failed to bulk {verb} variants {operation_label} via API",
        lambda: get_web_api_client().post_json(
            endpoint,
            headers=headers(),
            params={"apply": str(apply).lower(), "variant_ids": variant_ids},
        ),
    )
