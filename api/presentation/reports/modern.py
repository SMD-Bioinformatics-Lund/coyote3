"""Select the packaged modern layout for the web application's temporary report trial."""

from typing import Any

from coyote3.application.reporting.report_renderer import render_report_html


def render_modern_report_html(**report_inputs: Any) -> str:
    """Render established clinical inputs using the packaged alternate Jinja layout.

    Args:
        **report_inputs: Prepared report inputs accepted by render_report_html.

    Returns:
        Standalone modern HTML containing its embedded styles.
    """
    return render_report_html(**report_inputs, layout="modern")
