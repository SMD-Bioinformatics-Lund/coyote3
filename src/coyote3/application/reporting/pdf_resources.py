"""Restricted resource access for generated clinical PDFs."""

import base64
import re
from xml.etree import ElementTree

from weasyprint import URLFetcher


class _ReportSvgTreeBuilder(ElementTree.TreeBuilder):
    """Reject document type declarations after the XML parser decodes the input."""

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        """Reject DTDs in every supported XML encoding before entities are expanded.

        Args:
            name: Declared root element name.
            pubid: Optional public identifier supplied by the XML parser.
            system: Optional external DTD location supplied by the XML parser.

        Raises:
            ValueError: All document type declarations are forbidden in report images.
        """
        raise ValueError("Report SVG cannot contain document type declarations")


def _local_svg_reference(reference: str, *, allow_embedded_font: bool) -> bool:
    """Allow SVG fragments and validated self-contained WOFF2 stylesheet fonts.

    Args:
        reference: CSS URL, optionally surrounded by whitespace and quotes.
        allow_embedded_font: Whether the URL belongs to an SVG style element.

    Returns:
        True for a fragment or permitted WOFF2 data URL; false for other references.
    """
    reference = reference.strip(" \t\r\n'\"")
    if reference.startswith("#"):
        return True
    if not allow_embedded_font or not reference.startswith("data:font/woff2;base64,"):
        return False
    try:
        content = base64.b64decode(reference.partition(",")[2], validate=True)
    except ValueError:
        return False
    return content.startswith(b"wOF2")


def validate_report_svg(content: bytes) -> None:
    """Reject active/external SVG content while allowing embedded WOFF2 fonts.

    Args:
        content: SVG XML, limited to one megabyte before parsing.

    Raises:
        ValueError: The document is oversized, malformed, active, or references external content.
    """
    if len(content) > 1024 * 1024 or re.search(b"<!DOCTYPE|<!ENTITY", content, re.I):
        raise ValueError("Report SVG must be a small self-contained image")
    try:
        root = ElementTree.fromstring(
            content, parser=ElementTree.XMLParser(target=_ReportSvgTreeBuilder())
        )
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
            not _local_svg_reference(reference, allow_embedded_font=tag == "style")
            for reference in re.findall(r"url\s*\((.*?)\)", css, re.I | re.S)
        ):
            raise ValueError("Report SVG cannot reference external content")


class ReportResourceFetcher(URLFetcher):
    """Allow embedded images and fonts, never network or file reads."""

    def __init__(self):
        """Restrict the parent fetcher to data URLs and disable redirects."""
        super().__init__(allowed_protocols={"data"}, allow_redirects=False)

    def fetch(self, url: str, headers: dict | None = None):
        """Validate an embedded resource and reject unsafe SVG content before rendering.

        Args:
            url: Base64 PNG, JPEG, self-contained SVG or WOFF2 font data URL.
            headers: Optional headers passed to the restricted parent fetcher.

        Returns:
            The parent's decoded resource response.

        Raises:
            ValueError: The type, size, base64 encoding or SVG content is invalid.
        """
        if not url.startswith(
            (
                "data:image/png;base64,",
                "data:image/jpeg;base64,",
                "data:image/svg+xml;base64,",
                "data:font/woff2;base64,",
            )
        ):
            raise ValueError(
                "Report resources must be embedded PNG, JPEG or self-contained SVG images, "
                "or WOFF2 fonts"
            )
        if len(url) > 20 * 1024 * 1024:
            raise ValueError("Embedded report resource exceeds the size limit")
        if url.startswith("data:font/woff2;base64,"):
            content = base64.b64decode(url.partition(",")[2], validate=True)
            if not content.startswith(b"wOF2"):
                raise ValueError("Embedded report font must be WOFF2")
        if url.startswith("data:image/svg+xml;base64,"):
            validate_report_svg(base64.b64decode(url.partition(",")[2], validate=True))
        return super().fetch(url, headers)
