# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Format report cells and compact narrative without changing clinical content."""

import math
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from markdown import Markdown
from markdown.treeprocessors import Treeprocessor

from coyote.domain.common.reporting import TIER_NAME
from coyote.domain.dna.allele_frequency import allele_fraction
from coyote.domain.dna.cnv_metrics import copy_number_from_log2


def _copy_number(value: Any) -> str:
    """Format a finite log2-derived diploid copy estimate, or a missing-value marker.

    Args:
        value: Numeric log2 ratio. Missing, nonnumeric or overflowing values are unknown.

    Returns:
        Two-decimal copy-number estimate, or a dash for unusable input.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "-"
    try:
        estimate = copy_number_from_log2(value)
    except OverflowError:
        return "-"
    return f"{estimate:.2f}" if math.isfinite(estimate) else "-"


def _perc_no_dec(value: Any) -> str:
    """Format valid allele fractions; preserve zero and the explicit N/A marker."""
    if value == "N/A":
        return "N/A"
    fraction = allele_fraction(value)
    return f"{fraction * 100:.0f}%" if fraction is not None else "-"


def _format_tier(value: Any, include_label: bool = True) -> str:
    """Format a tier as a Roman numeral, optionally prefixed with its clinical label.

    Args:
        value: Numeric tier; unsupported numeric values display a dash.
        include_label: Include ``Tier`` for detailed wording; false gives a compact numeral.

    Returns:
        Clinical tier label or compact Roman numeral, with a dash for missing values.
    """
    try:
        tier = int(value)
        if tier not in TIER_NAME:
            return "-"
        return f"Tier {TIER_NAME[tier]}" if include_label else TIER_NAME[tier]
    except (TypeError, ValueError):
        return str(value or "-")


def _format_classification(value: Any, description: Any = None) -> str:
    """Render a known tier and optional description, or one plain missing-value hyphen.

    Args:
        value: Numeric classification tier; missing, zero and unclassified values are unknown.
        description: Optional clinical wording. Empty wording or a hyphen is omitted.

    Returns:
        A tier with a plain hyphen separator, or exactly ``-`` for an unknown tier.
    """
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return "-"
    if isinstance(value, bool) or tier not in TIER_NAME:
        return "-"
    label = f"Tier {TIER_NAME[tier]}"
    wording = str(description or "").strip()
    return f"{label} - {wording}" if wording and wording != "-" else label


def _value(value: Any) -> Any:
    """Return a JSON cell, preserving missing values, zero and false."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_value(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(str(_value(item)) for item in value)
    return str(value)


def _table(key: str, heading: str, columns: list[str], rows: list[list[Any]], **extra: Any) -> dict:
    """Build a rectangular Swedish table from explicitly selected display fields."""
    return {
        "key": key,
        "kind": "table",
        "heading": heading,
        "columns": {"sv": columns},
        "rows": [[_value(value) for value in row] for row in rows],
        **extra,
    }


def _hgvs(value: Any) -> Any:
    """Decode stored percent-encoded notation without replacing an unavailable value."""
    return unquote(value) if isinstance(value, str) else _value(value)


def _detail(key: str, title: str, fields: list[tuple[str, Any]]) -> dict:
    """Build one finding card without flattening its labels or exposing private fields."""
    fields = [(label, value) for label, value in fields if label != "Kommentar" or value]
    result = _table(key, "", [label for label, _ in fields], [[value for _, value in fields]])
    result.update(kind="details", record_titles=[title], fields_per_row=3)
    result["column_options"] = {
        str(index): {"format": "markdown", "full_width": True}
        for index, (label, _) in enumerate(fields)
        if label == "Kommentar"
    }
    return result


def _comment(row: dict, *, selected: bool = False) -> str:
    """Use the already selected assay annotation, otherwise the latest visible annotation."""
    annotations = row.get("global_annotations") or []
    if not annotations:
        return ""
    preferred = (row.get("annotations_interesting") or {}) if selected else {}
    if preferred:
        return "\n\n".join(str(item.get("text") or "") for item in preferred.values())
    return str(max(annotations, key=lambda item: item.get("time_created") or "").get("text") or "")


def _annotation(row: dict) -> dict:
    """Read the selected structural annotation, then MANE or the first annotation."""
    info = row.get("INFO") or {}
    annotations = info.get("ANN") or []
    selected = next((item for item in annotations if item.get("selected") == 1), None)
    return selected or info.get("MANE_ANN") or next(iter(annotations), {})


def _read_support(value: Any) -> str:
    """Preserve stored read-support text or format reference/alternate counts with slashes."""
    if isinstance(value, str):
        return value
    return "/".join(map(str, value)) if value is not None else "-"


class _CompactSummaryHeadings(Treeprocessor):
    """Format parsed Markdown headings without changing authored words or other blocks."""

    def run(self, root: ElementTree.Element) -> None:
        """Replace headings in the Markdown tree with body-sized bold paragraphs.

        Args:
            root: Parsed Markdown tree, modified before serialization and sanitization.
        """
        for parent in list(root.iter()):
            children = list(parent)
            for index, heading in enumerate(children):
                if heading.tag not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    continue
                heading.tag = "strong"
                heading.attrib.clear()
                following = children[index + 1] if index + 1 < len(children) else None
                position = list(parent).index(heading)
                parent.remove(heading)
                if following is not None and following.tag == "p":
                    line_break = ElementTree.Element("br")
                    line_break.tail = following.text
                    following.text = None
                    heading.tail = None
                    following.insert(0, heading)
                    following.insert(1, line_break)
                else:
                    paragraph = ElementTree.Element("p")
                    paragraph.tail = heading.tail
                    heading.tail = None
                    paragraph.append(heading)
                    parent.insert(position, paragraph)


def _summary_text(context: dict) -> str:
    """Keep reviewed summary words while displaying headings as compact bold paragraphs."""
    text = "\n\n".join(
        value
        for value in (context.get("report_scope_label"), context.get("latest_sample_comment_text"))
        if value
    )
    processor = Markdown(extensions=["extra", "nl2br"], output_format="xhtml")
    processor.preprocessors.deregister("html_block")
    processor.inlinePatterns.deregister("html")
    processor.treeprocessors.register(_CompactSummaryHeadings(processor), "summary_headings", 15)
    return processor.convert(text)


def _summary_copy_number(ratio: Any) -> str:
    """Match master's copy-number rounding while retaining unavailable/invalid values."""
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio):
        return "-"
    try:
        estimate = 2 * round(2**ratio, 2)
        return str(estimate) if math.isfinite(estimate) else "-"
    except OverflowError:
        return "-"
