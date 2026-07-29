"""Pure reporting helpers shared by domain workflows."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIER_NAME: dict[int, str] = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}

TIER_SHORT_DESC: dict[int, str] = {
    0: "None",
    1: "Stark klinisk signifikans",
    2: "Potentiell klinisk signifikans",
    3: "Oklar klinisk signifikans",
    4: "Benign/sannolikt benign",
}

TIER_DESC: dict[int, str] = {
    0: "None",
    1: "Variant av stark klinisk signifikans",
    2: "Variant av potentiell klinisk signifikans",
    3: "Variant av oklar klinisk signifikans",
    4: "Variant bedömd som benign eller sannolikt benign",
}

VARIANT_CLASS_TRANSLATION: dict[str, str] = {
    "missense_variant": "missense",
    "stop_gained": "stop gained",
    "frameshift_variant": "frameshift",
    "synonymous_variant": "synonymous",
    "frameshift_deletion": "frameshift del",
    "inframe_insertion": "in-frame ins",
    "inframe_deletion": "in-frame del",
    "coding_sequence_variant": "kodande variant",
    "feature_elongation": "feature elongation",
    "INS": "insertion",
    "DEL": "deletion",
}


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def nl_num(i: int, gender: str) -> Any | str:
    """Return Swedish words for small numbers used in report summaries."""
    names = [
        "noll",
        "en",
        "två",
        "tre",
        "fyra",
        "fem",
        "sex",
        "sju",
        "åtta",
        "nio",
        "tio",
        "elva",
        "tolv",
    ]
    if gender == "t":
        names[1] = "ett"
    if i <= 12:
        return names[i]
    return str(i)


def nl_join(arr: list, joiner: str) -> str:
    """Join text fragments with a natural-language conjunction."""
    if len(arr) == 1:
        return arr[0]
    if len(arr) == 2:
        return f"{arr[0]} {joiner} {arr[1]}"
    if len(arr) > 2:
        last = arr[-1]
        return f"{', '.join(arr[:-1])} {joiner} {last}"
    return ""


def get_report_header(assay: str, sample: dict, header: str) -> str:
    """Apply assay/sample-specific report header wording."""
    if assay == "myeloid" and sample.get("subpanel_id") == "hem-snabb":
        if sample.get("sample_no") == 2:
            header += ": fullständig parad analys"
        else:
            header += ": preliminär oparad analys"
    return header


def write_report(report_data: str, report_path: str) -> bool:
    """Write rendered report HTML to disk."""
    try:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(report_data)
        return True
    except OSError:
        return False


def get_base64_image(image_path: str) -> str:
    """Return a base64-encoded image payload."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_plot(fn: str, assay_config: dict | None = None) -> str | bool:
    """Return a configured plot image as base64 when available."""
    assay_config = assay_config or {}
    plot_dir = assay_config.get("REPORT", {}).get("plots_path", "")
    if plot_dir and fn:
        image_path = os.path.join(plot_dir, f"{fn}")
        if os.path.exists(image_path):
            return get_base64_image(image_path)
    return False
