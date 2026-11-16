# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""SVG styling for the contract-derived collection reference exporter."""

from html import escape

STYLE = """:root{--ink:#213951;--muted:#49617a;--blue:#2875b8;--teal:#17846b;--purple:#7960b2;--amber:#9d5b12;--rose:#c04a65;--badge-ink:#fff}
text{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;fill:var(--ink);text-rendering:optimizeLegibility}
.figure-title{font-size:23px;font-weight:650;letter-spacing:-.45px}
.figure-subtitle{font-size:13px;fill:var(--muted)}
.entity-title{font-size:14px;font-weight:650}
.entity-detail{font-size:12.5px;fill:var(--muted)}
.edge-label{font-size:11.5px;font-weight:550;fill:currentColor}
.figure-note{font-size:12px;fill:var(--muted)}
.blue{color:var(--blue)}.teal{color:var(--teal)}.purple{color:var(--purple)}.amber{color:var(--amber)}.rose{color:var(--rose)}
.glyph{fill:none;stroke:currentColor;stroke-width:1.35;stroke-linecap:round;stroke-linejoin:round}
.connection{fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.network,.conditional{stroke-dasharray:5 5}
.step-number{font-size:10px;font-weight:700;fill:var(--badge-ink)}
@media(prefers-color-scheme:dark){:root{--ink:#e2ecf8;--muted:#afc2d9;--blue:#77b7f0;--teal:#63cdae;--purple:#baa3ed;--amber:#edb46b;--rose:#f390a7;--badge-ink:#112235}}
@media print{:root{--ink:#213951;--muted:#49617a;--blue:#2875b8;--teal:#17846b;--purple:#7960b2;--amber:#9d5b12;--rose:#c04a65;--badge-ink:#fff}}"""

DATABASE_ICON = (
    '<symbol id="icon-database" viewBox="0 0 24 24">'
    '<path class="glyph" d="M4 6c0-4 16-4 16 0s-16 4-16 0Z'
    'm0 0v12c0 4 16 4 16 0V6M4 12c0 4 16 4 16 0"/></symbol>'
)


def arrow_marker(color: str) -> str:
    """Return a small filled directional marker using a declared theme color.

    Args:
        color: One of the diagram's semantic color names.

    Returns:
        Self-contained marker markup with a stable color-qualified identifier.

    Raises:
        ValueError: The requested color is outside the diagram palette.
    """
    if color not in {"blue", "teal", "purple", "amber", "rose"}:
        raise ValueError(f"Unknown diagram color: {color}")
    return (
        f'<marker id="arrow-{color}" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
        f'<path d="M1 1 9 5 1 9 3 5Z" fill="var(--{color})"/></marker>'
    )


def definitions(symbols: str = DATABASE_ICON) -> str:
    """Embed the authoritative theme and self-contained vector definitions.

    Args:
        symbols: Trusted repository-owned symbol markup needed by this diagram.

    Returns:
        SVG definitions with no external font, image or stylesheet dependencies.
    """
    return (
        f"<defs>\n<style>{escape(STYLE, quote=False)}</style>\n"
        + "\n".join(arrow_marker(color) for color in ("blue", "teal", "purple", "amber", "rose"))
        + "\n"
        + symbols
        + "\n</defs>"
    )
