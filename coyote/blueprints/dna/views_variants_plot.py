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

"""DNA variant plot routes."""

import io
import os

from PIL import Image
from flask import Response, current_app as app, flash, redirect, request, send_file, send_from_directory, url_for

from coyote.blueprints.dna import dna_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/plot/<string:fn>", endpoint="show_any_plot")  # type: ignore
@dna_bp.route("/<string:sample_id>/plot/rotated/<string:fn>", endpoint="show_any_plot_rotated")  # type: ignore
def show_any_plot(sample_id: str, fn: str, angle: int = 90) -> Response | str:
    """
    Displays a plot image for a given sample.

    Args:
        sample_id (str): The unique identifier of the sample.
        fn (str): The filename of the plot image to display.
        angle (int, optional): The angle to rotate the image, defaults to 90.

    Returns:
        flask.Response | str: The image file as a response, or an error message.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "plot_context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA plot context API fetch failed for sample %s: %s", sample_id, exc)
        flash("Failed to load sample context for plot", "red")
        return redirect(url_for("home_bp.samples_home"))

    assay_config = payload.assay_config
    base_dir = payload.plots_base_dir or assay_config.get("reporting", {}).get("plots_path", None)

    if base_dir:
        file_path = os.path.join(base_dir, fn)
        if not os.path.exists(file_path):
            flash(f"File not found: {file_path}", "red")
            return request.url

    if request.endpoint == "dna_bp.show_any_plot_rotated":
        try:
            with Image.open(os.path.join(base_dir, fn)) as img:
                rotated_img = img.rotate(-angle, expand=True)
                img_io = io.BytesIO()
                rotated_img.save(img_io, format="PNG")
                img_io.seek(0)
                return send_file(img_io, mimetype="image/png")
        except Exception as e:
            app.logger.error(f"Error rotating image: {e}")
            flash("Error processing image", "red")
            return request.url

    return send_from_directory(base_dir, fn)
