"""Hard architecture guardrails for API package boundaries."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

IMPORT_APP_PATTERN = re.compile(r"^\s*(from|import)\s+coyote_api\.app\b")
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
    parts = path.parts
    module_path = Path(*parts[parts.index("src") + 1 :]) if "src" in parts else path
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
        for path in _python_files(Path("core/src/coyote"))
        for line, module in _imported_modules(path)
        if module == "coyote_api" or module.startswith("coyote_api.")
    ]
    assert not offenders, "Library imports API application:\n" + "\n".join(offenders)


def test_installable_library_has_no_database_or_server_framework_imports() -> None:
    """Persistence codecs and database/framework implementations belong to consuming hosts."""
    forbidden = {
        "bson",
        "pymongo",
        "motor",
        "fastapi",
        "starlette",
        "celery",
        "redis",
        "coyote_mongo",
    }
    offenders = [
        f"{path}:{line}: {module}"
        for path in _python_files(Path("core/src/coyote"))
        for line, module in _imported_modules(path)
        if module.split(".")[0] in forbidden
    ]
    assert not offenders, "Runtime dependencies in the library:\n" + "\n".join(offenders)


def test_library_excludes_deployment_content_and_product_pages() -> None:
    """Host installation data and product-page presentation cannot return to the SDK."""
    library = Path("core/src/coyote")
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


def test_core_server_and_client_have_independent_distributions() -> None:
    """The server bundles both host layers; core and client remain independent wheels."""
    library = tomllib.loads(Path("core/pyproject.toml").read_text())
    discovery = library["tool"]["setuptools"]["packages"]["find"]
    assert discovery["where"] == ["src"]
    assert discovery["include"] == ["coyote", "coyote.*"]
    assert library["project"]["name"] == "coyote-core"
    assert "api" not in library["project"]["optional-dependencies"]
    server = tomllib.loads(Path("pyproject.toml").read_text())
    assert server["project"]["name"] == "coyote-server"
    assert f"coyote-core=={library['project']['version']}" in server["project"]["dependencies"]
    assert server["tool"]["setuptools"]["package-dir"] == {
        "": ".",
        "coyote_api": "api/src/coyote_api",
        "coyote_mongo": "adapters/mongo/src/coyote_mongo",
    }
    for component in ("api", "adapters/mongo"):
        settings = tomllib.loads(Path(component, "pyproject.toml").read_text())
        assert "project" not in settings
        assert "build-system" not in settings
        assert "pytest" in settings["tool"]
    assert server["project"]["scripts"]["coyote4-api"] == "coyote_api.cli:main"
    client = tomllib.loads(Path("clients/python/pyproject.toml").read_text())
    assert client["project"]["name"] == "coyote-pyclient"
    assert not any(
        dependency.lower().startswith(("coyote-core", "coyote-server"))
        for dependency in client["project"]["dependencies"]
    )


def test_mongo_adapter_has_no_application_host_imports() -> None:
    """The adapter remains independent of API imports within the server distribution."""
    offenders = [
        f"{path}:{line}: {module}"
        for path in _python_files(Path("adapters/mongo/src/coyote_mongo"))
        for line, module in _imported_modules(path)
        if module.split(".")[0] in {"coyote_api", "fastapi", "starlette", "coyote_pyclient"}
    ]
    assert not offenders, "Adapter imports its consumer:\n" + "\n".join(offenders)


def test_independent_packages_do_not_discover_deployment_environment() -> None:
    """Only the consuming host loads environment settings; libraries accept explicit inputs."""
    offenders = []
    for directory in (
        "core/src/coyote",
        "adapters/mongo/src/coyote_mongo",
        "clients/python/src/coyote_pyclient",
    ):
        for path in _python_files(Path(directory)):
            tree = ast.parse(path.read_text())
            os_names = {"os"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    os_names.update(
                        alias.asname or alias.name for alias in node.names if alias.name == "os"
                    )
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "os"
                    and any(alias.name in {"environ", "getenv"} for alias in node.names)
                ):
                    offenders.append(f"{path}:{node.lineno}: environment import")
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in os_names
                    and node.attr in {"environ", "getenv"}
                ):
                    offenders.append(f"{path}:{node.lineno}: environment discovery")
            for line, module in _imported_modules(path):
                if module.split(".")[0] in {"dotenv", "pydantic_settings"}:
                    offenders.append(f"{path}:{line}: {module}")
    assert not offenders, "Packages discover host configuration:\n" + "\n".join(offenders)


def test_http_workflows_use_the_application_sdk() -> None:
    """Prevent routes from introducing a second use-case or repository calling convention."""
    allowed_helpers = {
        "coyote.application.common.analysis_query",
        "coyote.application.common.change_payload",
    }
    offenders = []
    for path in _python_files(Path("api/src/coyote_api/interfaces/http")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            module = node.module
            if module.startswith("coyote_api.app.deps.repositories"):
                offenders.append(f"{path}:{node.lineno}: repository dependency")
            if module == "coyote_api.app.deps.services" and any(
                alias.name != "get_audit_service" for alias in node.names
            ):
                offenders.append(f"{path}:{node.lineno}: internal implementation dependency")
            if (
                module.startswith("coyote.application.")
                and not module.startswith("coyote.application.operations")
                and module not in allowed_helpers
            ):
                offenders.append(f"{path}:{node.lineno}: {module}")
    assert not offenders, "HTTP bypasses the application SDK:\n" + "\n".join(offenders)


def test_maintenance_tasks_delegate_workflows_to_the_application_sdk() -> None:
    """Task adapters own scheduling and process locks; application operations own workflows."""
    imports = _imported_modules(Path("api/src/coyote_api/tasks/maintenance.py"))
    forbidden = (
        "coyote_api.app.deps.services",
        "coyote_api.app.deps.repositories",
        "coyote_api.infra",
    )
    offenders = [
        module
        for _, module in imports
        if (
            any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
            or (
                module.startswith("coyote.application.")
                and not module.startswith("coyote.application.operations")
            )
        )
    ]
    assert not offenders, "Maintenance task bypasses the application SDK: " + ", ".join(offenders)


def test_core_has_no_runtime_adapter_or_transport_dependencies() -> None:
    """Core accepts ports and explicit inputs; composition supplies runtime adapters."""
    forbidden = (
        "coyote_api.app",
        "coyote_api.interfaces",
        "coyote_api.infra",
        "coyote_api.security",
        "coyote_pyclient",
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
    for root in (Path("core/src/coyote/domain"), Path("core/src/coyote/application")):
        for path in _python_files(root):
            blocked = forbidden + (
                (
                    "coyote.application",
                    "coyote.contracts",
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
    for root in (Path("core/src/coyote/domain"), Path("core/src/coyote/application")):
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
        _python_files(Path("api/src/coyote_api"))
        + _python_files(Path("core/src/coyote"))
        + _python_files(Path("clients/python/src/coyote_pyclient"))
    ):
        client = path.is_relative_to("clients/python/src/coyote_pyclient")
        for line, module in _imported_modules(path):
            if client:
                invalid = module.split(".")[0] in {"coyote_api", "coyote", "coyote_mongo"} and not (
                    module == "coyote_pyclient" or module.startswith("coyote_pyclient.")
                )
            else:
                invalid = module == "coyote_pyclient" or module.startswith("coyote_pyclient.")
            if invalid:
                offenders.append(f"{path}:{line}: {module}")
    assert not offenders, "SDK/server boundary violations:\n" + "\n".join(offenders)


def test_infra_does_not_import_app_layer() -> None:
    """Infrastructure must not depend upward on app composition/runtime modules."""
    offenders: list[str] = []
    for path in _python_files(Path("api/src/coyote_api/infra")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if IMPORT_APP_PATTERN.search(line):
                offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "coyote_api.infra must not import coyote_api.app:\n" + "\n".join(
        offenders
    )


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
    for root in (
        Path("core/src/coyote/application/audit"),
        Path("core/src/coyote/application/ingest"),
    ):
        for path in _python_files(root):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden:
                        offenders.append(f"{path}:{node.lineno}:{node.func.attr}")
    assert not offenders, "Use repository operations:\n" + "\n".join(offenders)


def test_domain_and_application_do_not_import_app_layer() -> None:
    """Domain/application code must not depend on app composition/runtime modules."""
    offenders: list[str] = []
    for root in (Path("core/src/coyote/domain"), Path("core/src/coyote/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if IMPORT_APP_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, (
        "coyote.domain/coyote.application must not import coyote_api.app:\n" + "\n".join(offenders)
    )


def test_domain_and_application_do_not_import_http_frameworks() -> None:
    """Domain/application code must not depend on FastAPI/Starlette."""
    offenders: list[str] = []
    for root in (Path("core/src/coyote/domain"), Path("core/src/coyote/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if HTTP_FRAMEWORK_IMPORT_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, (
        "coyote.domain/coyote.application must not import HTTP frameworks:\n" + "\n".join(offenders)
    )


def test_persistence_dependency_names_use_repository_terms() -> None:
    """Persistence dependencies should not use handler naming."""
    offenders: list[str] = []
    for root in (Path("api/src/coyote_api"), Path("docs")):
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
        Path("api/src/coyote_api/interfaces"),
        Path("core/src/coyote/application"),
        Path("core/src/coyote/domain"),
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
        Path("api/src/coyote_api/interfaces"),
        Path("core/src/coyote/application"),
        Path("core/src/coyote/domain"),
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
    for path in _python_files(Path("api/src/coyote_api/interfaces/http")):
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
        Path("core/src/coyote/contracts"),
        Path("core/src/coyote/domain"),
        Path("core/src/coyote/application"),
    ):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "from dataclasses import" in line or "@dataclass" in line:
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Use Pydantic models for API/domain contracts:\n" + "\n".join(offenders)
