"""Package-local synthetic records and fake ports for independent tests."""

import json
from datetime import UTC, datetime

from coyote.application.reporting.document import ReportDocumentBuilder
from coyote.application.reporting.presentation import ReportPresentation
from coyote.application.reporting.report_context import prepare_render_context
from smd_reports import ReportLoader


def document(inputs, analyte="dna", preview=True):
    """Validate the adapter's synthetic input against the installed package contract."""
    prepared = prepare_render_context(inputs, analyte=analyte, preview=preview)
    prepared["report_generated_at"] = datetime(2026, 1, 2, 12, tzinfo=UTC)
    result = ReportDocumentBuilder(
        prepared, analyte=analyte, preview=preview, presentation=ReportPresentation()
    ).build()
    ReportLoader().loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return result


def sections(result):
    """Index projected report sections by their stable clinical role."""
    return {section["key"]: section for section in result["sections"]}
