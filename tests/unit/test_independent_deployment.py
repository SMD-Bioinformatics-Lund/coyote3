"""Exercise mixed native/container deployment boundaries without contacting services."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from deploy.installer import cli, infrastructure, native, native_process
from deploy.installer.config import Profile, native_environment
from deploy.installer.native import NativeInstaller
from deploy.installer.native_services import (
    UserServices,
    operation_lock,
    prepare_directory,
    write_environment,
)
from deploy.installer.workflow import Options


@pytest.fixture
def profile(tmp_path, monkeypatch):
    """Select synthetic application targets; no database credentials are inherited."""
    for key in ("ENV_NAME", "LOG_LEVEL", "CELERY_LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "application.env"
    values = {
        "ENV_NAME": "stage",
        "SECRET_KEY": "synthetic-private-key",
        "INTERNAL_API_TOKEN": "synthetic-private-token",
        "PASSWORD_TOKEN_SALT": "synthetic-private-salt",
        "COYOTE4_MONGO_URI": "mongodb://127.0.0.1:29017/?replicaSet=synthetic",
        "IDENTITY_MONGO_URI": "mongodb://127.0.0.1:29017/?replicaSet=synthetic",
        "COYOTE4_DB": "synthetic_application",
        "IDENTITY_DB": "synthetic_identity",
        "PUBLIC_BASE_URL": "http://localhost:6801",
        "CACHE_REDIS_URL": "redis://127.0.0.1:29079/0",
        "CELERY_BROKER_URL": "redis://127.0.0.1:29079/1",
        "CELERY_RESULT_BACKEND": "redis://127.0.0.1:29079/2",
    }
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    return Profile.load(path, mode="native", directory=tmp_path / "runtime")


def test_native_profile_does_not_inherit_another_deployments_connections(profile, monkeypatch):
    monkeypatch.setenv("COYOTE4_MONGO_URI", "mongodb://unrelated.invalid")
    monkeypatch.setenv("LDAP_SECRET", "unrelated-secret")
    monkeypatch.setenv("ENV_NAME", "production")
    selected = Profile.load(profile.env_file, mode="native", environment="staging")
    assert selected.environment == "stage"
    assert selected.process_env["COYOTE4_MONGO_URI"].startswith("mongodb://127.0.0.1:29017/")
    assert "LDAP_SECRET" not in selected.process_env


def test_explicit_environment_references_never_execute_shell_or_read_ambient_keys(
    tmp_path, monkeypatch
):
    path = tmp_path / "settings.env"
    marker = tmp_path / "unwanted"
    path.write_text(f"ROOT=${{PWD}}/data\nCOPY=${{ROOT}}\nCOMMAND=$(touch {marker})\n")
    values = native_environment(path)
    assert values["ROOT"] == values["COPY"]
    assert values["COMMAND"].startswith("$(touch ")
    assert not marker.exists()
    monkeypatch.setenv("PRIVATE_VALUE", "ambient-secret")
    path.write_text("COPY=${PRIVATE_VALUE}\n")
    with pytest.raises(ValueError, match="Undefined environment reference"):
        native_environment(path)


def test_native_plan_is_read_only_and_never_contacts_systemd_or_databases(profile, monkeypatch):
    process = Mock(side_effect=AssertionError("Unexpected service operation"))
    monkeypatch.setattr(subprocess, "run", process)
    monkeypatch.setattr(subprocess, "Popen", process)
    NativeInstaller(profile, Options()).plan()
    assert not profile.directory.exists()
    process.assert_not_called()


@pytest.mark.parametrize(
    "service,mode",
    [("mongo", "docker"), ("redis", "docker"), ("mongo", "native"), ("redis", "native")],
)
def test_infrastructure_plan_needs_no_application_secrets(tmp_path, monkeypatch, service, mode):
    settings = tmp_path / "server.env"
    settings.write_text("ENV_NAME=stage\n")
    execute = Mock(side_effect=AssertionError("No process allowed during plan"))
    monkeypatch.setattr(subprocess, "run", execute)
    monkeypatch.setattr(subprocess, "Popen", execute)
    args = [service, "plan", "--mode", mode, "--env-file", str(settings)]
    if mode == "native":
        args.extend(["--unit", "synthetic.service"])
    assert cli.main(args) == 0
    execute.assert_not_called()


@pytest.mark.parametrize("service", ["mongo", "redis"])
def test_native_infrastructure_controls_only_the_explicit_unit(tmp_path, monkeypatch, service):
    settings = tmp_path / "server.env"
    settings.write_text("ENV_NAME=stage\n")
    run = Mock(return_value="")
    monkeypatch.setattr(infrastructure.Runner, "run", run)
    assert (
        cli.main(
            [
                service,
                "start",
                "--mode",
                "native",
                "--unit",
                "synthetic.service",
                "--env-file",
                str(settings),
            ]
        )
        == 0
    )
    assert run.call_args.args[0] == ["systemctl", "start", "--", "synthetic.service"]
    assert run.call_count == 1


@pytest.mark.parametrize("service", ["mongo", "redis"])
def test_docker_infrastructure_starts_only_its_server_and_initializer(
    tmp_path, monkeypatch, service
):
    path = tmp_path / "server.env"
    path.write_text("ENV_NAME=stage\n")
    engine = Mock()
    monkeypatch.setattr(infrastructure, "InfrastructureCompose", Mock(return_value=engine))
    assert cli.main([service, "start", "--mode", "docker", "--env-file", str(path)]) == 0
    calls = [call.args[0] for call in engine.run.call_args_list]
    assert calls[0][-1] == service
    assert "--wait" in calls[0]
    assert calls[1:] == ([["run", "--rm", "--no-deps", "mongo_init"]] if service == "mongo" else [])
    assert all("api" not in call for call in calls)


def test_native_application_retains_external_urls_and_independent_worker_queues(profile):
    installer = NativeInstaller(profile, Options())
    commands = installer.commands()
    assert not {"mongo", "redis"} & commands.keys()
    assert "--queues=ingest" in commands["worker"]
    assert "--queues=default" in commands["maintenance-worker"]
    assert "watchdog.watchmedo" not in commands["api"]
    assert installer.environment["CELERY_BROKER_URL"] == "redis://127.0.0.1:29079/1"
    assert str(profile.directory / "beat-schedule") in commands["beat"]


def test_native_frontend_receives_no_backend_credentials(profile):
    installer = NativeInstaller(profile, Options())
    environment = installer.public_environment()
    assert environment["ENV_NAME"] == "stage"
    assert environment["PUBLIC_BASE_URL"] == "http://localhost:6801"
    assert (
        not {"SECRET_KEY", "COYOTE4_MONGO_URI", "IDENTITY_MONGO_URI", "CELERY_BROKER_URL"}
        & environment.keys()
    )


def test_native_startup_failure_stops_only_processes_it_started(profile, monkeypatch):
    runner = Mock(redactions={}, run=Mock(return_value=""))
    installer = NativeInstaller(profile, Options(), runner=runner)
    prepare_directory(profile.directory)
    monkeypatch.setattr(installer, "_web_configuration", Mock())
    installer.services = Mock(spec=UserServices)
    installer.services.start.side_effect = [None, None, RuntimeError("synthetic worker failure")]
    with pytest.raises(RuntimeError, match="synthetic worker failure"):
        installer._start()
    installer.services.stop.assert_called_once_with(["monitor", "api"])
    assert (profile.directory / "runtime.json").stat().st_mode & 0o777 == 0o600


def test_redis_failure_prevents_native_bootstrap_and_start(profile, monkeypatch):
    runner = Mock(redactions={}, run=Mock(return_value=""))
    installer = NativeInstaller(profile, Options(steps=("validate", "start")), runner=runner)
    monkeypatch.setattr(native.shutil, "which", lambda name: f"/synthetic/{name}")
    installer.services = Mock(spec=UserServices)
    monkeypatch.setattr(installer, "_check", Mock(side_effect=ValueError("Redis unavailable")))
    monkeypatch.setattr(installer, "_check_ports", Mock())
    apply = Mock()
    monkeypatch.setattr(installer, "_apply", apply)
    with pytest.raises(ValueError, match="Redis unavailable"):
        installer.run()
    apply.assert_not_called()
    installer.services.start.assert_not_called()


def test_native_service_owner_check_prevents_stopping_unrelated_processes(profile):
    runner = Mock(
        redactions={},
        run=Mock(
            return_value=f"{profile.project}-api.service loaded active running Other application\n"
        ),
    )
    manager = UserServices(profile.project, profile.directory, runner)
    with pytest.raises(ValueError, match="another installation"):
        manager.stop(["api"])
    assert runner.run.call_count == 1
    assert "stop" not in runner.run.call_args.args[0]


def test_absent_native_services_are_safe_to_inspect_and_stop(profile):
    runner = Mock(redactions={}, run=Mock(return_value=""))
    manager = UserServices(profile.project, profile.directory, runner)
    assert manager.status(["api"]) == {"api": "inactive"}
    manager.stop(["api"])
    assert all("stop" not in call.args[0] for call in runner.run.call_args_list)


def test_native_stop_checks_all_owners_before_stopping_any_service(profile):
    runner = Mock(redactions={})
    manager = UserServices(profile.project, profile.directory, runner)
    runner.run.side_effect = [
        f"{profile.project}-api.service loaded active running {manager.description('api')}\n",
        f"{profile.project}-worker.service loaded active running Other owner\n",
    ]
    with pytest.raises(ValueError, match="another installation"):
        manager.stop(["api", "worker"])
    assert all("stop" not in call.args[0] for call in runner.run.call_args_list)


def test_native_operations_cannot_replace_each_others_runtime_settings(profile):
    with operation_lock(profile.directory):
        with pytest.raises(RuntimeError, match="operation is in progress"):
            with operation_lock(profile.directory):
                pytest.fail("Second deployment acquired an active operation lock")
    with operation_lock(profile.directory):
        assert (profile.directory / "operation.lock").exists()


def test_private_runtime_file_preserves_literal_secrets_and_refuses_symlinks(tmp_path):
    path = tmp_path / "runtime.json"
    write_environment(path, {"SECRET": 'synthetic "$value`\\quoted'})
    assert path.stat().st_mode & 0o777 == 0o600
    previous = path.read_text()
    alias = tmp_path / "alias.env"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="symbolic links"):
        write_environment(alias, {"SECRET": "replacement"})
    assert path.read_text() == previous


def test_native_service_replaces_systemd_manager_environment(tmp_path, monkeypatch):
    path = tmp_path / "runtime.json"
    selected = {"SECRET_KEY": 'synthetic "$literal`\\value', "PATH": "/synthetic"}
    write_environment(path, selected)
    monkeypatch.setenv("COYOTE4_MONGO_URI", "mongodb://unrelated.invalid")
    execute = Mock()
    monkeypatch.setattr(native_process.os, "execvpe", execute)
    native_process.main([str(path), "synthetic-service", "argument"])
    execute.assert_called_once_with(
        "synthetic-service", ["synthetic-service", "argument"], selected
    )


def test_native_prepare_preserves_existing_data_and_checks_installation_identity(profile):
    installer = NativeInstaller(profile, Options())
    installer._prepare()
    data = Path(installer.environment["COYOTE4_DATA_ROOT"])
    document = data / "retained.txt"
    document.write_text("synthetic retained artifact")
    installer._prepare()
    assert document.read_text() == "synthetic retained artifact"
    metadata = profile.directory / "installation.json"
    metadata.write_text(json.dumps({"workspace": "another installation"}))
    with pytest.raises(ValueError, match="different installation"):
        installer._prepare()
    assert document.read_text() == "synthetic retained artifact"
