"""Package-owned suites remain usable without application-level test helpers."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "directory,forbidden",
    [
        (
            "core",
            {
                "coyote_api",
                "coyote_mongo",
                "coyote_pyclient",
                "api_test_support",
                "mongo_test_support",
                "bson",
                "pymongo",
                "fastapi",
                "starlette",
                "tests",
            },
        ),
        (
            "adapters/mongo",
            {"coyote_api", "coyote_pyclient", "api_test_support", "core_test_support", "tests"},
        ),
        ("api", {"core_test_support", "mongo_test_support", "tests"}),
        (
            "clients/python",
            {
                "coyote",
                "coyote_api",
                "coyote_mongo",
                "core_test_support",
                "api_test_support",
                "mongo_test_support",
                "tests",
            },
        ),
    ],
)
def test_package_test_dependencies_follow_the_distribution_boundary(directory, forbidden):
    """Prevent an apparently independent suite from borrowing an outer host or test tree."""
    violations = []
    for path in (ROOT / directory / "tests").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                if module.split(".", 1)[0] in forbidden:
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
    assert not violations, "\n".join(violations)
