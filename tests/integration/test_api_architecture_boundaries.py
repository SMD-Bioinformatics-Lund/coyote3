"""Hard architecture guardrails for API package boundaries."""

from __future__ import annotations

import re
import ast
from pathlib import Path


IMPORT_APP_PATTERN = re.compile(r"^\s*(from|import)\s+api\.app\b")
HTTP_FRAMEWORK_IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+(fastapi|starlette)\b")
OLD_MONGO_HANDLER_PATTERN = re.compile(
    re.escape("api.infra.mongo." + "handlers") + "|" + re.escape("infra/mongo/" + "handlers")
)
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
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_infra_does_not_import_app_layer() -> None:
    """Infrastructure must not depend upward on app composition/runtime modules."""
    offenders: list[str] = []
    for path in _python_files(Path("api/infra")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if IMPORT_APP_PATTERN.search(line):
                offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "api.infra must not import api.app:\n" + "\n".join(offenders)


def test_domain_and_application_do_not_import_app_layer() -> None:
    """Domain/application code must not depend on app composition/runtime modules."""
    offenders: list[str] = []
    for root in (Path("api/domain"), Path("api/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if IMPORT_APP_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "api.domain/api.application must not import api.app:\n" + "\n".join(
        offenders
    )


def test_domain_and_application_do_not_import_http_frameworks() -> None:
    """Domain/application code must not depend on FastAPI/Starlette."""
    offenders: list[str] = []
    for root in (Path("api/domain"), Path("api/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if HTTP_FRAMEWORK_IMPORT_PATTERN.search(line):
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "api.domain/api.application must not import HTTP frameworks:\n" + "\n".join(
        offenders
    )


def test_retired_domains_package_path_is_not_reintroduced() -> None:
    """Use api.application for use-case orchestration; the old plural package is retired."""
    offenders: list[str] = []
    retired_patterns = ("api." + "domains", "api/" + "domains")
    for root in (Path("api"), Path("tests"), Path("docs"), Path("scripts")):
        if not root.exists():
            continue
        files = sorted(
            path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts
        )
        for path in files:
            if path.suffix not in {".py", ".md", ".json", ".yml", ".yaml", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8")
            if any(pattern in text for pattern in retired_patterns):
                offenders.append(path.as_posix())

    assert not offenders, "Retired plural application package references remain:\n" + "\n".join(
        offenders
    )


def test_mongo_handlers_package_path_is_retired() -> None:
    """Mongo data access should use the repositories package path only."""
    offenders: list[str] = []
    for root in (Path("api"), Path("tests"), Path("docs"), Path("scripts")):
        if not root.exists():
            continue
        files = sorted(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
        for path in files:
            if path.suffix not in {".py", ".md", ".json", ".yml", ".yaml", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8")
            if OLD_MONGO_HANDLER_PATTERN.search(text):
                offenders.append(path.as_posix())

    assert not offenders, "Retired mongo handler package references remain:\n" + "\n".join(
        offenders
    )


def test_persistence_dependency_names_use_repository_terms() -> None:
    """Persistence dependencies should not use handler naming."""
    offenders: list[str] = []
    for root in (Path("api"), Path("docs")):
        files = sorted(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
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
    for root in (Path("api/interfaces"), Path("api/application"), Path("api/domain")):
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
    for root in (Path("api/interfaces"), Path("api/application"), Path("api/domain")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if ".get_collection()" in line:
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Domain/interface layers must not call get_collection():\n" + "\n".join(
        offenders
    )


def test_ingest_service_uses_collection_gateway_not_collection_maps() -> None:
    """Internal ingest orchestration should not carry ad hoc raw collection maps."""
    path = Path("api/application/ingest/service.py")
    offenders: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if "self.collections" in stripped or "service.collections" in stripped:
            offenders.append(f"{path.as_posix()}:{line_no}: {stripped}")

    assert not offenders, "Ingest service must use IngestCollectionGateway:\n" + "\n".join(
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
                    offenders.append(
                        f"{path.as_posix()}:{node.lineno}: @{func.attr} {node.name}"
                    )

    assert not offenders, "HTTP routes must declare response contracts:\n" + "\n".join(offenders)


def test_contract_layers_use_pydantic_models_instead_of_dataclasses() -> None:
    """Keep request/response and domain value contracts on one modelling style."""
    offenders: list[str] = []
    for root in (Path("api/contracts"), Path("api/domain"), Path("api/application")):
        for path in _python_files(root):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "from dataclasses import" in line or "@dataclass" in line:
                    offenders.append(f"{path.as_posix()}:{line_no}: {line.strip()}")

    assert not offenders, "Use Pydantic models for API/domain contracts:\n" + "\n".join(
        offenders
    )
