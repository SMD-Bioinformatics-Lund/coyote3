"""Read optional center-owned report wording without changing clinical configurations."""

import tomllib

from api.config.paths import CENTER_CONFIG_DIR
from coyote3.application.reporting.presentation import ReportPresentation


def load_report_presentation() -> ReportPresentation:
    """Read modern-report wording for this render, retaining defaults for omitted keys.

    Returns:
        Validated presentation settings from report_presentation.toml, or defaults
        when the optional file is absent.

    Raises:
        OSError: An existing configuration file cannot be read.
        ValueError: TOML syntax, message keys, or message values are invalid.
    """
    path = CENTER_CONFIG_DIR / "report_presentation.toml"
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return ReportPresentation()
    return ReportPresentation.model_validate(tomllib.loads(content.decode("utf-8")))
