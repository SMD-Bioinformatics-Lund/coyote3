"""Keep the deployment template connected to Compose and its operator reference."""

import ast
import re
from pathlib import Path

import pytest
import yaml
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy/env/example.env"
TEMPLATES = sorted((ROOT / "deploy/env").glob("example*.env"))
COMPOSE_FILES = (
    ROOT / "deploy/compose/docker-compose.yml",
    ROOT / "deploy/compose/docker-compose.mongo.yml",
    ROOT / "deploy/compose/docker-compose.loadtest.yml",
)


def _strings(value):
    """Yield strings from parsed Compose values, excluding comments."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.name)
def test_every_template_variable_has_compose_wiring(template):
    keys = set(dotenv_values(template, interpolate=False))
    wired = set()
    for path in COMPOSE_FILES:
        for value in _strings(yaml.safe_load(path.read_text())):
            wired.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", value))
    assert keys - wired == set(), "Template settings must affect the deployment"


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.name)
def test_every_template_variable_has_a_reference_table_entry(template):
    keys = set(dotenv_values(template, interpolate=False))
    reference = "\n".join(
        (ROOT / name).read_text()
        for name in ("docs/start_here/configuration.md", "docs/testing/load_testing.md")
    )
    first_cells = [line.split("|")[1] for line in reference.splitlines() if line.startswith("|")]
    documented = set(re.findall(r"`([A-Z][A-Z0-9_]*)`", "\n".join(first_cells)))
    assert keys - documented == set(), "Document the variable itself, not only a mention"


def test_template_runtime_settings_have_consumers_outside_their_declarations():
    keys = set(dotenv_values(TEMPLATE, interpolate=False))
    settings_path = ROOT / "api/config/runtime_settings.py"
    settings = ast.parse(settings_path.read_text())
    declared = {
        node.args[0].value
        for node in ast.walk(settings)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "getenv"
            or isinstance(node.func, ast.Name)
            and node.func.id == "_environment_bool"
        )
    }
    referenced = set()
    for path in (ROOT / "api").rglob("*.py"):
        if path == settings_path:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                referenced.add(node.value)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
    assert (keys & declared) - referenced == set(), "A configuration declaration is not a consumer"
