# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP delivery of temporary report previews generated without report persistence."""

from pydantic import BaseModel


class ReportPreviewBundlePayload(BaseModel):
    """Deliver matching temporary HTML/PDF content for browser preview and local download."""

    html: str
    pdf_base64: str
    filename: str
    snapshot_count: int
    reporting_warning: str | None = None
