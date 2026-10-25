"""HTTP delivery of alternate reports generated without report persistence."""

from pydantic import BaseModel


class ReportTrialPayload(BaseModel):
    """Deliver matching temporary HTML/PDF content for browser preview and local download."""

    html: str
    pdf_base64: str
    filename: str
    snapshot_count: int
