"""Select smd-reports for the web application's modern report presentation."""

from typing import Any

from api.presentation.reports.branding import render_branded_report_html
from coyote3.application.reporting.report_renderer import render_report_html


def render_modern_report_html(
    *, branding_config: dict[str, Any] | None = None, **report_inputs: Any
) -> str:
    """Render evaluated clinical inputs through the smd-reports Python interface.

    Args:
        branding_config: Host center settings, or None for a standalone unbranded render.
        **report_inputs: Prepared report inputs accepted by render_report_html.

    Returns:
        Standalone modern HTML containing its embedded styles.
    """
    if branding_config is not None:
        return render_branded_report_html(config=branding_config, **report_inputs, layout="modern")
    return render_report_html(**report_inputs, layout="modern")
