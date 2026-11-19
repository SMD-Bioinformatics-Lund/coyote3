from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "definition",
    [
        "deploy/compose/docker-compose.yml",
        "deploy/legacy/docker-compose.yml",
        "deploy/legacy/docker-compose.dev.yml",
    ],
)
def test_proxy_mounts_standalone_error_page_in_every_stack(definition: str) -> None:
    """Every proxy definition supplies the local page required by its shared Nginx config."""
    path = REPOSITORY_ROOT / definition
    proxy = yaml.safe_load(path.read_text())["services"]["proxy"]
    mounts = [value.split(":") for value in proxy["volumes"] if isinstance(value, str)]
    page_mounts = [value for value in mounts if value[1] == "/etc/nginx/error-pages"]
    assert len(page_mounts) == 1
    source, _, mode = page_mounts[0]
    assert mode == "ro"
    assert (path.parent / source).resolve() == (
        REPOSITORY_ROOT / "deploy/compose/nginx/error-pages"
    )
    assert (
        "Service temporarily unavailable" in (path.parent / source / "unavailable.html").read_text()
    )


@pytest.mark.parametrize(
    "script",
    [
        "install.sh",
        "scripts/quality/run_quality_suite.sh",
        "scripts/quality/run_package_tests.sh",
        "scripts/database/mongo_backup_archive.sh",
        "scripts/database/mongo_restore_archive.sh",
    ],
)
def test_documented_shell_entry_points_are_executable(script: str) -> None:
    """Commands documented without a shell prefix must run from a fresh checkout."""
    assert os.access(REPOSITORY_ROOT / script, os.X_OK), script


