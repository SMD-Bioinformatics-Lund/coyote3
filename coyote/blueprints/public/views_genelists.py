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

"""Public blueprint genelist routes."""

from __future__ import annotations

from flask import current_app as app
from flask import redirect, render_template, request, flash
from werkzeug import Response

from coyote.blueprints.public import public_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, get_web_api_client


@public_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
def view_genelist(genelist_id: str) -> Response | str:
    """
    Display a specific genelist and optionally filter its genes by a selected assay.
    """
    selected_assay = request.args.get("assay")
    try:
        params = {"assay": selected_assay} if selected_assay else None
        payload = get_web_api_client().get_json(
            api_endpoints.public("genelists", genelist_id, "view_context"),
            params=params,
        )
    except ApiRequestError:
        app.public_logger.info(
            "Genelist '%s' not found via API",
            genelist_id,
            extra={"genelist_id": genelist_id},
        )
        flash(f"Genelist '{genelist_id}' not found!", "red")
        return redirect(request.url)

    return render_template(
        "isgl/view_isgl.html",
        genelist=payload.genelist,
        selected_assay=payload.selected_assay,
        filtered_genes=payload.filtered_genes,
        germline_genes=payload.germline_genes,
        is_public=payload.is_public,
    )
