"""Restricted resource access for generated clinical PDFs."""

from weasyprint import URLFetcher


class ReportResourceFetcher(URLFetcher):
    """Allow embedded raster plots, never network requests or local-file reads."""

    def __init__(self):
        """Restrict the parent fetcher to data URLs and disable redirects."""
        super().__init__(allowed_protocols={"data"}, allow_redirects=False)

    def fetch(self, url: str, headers: dict | None = None):
        """Validate the image type and encoded size before decoding."""
        if not url.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
            raise ValueError("Report resources must be embedded PNG or JPEG images")
        if len(url) > 20 * 1024 * 1024:
            raise ValueError("Embedded report image exceeds the size limit")
        return super().fetch(url, headers)
