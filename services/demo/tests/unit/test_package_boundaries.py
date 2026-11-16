"""Optional host integrations cannot become dependencies of the base demo library."""

import ast
from pathlib import Path

import coyote_demo


def test_database_and_host_imports_stay_in_explicit_integrations():
    """Only host/API/worker adapters may import optional server dependencies."""
    package = Path(coyote_demo.__file__).parent
    host_dependencies = {"coyote_api", "coyote_mongo", "coyote_relay", "fastapi", "starlette"}
    violations = []
    for source in package.rglob("*.py"):
        relative = source.relative_to(package)
        integration = relative.parts[0] == "api" or relative.name in {"host.py", "runtime.py"}
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            else:
                continue
            for imported in imports:
                dependency = imported.split(".")[0]
                if dependency in {"pymongo", "mongomock"} or (
                    dependency in host_dependencies and not integration
                ):
                    violations.append(f"{relative}:{node.lineno}: {imported}")
    assert not violations, "Demo package crosses an integration boundary:\n" + "\n".join(violations)
