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

"""Home blueprint gene write routes."""

import re

from flask import Response, flash, g, jsonify, request
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.web import log_api_error
from coyote.services.audit_logs.decorators import log_action


@home_bp.route("/<string:sample_id>/genes/apply-isgl", methods=["POST"])
@log_action(action_name="apply_isgl", call_type="user")
@login_required
def apply_isgl(sample_id: str) -> Response:
    """
    Apply adhoc in-study gene list to the sample's adhoc gene filter.
    """
    payload = request.get_json(silent=True) or {}
    isgl_ids = payload.get("isgl_ids", [])

    if payload and (isgl_ids or isgl_ids == []):
        g.audit_metadata = {
            "sample": sample_id,
            "isgl_ids": isgl_ids,
        }
        try:
            get_web_api_client().post_json(
                api_endpoints.home_sample(sample_id, "genes", "apply-isgl"),
                headers=forward_headers(),
                json_body={"isgl_ids": (isgl_ids if isinstance(isgl_ids, list) else [])},
            )
            flash(f"Gene list(s) {isgl_ids} applied to sample.", "green")
            app.home_logger.info(
                f"Applied gene list(s) {isgl_ids} to sample {sample_id} adhoc gene filter"
            )
        except ApiRequestError as exc:
            log_api_error(
                exc,
                logger=app.home_logger,
                log_message=f"Failed to apply gene list(s) via API for sample {sample_id}",
                flash_message=f"Failed to apply gene list(s): {exc}",
            )

    return jsonify({"ok": True})


@home_bp.route("/<string:sample_id>/adhoc_genes", methods=["POST"])
@log_action(action_name="save_adhoc_genes", call_type="user")
@login_required
def save_adhoc_genes(sample_id: str) -> Response:
    """
    Save adhoc genes to the sample's adhoc gene filter.
    """
    data = request.get_json()
    genes = [g.strip() for g in re.split(r"[ ,\n]+", data.get("genes", "")) if g.strip()]
    genes.sort()
    label = data.get("label") or "adhoc"
    try:
        payload = {"genes": data.get("genes", "")}
        if label:
            payload["label"] = label
        get_web_api_client().post_json(
            api_endpoints.home_sample(sample_id, "adhoc_genes", "save"),
            headers=forward_headers(),
            json_body=payload,
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to save AdHoc genes via API for sample {sample_id}",
            flash_message=f"Failed to save AdHoc genes: {exc}",
        )
        return jsonify({"ok": False}), 502
    g.audit_metadata = {
        "sample": sample_id,
        "label": label,
        "gene_count": len(genes),
    }
    flash("AdHoc genes saved to sample.", "green")
    app.home_logger.info(f"Saved {len(genes)} AdHoc genes to sample {sample_id} adhoc gene filter")

    return jsonify({"ok": True})


@home_bp.route("/<string:sample_id>/adhoc_genes/clear", methods=["POST"])
@log_action(action_name="clear_adhoc_genes", call_type="user")
@login_required
def clear_adhoc_genes(sample_id: str) -> Response:
    """
    Clear adhoc genes from the sample's adhoc gene filter.
    """
    try:
        get_web_api_client().post_json(
            api_endpoints.home_sample(sample_id, "adhoc_genes", "clear"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to clear AdHoc genes via API for sample {sample_id}",
            flash_message=f"Failed to clear AdHoc genes: {exc}",
        )
        return jsonify({"ok": False}), 502
    g.audit_metadata = {
        "sample": sample_id,
        "action": "clear_adhoc_genes",
    }
    flash("AdHoc genes cleared from sample.", "green")
    app.home_logger.info(f"Cleared AdHoc genes from sample {sample_id} adhoc gene filter")
    return jsonify({"ok": True})
