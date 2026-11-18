"""Development reload selection and service lifecycle using isolated synthetic commands."""

import signal
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest
import yaml

from deploy.installer import cli, config, development
from deploy.installer.development import DevelopmentWatcher


@pytest.fixture
def checkout(tmp_path):
    """Create editable package metadata without any application credentials or services."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.setuptools.package-dir]\ncoyote_api = "api/src/coyote_api"\n'
        '[tool.uv.workspace]\nmembers = ["core", "services/atlas", "services/demo"]\n'
    )
    for name in (
        "api",
        "core",
        "services/atlas",
        "services/demo",
    ):
        (tmp_path / name / "src").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize(
    "environment", ["prod", "production", "stage", "staging", "test", "testing", "validation"]
)
def test_other_environments_cannot_launch_a_watcher(checkout, monkeypatch, environment):
    monkeypatch.setattr(development, "ROOT", checkout)
    monkeypatch.setenv("ENV_NAME", environment)
    execute = Mock()
    monkeypatch.setattr(development.os, "execvpe", execute)
    assert cli.main(["watch", "--", sys.executable, "-c", "pass"]) == 1
    execute.assert_not_called()


def test_watch_reads_the_selected_environment_without_logging_secrets(
    checkout, monkeypatch, capsys
):
    monkeypatch.setattr(development, "ROOT", checkout)
    monkeypatch.delenv("ENV_NAME", raising=False)
    settings = checkout / "development.env"
    settings.write_text("ENV_NAME=development\nSECRET_KEY=synthetic-private-value\n")
    execute = Mock()
    monkeypatch.setattr(development.os, "execvpe", execute)
    assert cli.main(["watch", "--env-file", str(settings), "--", sys.executable, "-c", "pass"]) == 0
    _, arguments, environment = execute.call_args.args
    assert environment["ENV_NAME"] == "development"
    assert environment["SECRET_KEY"] == "synthetic-private-value"
    assert arguments[-3:] == [sys.executable, "-c", "pass"]
    assert "synthetic-private-value" not in capsys.readouterr().err


def test_workspace_and_external_editable_packages_are_all_watched(checkout):
    extra = checkout / "external client"
    extra.mkdir()
    watcher = DevelopmentWatcher(checkout, {"ENV_NAME": "dev"})
    directories = watcher.directories([extra, extra])
    assert {path.relative_to(checkout).as_posix() for path in directories} == {
        "api/src",
        "core/src",
        "services/atlas/src",
        "services/demo/src",
        "external client",
    }
    assert directories.count(extra) == 1


def wait_for(predicate, timeout=10):
    """Bound asynchronous filesystem observations without contacting services."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Development service did not reach its expected state")


def test_source_and_package_configuration_changes_restart_and_shutdown_service(checkout):
    """Exercise actual polling and signals, including sources from an optional service."""
    source = checkout / "services/atlas/src/version.py"
    settings = checkout / "core/src/settings.toml"
    source.write_text("first")
    settings.write_text("initial")
    events = checkout / "events.txt"
    program = (
        "from pathlib import Path; import signal, time\n"
        f"events = Path({str(events)!r})\n"
        "def record(value):\n"
        '    with events.open("a") as output: output.write(value + "\\n")\n'
        "def stop(*args):\n"
        '    record("stopped")\n'
        "    raise SystemExit(0)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        f'record(Path({str(source)!r}).read_text() + ":" + Path({str(settings)!r}).read_text())\n'
        "while True: time.sleep(0.1)\n"
    )
    watcher = DevelopmentWatcher(checkout, {"ENV_NAME": "development"})
    command = watcher.command([sys.executable, "-u", "-c", program], [])
    with (checkout / "watch.log").open("w") as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, cwd=checkout)
        try:
            wait_for(lambda: events.exists() and "first:initial" in events.read_text())
            # Watchmedo starts the child before taking its initial polling snapshot.
            time.sleep(1.1)
            source.write_text("second")
            wait_for(lambda: "second:initial" in events.read_text())
            settings.write_text("updated")
            wait_for(lambda: "second:updated" in events.read_text())
        finally:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
    assert events.read_text().splitlines() == [
        "first:initial",
        "stopped",
        "second:initial",
        "stopped",
        "second:updated",
        "stopped",
    ]


@pytest.mark.parametrize("folder", ["compose", "legacy"])
def test_docker_services_run_directly_with_manual_backend_reload(folder):
    """Check the selected deployment wiring rather than starting containers."""

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor("!reset", lambda loader, node: None)
    directory = config.ROOT / "deploy" / folder
    dev = yaml.load((directory / "docker-compose.dev.yml").read_text(), Loader=Loader)["services"]
    production = yaml.safe_load((directory / "docker-compose.yml").read_text())["services"]
    for service in ("api", "worker", "maintenance-worker", "beat", "monitor"):
        assert "installer watch" not in dev[service]["command"]
        assert "--reload" not in dev[service]["command"]
        assert "installer watch" not in production[service]["command"]
        mounts = [entry for entry in dev[service]["volumes"] if isinstance(entry, str)]
        for package in (
            "api",
            "adapters/mongo",
            "core",
            "services/atlas",
            "services/demo",
        ):
            assert f"../../{package}:/app/{package}" in mounts
    assert "npm run dev" in dev["frontend"]["command"]
    assert dev["frontend"]["environment"]["CHOKIDAR_USEPOLLING"] == "true"
