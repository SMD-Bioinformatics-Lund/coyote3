"""Hard architecture guardrails for API package boundaries."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

IMPORT_APP_PATTERN = re.compile(r"^\s*(from|import)\s+api\.app\b")
HTTP_FRAMEWORK_IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+(fastapi|starlette)\b")
PERSISTENCE_NAMES = (
    "annotation",
    "assay_configuration",
    "assay_panel",
    "bam_record",
    "biomarker",
    "blacklist",
    "brca",
    "civic",
    "copy_number_variant",
    "cosmic",
    "coverage",
    "expression",
    "fusion",
    "grouped_coverage",
    "hgnc",
    "iarc_tp53",
    "gene_list",
    "oncokb",
    "permissions",
    "reported_variant",
    "rna_classification",
    "rna_expression",
    "rna_quality",
    "roles",
    "sample",
    "translocation",
    "user",
    "variant",
    "vep_metadata",
)
PERSISTENCE_HANDLER_NAME_PATTERN = re.compile(
    r"store\.(?:" + "|".join(PERSISTENCE_NAMES) + r")_handler\b|"
    r"\bget_(?:user|roles|permissions|assay_panel|sample|gene_list)_handler\b|"
    r"\b(?:" + "|".join(PERSISTENCE_NAMES) + r")_handler\s*="
)
PYMONGO_RESULT_PATTERN = re.compile(
    r"\bpymongo\.results\b|"
    r"\b(from\s+pymongo\.results\s+import|"
    r"InsertOneResult|InsertManyResult|UpdateResult|DeleteResult|BulkWriteResult)\b"
)


def _python_files(root: Path) -> list[Path]:
    """Find Python sources and fail if a moved boundary no longer exists."""
    assert root.is_dir(), f"Missing architecture boundary: {root}"
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """Resolve imports, including local imports and relative from-import aliases."""
    imports = []
    module_path = path.relative_to("src") if path.is_relative_to("src") else path
    package = module_path.with_suffix("").parts[:-1]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = ".".join(package[: len(package) - node.level + 1]) if node.level else ""
            module = ".".join(part for part in (prefix, node.module) if part)
            imports.append((node.lineno, module))
            imports.extend((node.lineno, f"{module}.{alias.name}") for alias in node.names)
    return imports


def test_installable_library_never_imports_the_api_application() -> None:
    """Every library module must be importable without the source-deployed API."""
    offenders = [
        f"{path}:{line}: {module}"
        for path in _python_files(Path("src/coyote3"))
        for line, module in _imported_modules(path)
        if module == "api" or module.startswith("api.")
    ]
    assert not offenders, "Library imports API application:\n" + "\n".join(offenders)


def test_installable_library_has_no_database_or_server_framework_imports() -> None:
    """Persistence codecs and database/framework implementations belong to consuming hosts."""
    forbidden = {"bson", "pymongo", "motor", "fastapi", "starlette", "celery", "redis"}
    offenders = [
        f"{path}:{line}: {module}"
        for path in _python_files(Path("src/coyote3"))
        for line, module in _imported_modules(path)
        if module.split(".")[0] in forbidden
    ]
    assert not offenders, "Runtime dependencies in the library:\n" + "\n".join(offenders)


def test_library_excludes_deployment_content_and_product_pages() -> None:
    """Host installation data and product-page presentation cannot return to the SDK."""
    library = Path("src/coyote3")
    for relative in (
        "config/bootstrap",
        "config/assets",
        "config/application_metadata.py",
        "config/loaders/contact.py",
        "config/clinical_query_seed.toml",
        "application/provisioning",
        "application/resources/release_compilation.py",
        "contracts/demo_installation.py",
        "contracts/deployment_data.py",
        "contracts/http.py",
        "contracts/system.py",
        "contracts/internal.py",
        "contracts/client_errors.py",
    ):
        target = library / relative
        assert not target.is_file(), relative
        assert not any(target.rglob("*.py")), relative
        assert not any(target.rglob("*.toml")), relative


def test_server_and_core_share_a_distribution_with_optional_api_dependencies() -> None:
    """API modules ship with core; the external HTTP client has its own distribution."""
    library = tomllib.loads(Path("pyproject.toml").read_text())
    discovery = library["tool"]["setuptools"]["packages"]["find"]
    assert discovery["where"] == ["src", "."]
    assert discovery["include"] == ["coyote3*", "api", "api.*"]
    assert library["project"]["optional-dependencies"]["api"]
    assert library["project"]["scripts"]["coyote3-api"] == "api.cli:main"
    api = tomllib.loads(Path("api/pyproject.toml").read_text())
    assert "project" not in api and "build-system" not in api
    assert api["tool"]["coyote3"]["asgi"] == "api.app.main:app"
    client = tomllib.loads(Path("clients/python/pyproject.toml").read_text())
    assert client["project"]["name"] == "coyote3-client"
    assert not any(
        "coyote3" in dependency.lower() for dependency in client["project"]["dependencies"]
    )


def test_http_workflows_use_the_application_sdk() -> None:
    """Prevent routes from introducing a second use-case or repository calling convention."""
    allowed_helpers = {
        "coyote3.application.common.analysis_query",
        "coyote3.application.common.change_payload",
    }
    offenders = []
    for path in _python_files(Path("api/interfaces/http")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            module = node.module
            if module.startswith("api.app.deps.repositories"):
                offenders.append(f"{path}:{node.lineno}: repository dependency")
            if module == "api.app.deps.services" and any(
                alias.name != "get_audit_service" for alias in node.names
            ):
                offenders.append(f"{path}:{node.lineno}: internal implementation dependency")
            if (
                module.startswith("coyote3.application.")
                and not module.startswith("coyote3.application.operations")
                and module not in allowed_helpers
            ):
                offenders.append(f"{path}:{node.lineno}: {module}")
    assert not offenders, "HTTP bypasses the application SDK:\n" + "\n".join(offenders)


def test_maintenance_tasks_delegate_workflows_to_the_application_sdk() -> None:
    """Task adapters own scheduling and process locks; application operations own workflows."""
    imports = _imported_modules(Path("api/tasks/maintenance.py"))
    forbidden = ("api.app.deps.services", "api.app.deps.repositories", "api.infra")
    offenders = [
        module
        for _, module in imports
        if (
            any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
            or (
                module.startswith("coyote3.application.")
                and not module.startswith("coyote3.application.operations")
            )
        )
    ]
    assert not offenders, "Maintenance task bypasses the application SDK: " + ", ".join(offenders)


def test_core_has_no_runtime_adapter_or_transport_dependencies() -> None:
    """Core accepts ports and explicit inputs; composition supplies runtime adapters."""
    forbidden = (
        "api.app",
        "api.interfaces",
        "api.infra",
        "api.security",
        "coyote3_client",
        "fastapi",
        "starlette",
        "pymongo",
        "bson",
        "celery",
        "redis",
        "prometheus_client",
        "httpx",
        "requests",
        "werkzeug",
    )
    offenders = []
    for root in (Path("src/coyote3/domain"), Path("src/coyote3/application")):
        for path in _python_files(root):
            blocked = forbidden + (
                (
                    "coyote3.application",
                    "coyote3.contracts",
                    "os",
                    "pathlib",
                    "tempfile",
                    "shutil",
                    "subprocess",
                    "socket",
                )
                if root.name == "domain"
                else ()
            )
            for line, module in _imported_modules(path):
                if any(module == name or module.startswith(name + ".") for name in blocked):
                    offenders.append(f"{path}:{line}: {module}")
    assert not offenders, "Core imports runtime or transport implementations:\n" + "\n".join(
        offenders
    )


def test_core_does_not_construct_executable_database_predicates() -> None:
    """Clinical core constructs selections; storage adapters emit MongoDB operators."""
    offenders = []
    for root in (Path("src/coyote3/domain"), Path("src/coyote3/application")):
        for path in _python_files(root):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                keys = (
                    node.keys
                    if isinstance(node, ast.Dict)
                    else ([node.slice] if isinstance(node, ast.Subscript) else [])
                )
                for key in keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value.startswith("$"):
                            offenders.append(f"{path}:{key.lineno}: {key.value}")
    assert not offenders, "Executable storage syntax in core:\n" + "\n".join(offenders)


def test_sdk_and_server_are_independent_consumers() -> None:
    """The SDK depends on its own HTTP models; the server never calls its remote SDK."""
    offenders = []
    for path in (
        _python_files(Path("api"))
        + _python_files(Path("src/coyote3"))
        + _python_files(Path("clients/python/src/coyote3_client"))
    ):
        client = path.is_relative_to("clients/python/src/coyote3_client")
        for line, module in _imported_modules(path):
            if client:
                invalid = module.startswith(("api.", "coyote3.")) and not (
                    module == "coyote3_client" or module.startswith("coyote3_client.")
                )
            else:
                invalid = module == "coyote3_client" or module.startswith("coyote3_client.")
            if invalid:
                offenders.append(f"{path}:{line}: {module}")
    assert not offenders, "SDK/server boundary violations:\n" + "\n".join(offenders)


def test_infra_does_not_import_app_layer() -> None:
    """Infrastructure must not depend upward on app composition/runtime modules."""
    offenders: list[str] = []
    for path in _python_files(Path("api/infra")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if IMPORT_APP_PATTERN.search(line):
                offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "api.infra must not import api.app:\n" + "\n".join(offenders)


def test_audit_and_ingest_use_repository_operations_not_mongo_handles() -> None:
    """Prevent storage handles and driver calls leaking back into audited workflows."""
    forbidden = {
        "find",
        "find_one",
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "delete_many",
        "replace_one",
        "count_documents",
        "estimated_document_count",
        "get_collection",
        "sample_collection",
        "mongo_client",
        "_collection",
    }
    offenders = []
    for root in (Path("src/coyote3/application/audit"), Path("src/coyote3/application/ingest")):
        for path in _python_files(root):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden:
                        offenders.append(f"{path}:{node.lineno}:{node.func.attr}")
    assert not offenders, "Use repository operations:\n" + "\n".join(offenders)


def test_domain_and_application_do_not_import_app_layer() -> None:
    """Domain/application code must not depend on app composition/runtime modules."""
    offenders: list[str] = []
    for root in (Path("src/coyote3/domain"), Path("src/coyote3/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if IMPORT_APP_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, (
        "coyote3.domain/coyote3.application must not import api.app:\n" + "\n".join(offenders)
    )


def test_domain_and_application_do_not_import_http_frameworks() -> None:
    """Domain/application code must not depend on FastAPI/Starlette."""
    offenders: list[str] = []
    for root in (Path("src/coyote3/domain"), Path("src/coyote3/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if HTTP_FRAMEWORK_IMPORT_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, (
        "coyote3.domain/coyote3.application must not import HTTP frameworks:\n"
        + "\n".join(offenders)
    )


def test_persistence_dependency_names_use_repository_terms() -> None:
    """Persistence dependencies should not use handler naming."""
    offenders: list[str] = []
    for root in (Path("api"), Path("docs")):
        files = sorted(
            path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts
        )
        for path in files:
            if path.suffix not in {".py", ".md"}:
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if PERSISTENCE_HANDLER_NAME_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Persistence dependencies must use repository naming:\n" + "\n".join(
        offenders
    )


def test_api_boundaries_do_not_expose_pymongo_result_types() -> None:
    """API and domain layers should use JSON-safe contracts, not driver result types."""
    offenders: list[str] = []
    for root in (
        Path("api/interfaces"),
        Path("src/coyote3/application"),
        Path("src/coyote3/domain"),
    ):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if PYMONGO_RESULT_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "API/domain layers must not expose PyMongo result types:\n" + "\n".join(
        offenders
    )


def test_domain_and_interface_layers_do_not_reach_into_repository_collections() -> None:
    """Domain/interface code should ask repositories for operations, not raw collections."""
    offenders: list[str] = []
    for root in (
        Path("api/interfaces"),
        Path("src/coyote3/application"),
        Path("src/coyote3/domain"),
    ):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if ".get_collection()" in line:
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Domain/interface layers must not call get_collection():\n" + "\n".join(
        offenders
    )


def test_http_routes_declare_response_contracts() -> None:
    """Every documented route must declare a response model or a non-JSON response class."""
    offenders: list[str] = []
    for path in _python_files(Path("api/interfaces/http")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                    and func.attr in {"get", "post", "put", "patch", "delete"}
                ):
                    continue
                keywords = {keyword.arg for keyword in decorator.keywords if keyword.arg}
                if "include_in_schema" in keywords:
                    continue
                if "response_model" not in keywords and "response_class" not in keywords:
                    offenders.append(f"{path.as_posix()}:{node.lineno}: @{func.attr} {node.name}")

    assert not offenders, "HTTP routes must declare response contracts:\n" + "\n".join(offenders)


def test_contract_layers_use_pydantic_models_instead_of_dataclasses() -> None:
    """Keep request/response and domain value contracts on one modelling style."""
    offenders: list[str] = []
    for root in (
        Path("src/coyote3/contracts"),
        Path("src/coyote3/domain"),
        Path("src/coyote3/application"),
    ):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "from dataclasses import" in line or "@dataclass" in line:
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Use Pydantic models for API/domain contracts:\n" + "\n".join(offenders)
