"""JSON resource loading with actionable ingestion error messages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_ingest_json(filename: str, label: str) -> Any:
    """Read an ingest JSON resource and report its filename and failing location.

    Args:
        filename: Resolved staged file path.
        label: Human-readable analysis resource name.

    Returns:
        Decoded JSON value.

    Raises:
        ValueError: If the file is empty, malformed, or not UTF-8 text.
        OSError: If the resource cannot be read.
    """
    path = Path(filename)
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"{label} file '{path.name}' is empty; provide valid JSON output.")
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} file '{path.name}' contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}."
        ) from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} file '{path.name}' must contain UTF-8 JSON text.") from exc
