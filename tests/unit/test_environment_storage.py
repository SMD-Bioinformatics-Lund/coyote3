"""Environment storage naming and directory creation without external services."""

import runpy
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "api/config/paths.py"


def test_container_directory_maps_to_expected_host_directory(monkeypatch):
    monkeypatch.setenv("ENV_NAME", "development")
    config = runpy.run_path(str(SOURCE))
    container_root = config["COYOTE3_DATA_CONTAINER_ROOT"]
    assert container_root == Path("/data/coyote3_dev")
    host_root = Path("/data/coyote3") / container_root.relative_to("/data")
    assert host_root == Path("/data/coyote3/coyote3_dev")


@pytest.mark.parametrize(
    ("environment", "folder"),
    [
        ("development", "dev"),
        ("dev", "dev"),
        ("Production", "prod"),
        ("prod", "prod"),
        ("testing", "test"),
        ("test", "test"),
        ("staging", "stage"),
        ("stage", "stage"),
        ("validation", "validation"),
    ],
)
def test_environment_directory(environment, folder, tmp_path):
    config = runpy.run_path(str(SOURCE))
    assert (
        config["environment_storage_root"](environment, tmp_path) == tmp_path / f"coyote3_{folder}"
    )


@pytest.mark.parametrize("environment", ["", "../dev", "/dev", "dev/other", "dev other"])
def test_environment_cannot_escape_root(environment):
    config = runpy.run_path(str(SOURCE))
    with pytest.raises(ValueError):
        config["environment_storage_root"](environment)


def test_startup_creates_directories_without_overwriting_files(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_NAME", "development")
    config = runpy.run_path(str(SOURCE))
    initialize = config["initialize_storage_directories"]
    for key in ("REPORTS_BASE_PATH", "INGEST_STAGING_DIR", "INGEST_WATCH_DIR"):
        path = tmp_path / config[key].relative_to("/data")
        initialize.__globals__[key] = path
    initialize()
    report = initialize.__globals__["REPORTS_BASE_PATH"] / "existing.html"
    report.write_text("saved report")
    initialize()
    assert report.read_text() == "saved report"
    assert (tmp_path / "coyote3_dev/copied_sample_files/yaml").is_dir()
