"""Restricted resource access for generated clinical PDFs."""

import base64
import re
from xml.etree import ElementTree

from weasyprint import URLFetcher


def validate_report_svg(content: bytes) -> None:
    """Reject active content and external references in an embedded report logo.

    Args:
        content: SVG XML, limited to one megabyte before parsing.

    Raises:
        ValueError: The document is oversized, malformed, active, or references external content.
    """
    if len(content) > 1024 * 1024 or re.search(b"<!DOCTYPE|<!ENTITY", content, re.I):
        raise ValueError("Report SVG must be a small self-contained image")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise ValueError("Report SVG is not valid XML") from error
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Report SVG must have an SVG root")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in {"script", "foreignobject", "image", "animate", "animatetransform", "set"}:
            raise ValueError("Report SVG cannot contain active or nested image content")
        for key, value in element.attrib.items():
            attribute = key.rsplit("}", 1)[-1].lower()
            if attribute.startswith("on") or (attribute == "href" and not value.startswith("#")):
                raise ValueError("Report SVG cannot reference external content")
        css = " ".join([element.text or "", *element.attrib.values()])
        if "@import" in css.lower() or any(
            not reference.strip(" \t\r\n'\"").startswith("#")
            for reference in re.findall(r"url\s*\((.*?)\)", css, re.I | re.S)
        ):
            raise ValueError("Report SVG cannot reference external content")


class ReportResourceFetcher(URLFetcher):
    """Allow embedded plots and self-contained SVG logos, never network or file reads."""

    def __init__(self):
        """Restrict the parent fetcher to data URLs and disable redirects."""
        super().__init__(allowed_protocols={"data"}, allow_redirects=False)

    def fetch(self, url: str, headers: dict | None = None):
        """Validate an embedded image and reject unsafe SVG content before rendering.

        Args:
            url: Base64 PNG, JPEG or self-contained SVG data URL.
            headers: Optional headers passed to the restricted parent fetcher.

        Returns:
            The parent's decoded resource response.

        Raises:
            ValueError: The type, size, base64 encoding or SVG content is invalid.
        """
        if not url.startswith(
            ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/svg+xml;base64,")
        ):
            raise ValueError(
                "Report resources must be embedded PNG, JPEG or self-contained SVG images"
            )
        if len(url) > 20 * 1024 * 1024:
            raise ValueError("Embedded report image exceeds the size limit")
        if url.startswith("data:image/svg+xml;base64,"):
            validate_report_svg(base64.b64decode(url.partition(",")[2], validate=True))
        return super().fetch(url, headers)
