"""Endpoint builders for Flask -> API route calls."""

from __future__ import annotations

from typing import Any

_API_V1_PREFIX = "/api/v1"


def _normalize(part: Any) -> str:
    """Handle  normalize.

    Args:
            part: Part.

    Returns:
            The  normalize result.
    """
    return str(part).strip("/")


def v1(*parts: Any) -> str:
    """Build an API v1 path from raw segments.

    Args:
        *parts: Path segments to append under ``/api/v1``.

    Returns:
        A normalized API path string.
    """
    normalized = [_normalize(part) for part in parts if part is not None and str(part) != ""]
    if not normalized:
        return _API_V1_PREFIX
    return f"{_API_V1_PREFIX}/{'/'.join(normalized)}"


def auth(*parts: Any) -> str:
    """Build an authentication endpoint path.

    Args:
        *parts: Path segments under the authentication route family.

    Returns:
        A normalized authentication API path.
    """
    return v1("auth", *parts)


def admin(*parts: Any) -> str:
    """Build a governance or resource-management endpoint path.

    Args:
        *parts: Path segments describing the target governance or resource route.

    Returns:
        A normalized management API path.
    """
    normalized = tuple(_normalize(part) for part in parts if part is not None and str(part) != "")
    if not normalized:
        return v1("resources")
    head, *tail = normalized
    if head in {"users", "roles", "permissions"}:
        return v1(head, *tail)
    if head in {"asp", "aspc", "genelists", "samples", "schemas"}:
        return v1("resources", head, *tail)
    return v1("resources", head, *tail)


def common(*parts: Any) -> str:
    """Build a common-domain endpoint path.

    Args:
        *parts: Path segments under the common route family.

    Returns:
        A normalized API path.
    """
    return v1("common", *parts)


def coverage(*parts: Any) -> str:
    """Build a coverage endpoint path.

    Args:
        *parts: Path segments under the coverage route family.

    Returns:
        A normalized API path.
    """
    return v1("coverage", *parts)


def dashboard(*parts: Any) -> str:
    """Build a dashboard endpoint path.

    Args:
        *parts: Path segments under the dashboard route family.

    Returns:
        A normalized API path.
    """
    return v1("dashboard", *parts)


def dna_sample(sample_id: str, *parts: Any) -> str:
    """Build a DNA sample-centric endpoint path.

    Args:
        sample_id: Sample identifier.
        *parts: Domain-specific segments under the sample route.

    Returns:
        A normalized sample-centric API path.
    """
    translated = _translate_sample_parts(parts, omics="dna")
    return v1("samples", sample_id, *translated)


def home(*parts: Any) -> str:
    """Build a sample-list endpoint path for UI home/sample flows.

    Args:
        *parts: Path segments describing the sample-list route.

    Returns:
        A normalized sample-centric API path.
    """
    normalized = tuple(_normalize(part) for part in parts if part is not None and str(part) != "")
    match normalized:
        case ("samples",):
            return v1("samples")
        case _:
            return v1("samples", *normalized)


def home_sample(sample_id: str, *parts: Any) -> str:
    """Build a sample-context endpoint path for UI home/sample flows.

    Args:
        sample_id: Sample identifier.
        *parts: Route segments describing the target sample context.

    Returns:
        A normalized sample-centric API path.
    """
    normalized = tuple(_normalize(part) for part in parts if part is not None and str(part) != "")
    match normalized:
        case ("isgls",):
            return v1("samples", sample_id, "genelists")
        case ("effective_genes", "all"):
            return v1("samples", sample_id, "effective-genes")
        case ("edit_context",):
            return v1("samples", sample_id, "edit-context")
        case ("genes", "apply-isgl"):
            return v1("samples", sample_id, "genelists", "selection")
        case ("adhoc_genes", "save"):
            return v1("samples", sample_id, "adhoc-genes")
        case ("adhoc_genes", "clear"):
            return v1("samples", sample_id, "adhoc-genes")
        case ("reports", report_id, "context"):
            return v1("samples", sample_id, "reports", report_id, "context")
        case ("context",):
            return v1("samples", sample_id, "edit-context")
        case _:
            return v1("samples", sample_id, *normalized)


def internal(*parts: Any) -> str:
    """Build an internal support endpoint path.

    Args:
        *parts: Path segments under the internal route family.

    Returns:
        A normalized API path.
    """
    return v1("internal", *parts)


def public(*parts: Any) -> str:
    """Build a public endpoint path.

    Args:
        *parts: Path segments under the public route family.

    Returns:
        A normalized API path.
    """
    return v1("public", *parts)


def rna_sample(sample_id: str, *parts: Any) -> str:
    """Build an RNA sample-centric endpoint path.

    Args:
        sample_id: Sample identifier.
        *parts: Domain-specific segments under the sample route.

    Returns:
        A normalized sample-centric API path.
    """
    translated = _translate_sample_parts(parts, omics="rna")
    return v1("samples", sample_id, *translated)


def sample(sample_id: str, *parts: Any) -> str:
    """Build a generic sample-centric endpoint path.

    Args:
        sample_id: Sample identifier.
        *parts: Additional path segments under the sample route.

    Returns:
        A normalized sample-centric API path.
    """
    return v1("samples", sample_id, *parts)


def _translate_sample_parts(parts: tuple[Any, ...], *, omics: str) -> tuple[Any, ...]:
    """Handle  translate sample parts.

    Args:
            parts: Parts.
            omics: Omics. Keyword-only argument.

    Returns:
            The  translate sample parts result.
    """
    normalized = tuple(_normalize(part) for part in parts if part is not None and str(part) != "")
    if not normalized:
        return normalized

    if omics == "dna":
        match normalized:
            case ("variants",):
                return ("small-variants",)
            case ("small_variants",):
                return ("small-variants",)
            case ("variants", "tier"):
                return ("classifications", "tier")
            case ("small_variants", "tier"):
                return ("classifications", "tier")
            case ("variants", "flags", flag):
                return ("small-variants", "flags", flag)
            case ("small_variants", "flags", flag):
                return ("small-variants", "flags", flag)
            case ("variants", var_id, *rest):
                return ("small-variants", var_id, *rest)
            case ("small_variants", var_id, *rest):
                return ("small-variants", var_id, *rest)
            case ("classifications", *rest):
                return ("classifications", *rest)
            case ("annotations", *rest):
                return ("annotations", *rest)
            case ("biomarkers",):
                return ("biomarkers",)
            case ("plot_context",):
                return ("small-variants", "plot-context")
            case ("reports", *rest):
                return ("reports", "dna", *rest)
            case _:
                return normalized

    if omics == "rna":
        match normalized:
            case ("fusions", "flags", flag):
                return ("fusions", "flags", flag)
            case ("reports", *rest):
                return ("reports", "rna", *rest)
            case _:
                return normalized

    return normalized
