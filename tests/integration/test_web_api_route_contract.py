"""Contract tests for Flask->API endpoint wiring."""

from __future__ import annotations

import ast
from pathlib import Path

from api.main import app as api_app
from coyote.services.api_client import endpoints as api_endpoints


def _api_route_templates() -> set[str]:
    """Handle  api route templates.

    Returns:
            The  api route templates result.
    """
    templates: set[str] = set()
    for route in api_app.routes:
        path = getattr(route, "path", "")
        if isinstance(path, str) and path.startswith("/api/v1/"):
            templates.add(path)
    return templates


def _matches_template(path: str, template: str) -> bool:
    """Handle  matches template.

    Args:
            path: Path.
            template: Template.

    Returns:
            The  matches template result.
    """
    path_parts = [part for part in path.strip("/").split("/") if part]
    template_parts = [part for part in template.strip("/").split("/") if part]
    if len(path_parts) != len(template_parts):
        return False
    for part, template_part in zip(path_parts, template_parts, strict=True):
        if template_part.startswith("{") and template_part.endswith("}"):
            continue
        if part != template_part:
            return False
    return True


def _literal_or_placeholder(node: ast.AST, idx: int) -> object:
    """Handle  literal or placeholder.

    Args:
            node: Node.
            idx: Idx.

    Returns:
            The  literal or placeholder result.
    """
    if isinstance(node, ast.Constant):
        return node.value
    return f"arg{idx}"


def _collect_endpoint_paths_from_web_layer() -> list[tuple[str, int, str, str]]:
    """Handle  collect endpoint paths from web layer.

    Returns:
            The  collect endpoint paths from web layer result.
    """
    calls: list[tuple[str, int, str, str]] = []
    for py_file in sorted(Path("coyote").rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "api_endpoints":
                continue

            endpoint_builder = node.func.attr
            builder = getattr(api_endpoints, endpoint_builder, None)
            if not callable(builder):
                continue

            args = [_literal_or_placeholder(arg, idx) for idx, arg in enumerate(node.args)]
            try:
                path = str(builder(*args))
            except Exception:
                continue
            calls.append((py_file.as_posix(), node.lineno, endpoint_builder, path))
    return calls


def test_web_api_endpoint_builders_match_existing_api_routes():
    """Handle test web api endpoint builders match existing api routes.

    Returns:
        The function result.
    """
    templates = _api_route_templates()
    assert templates, "No API route templates discovered"

    missing: list[str] = []
    for source, line, builder_name, path in _collect_endpoint_paths_from_web_layer():
        if not path.startswith("/api/v1/"):
            missing.append(
                f"{source}:{line} via api_endpoints.{builder_name} -> {path} (bad prefix)"
            )
            continue
        if "/report/arg" in path:
            # Dynamic action in reports helper is asserted explicitly in
            # `test_report_action_endpoints_exist`.
            continue
        if not any(_matches_template(path, template) for template in templates):
            missing.append(f"{source}:{line} via api_endpoints.{builder_name} -> {path}")

    assert not missing, "Web layer endpoint builder calls do not match API routes:\n" + "\n".join(
        sorted(missing)
    )


def test_report_action_endpoints_exist():
    """Handle test report action endpoints exist.

    Returns:
        The function result.
    """
    templates = _api_route_templates()
    explicit_paths = {
        api_endpoints.dna_sample("S1", "reports", "preview"),
        api_endpoints.dna_sample("S1", "reports"),
        api_endpoints.rna_sample("S1", "reports", "preview"),
        api_endpoints.rna_sample("S1", "reports"),
    }
    missing = [
        path
        for path in sorted(explicit_paths)
        if not any(_matches_template(path, t) for t in templates)
    ]
    assert not missing, "Missing report API route template(s):\n" + "\n".join(missing)
