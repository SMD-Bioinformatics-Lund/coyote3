"""Endpoint builders for Flask -> API route calls."""

from __future__ import annotations

from typing import Any

_API_V1_PREFIX = "/api/v1"


def _normalize(part: Any) -> str:
    return str(part).strip("/")


def v1(*parts: Any) -> str:
    normalized = [_normalize(part) for part in parts if part is not None and str(part) != ""]
    if not normalized:
        return _API_V1_PREFIX
    return f"{_API_V1_PREFIX}/{'/'.join(normalized)}"


def auth(*parts: Any) -> str:
    return v1("auth", *parts)


def admin(*parts: Any) -> str:
    return v1("admin", *parts)


def common(*parts: Any) -> str:
    return v1("common", *parts)


def coverage(*parts: Any) -> str:
    return v1("coverage", *parts)


def dashboard(*parts: Any) -> str:
    return v1("dashboard", *parts)


def dna_sample(sample_id: str, *parts: Any) -> str:
    return v1("dna", "samples", sample_id, *parts)


def home(*parts: Any) -> str:
    return v1("home", *parts)


def home_sample(sample_id: str, *parts: Any) -> str:
    return v1("home", "samples", sample_id, *parts)


def internal(*parts: Any) -> str:
    return v1("internal", *parts)


def public(*parts: Any) -> str:
    return v1("public", *parts)


def rna_sample(sample_id: str, *parts: Any) -> str:
    return v1("rna", "samples", sample_id, *parts)


def sample(sample_id: str, *parts: Any) -> str:
    return v1("samples", sample_id, *parts)