@pytest.mark.parametrize("selection", ["repository", "active", "explicit"])
def test_family_coverage_uses_project_root_and_selected_interpreter(tmp_path, selection):
    """Running from outside the repo preserves interpreter precedence and coverage location."""
    root = tmp_path / "project"
    scripts = root / "scripts" / "quality"
    scripts.mkdir(parents=True)
    script = scripts / "run_family_coverage_gates.sh"
    script.write_text(
        (REPOSITORY_ROOT / "scripts/quality/run_family_coverage_gates.sh").read_text(),
        encoding="utf-8",
    )
    (root / ".coverage").touch()
    interpreters = {}
    for name in ("repository", "active", "explicit"):
        path = root / (".venv" if name == "repository" else name) / "bin/python"
        path.parent.mkdir(parents=True)
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name}:$PWD:$*"\n', encoding="utf-8")
        path.chmod(0o700)
        interpreters[name] = path
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHON_BIN", "VIRTUAL_ENV"}
    }
    if selection in {"active", "explicit"}:
        env["VIRTUAL_ENV"] = str(interpreters["active"].parents[1])
    if selection == "explicit":
        env["PYTHON_BIN"] = str(interpreters["explicit"])
    result = subprocess.run(
        ["bash", str(script), "--from-existing"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.count(f"{selection}:{root}:-m coverage report") == 5


def _run_script(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    folder = "database" if script.startswith("mongo_") else "deployment"
    return subprocess.run(
        ["bash", str(REPOSITORY_ROOT / "scripts" / folder / script), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_backup_script_documents_and_enforces_required_arguments() -> None:
    help_result = _run_script("mongo_backup_archive.sh", "--help")
    assert help_result.returncode == 0
    assert "Create a compressed MongoDB backup archive" in help_result.stdout

    missing_result = _run_script("mongo_backup_archive.sh")
    assert missing_result.returncode == 2
    assert "--mongo-uri and --out-dir are required" in missing_result.stdout


def test_restore_script_requires_explicit_patient_data_confirmation(tmp_path: Path) -> None:
    archive = tmp_path / "backup.archive.gz"
    archive.write_bytes(b"not a real archive")

    result = _run_script(
        "mongo_restore_archive.sh",
        "--mongo-uri",
        "mongodb://example.invalid:27017",
        "--archive",
        str(archive),
    )

    assert result.returncode == 3
    assert "restore blocked" in result.stdout
    assert "starting restore" not in result.stdout


def test_public_proxy_applies_browser_security_headers() -> None:
    script = (REPOSITORY_ROOT / "deploy/compose/nginx/render-config.sh").read_text(encoding="utf-8")

    assert 'add_header X-Content-Type-Options "nosniff" always;' in script
    assert 'add_header X-Frame-Options "DENY" always;' in script
    assert "add_header Content-Security-Policy" in script
    assert "Strict-Transport-Security" in script
    assert r"proxy_set_header X-Forwarded-Proto \$forwarded_proto;" in script


def test_root_proxy_preserves_frontend_asset_and_route_paths(tmp_path: Path) -> None:
    """Render a root deployment without replacing every frontend request URI with slash."""
    output = tmp_path / "nginx.conf"
    result = subprocess.run(
        ["sh", str(REPOSITORY_ROOT / "deploy/compose/nginx/render-config.sh")],
        env={
            **os.environ,
            "SCRIPT_NAME": "",
            "COYOTE4_NGINX_OUTPUT_PATH": str(output),
            "COYOTE4_NGINX_FRONTEND_UPSTREAM": "http://frontend:3000",
            "COYOTE4_NGINX_API_UPSTREAM": "http://api:8001",
            "COYOTE4_NGINX_DOCS_UPSTREAM": "http://docs:8080",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    frontend_location = output.read_text().split("    location / {", 1)[1]
    assert "proxy_pass $frontend_target;" in frontend_location
    assert "proxy_pass $frontend_target/;" not in frontend_location


def test_restore_does_not_print_database_credentials(tmp_path: Path, monkeypatch) -> None:
    """Exercise restore logging without contacting Docker or a database."""
    archive = tmp_path / "synthetic.archive.gz"
    archive.write_bytes(gzip.compress(b"synthetic archive"))
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    uri = "mongodb://restore-user:synthetic-password@example.invalid:27017/admin"
    result = _run_script(
        "mongo_restore_archive.sh",
        "--mongo-uri",
        uri,
        "--archive",
        str(archive),
        "--confirm",
        "RESTORE_PATIENT_DATA",
    )
    assert result.returncode == 0, result.stderr
    assert "restore complete" in result.stdout
    assert uri not in result.stdout + result.stderr
    assert "synthetic-password" not in result.stdout + result.stderr


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "Dockerfile.legacy"])
def test_production_images_build_dependencies_outside_runtime(dockerfile: str) -> None:
    """Production bases retain shared libraries without compiler and header layers."""
    definition = (REPOSITORY_ROOT / "docker" / dockerfile).read_text()
    builder = definition.split(" AS coyote4_dependency_builder\n", 1)[1].split("\nFROM ", 1)[0]
    runtime = definition.split(" AS coyote4_runtime_base\n", 1)[1].split("\nFROM ", 1)[0]
    assert "pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt" in builder
    assert "--ignore-installed" in builder
    assert "--prefix=/opt/runtime -r requirements.txt" in builder
    assert "COPY --from=coyote4_dependency_builder /opt/runtime/ /usr/local/" in runtime
    assert "build-essential" not in runtime
    assert "-dev " not in runtime
    assert "pip install" not in runtime
    assert "libpango-1.0-0" in runtime
    assert "libpangoft2-1.0-0" in runtime
    assert "fonts-dejavu-core" in runtime
    assert "FROM coyote4_dependency_builder AS coyote4_runtime_base" not in definition
    assert "/tmp/coyote-pyclient" not in definition


@pytest.mark.parametrize(
    "relative_path",
    [
        "deploy/compose/docker-compose.yml",
        "deploy/legacy/docker-compose.yml",
        "deploy/legacy/docker-compose.dev.yml",
    ],
)
def test_deployments_start_ingest_and_maintenance_from_their_own_apps(relative_path) -> None:
    """Both deployment variants keep ingestion and maintenance on their owning task apps."""
    services = yaml.safe_load((REPOSITORY_ROOT / relative_path).read_text())["services"]
    assert "coyote-relay-worker" in services["worker"]["command"]
    assert "--queues=ingest " in services["worker"]["command"]
    assert "coyote_api.celery_app:celery_app" in services["maintenance-worker"]["command"]
    assert "--queues=default " in services["maintenance-worker"]["command"]
    assert "coyote_api.celery_app:celery_app beat" in services["beat"]["command"]


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "Dockerfile.dev", "Dockerfile.legacy"])
def test_source_images_include_the_selected_reference_distribution(dockerfile) -> None:
    """Source and editable image builds have the complete independently packaged service."""
    definition = (REPOSITORY_ROOT / "docker" / dockerfile).read_text()
    assert "COPY .release/atlas/ /opt/coyote-atlas/" in definition
    if dockerfile in {"Dockerfile.dev", "Dockerfile.legacy"}:
        assert "/opt/coyote-atlas/coyote_atlas-*.whl" in definition
