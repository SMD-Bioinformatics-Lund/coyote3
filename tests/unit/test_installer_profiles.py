"""Verify deployment planning, command boundaries and credential-safe failures."""

import subprocess
from unittest.mock import Mock

import pytest

from deploy.installer import cli, compose, config
from deploy.installer.config import Profile
from deploy.installer.process import Runner
from deploy.installer.workflow import Installer, Options


@pytest.fixture
def environment_file(tmp_path, monkeypatch):
    """Supply an explicit synthetic target without inheriting operator selections."""
    settings = {
        "SECRET_KEY": "synthetic-secret-key",
        "INTERNAL_API_TOKEN": "synthetic-internal-token",
        "PASSWORD_TOKEN_SALT": "synthetic-password-salt",
        "REDIS_PASSWORD": "synthetic_redis_password",
        "COYOTE4_MONGO_URI": "mongodb://synthetic.invalid",
    }
    for key in (*settings, "ENV_NAME", "LOG_LEVEL", "CELERY_LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "settings.env"
    path.write_text("".join(f"{key}={value}\n" for key, value in settings.items()))
    return path


@pytest.mark.parametrize("environment", ["prod", "dev", "stage", "test"])
@pytest.mark.parametrize("legacy", [False, True])
def test_profiles_select_matching_files_and_versioned_images(environment_file, environment, legacy):
    profile = Profile.load(environment_file, environment=environment, legacy=legacy)
    directory = config.ROOT / "deploy" / ("legacy" if legacy else "compose")
    expected = [directory / "docker-compose.yml"]
    if environment != "prod":
        expected.append(directory / f"docker-compose.{environment}.yml")
    assert list(profile.files) == expected
    version = profile.process_env["COYOTE4_VERSION"]
    assert profile.process_env["COYOTE4_IMAGE_TAG"] == (
        version if environment == "prod" else f"{version}-{environment}"
    )


@pytest.mark.parametrize(
    "short,full",
    [("prod", "production"), ("dev", "development"), ("stage", "staging"), ("test", "testing")],
)
@pytest.mark.parametrize("full_argument", [False, True])
def test_cli_accepts_equivalent_deployment_spellings(
    environment_file, monkeypatch, capsys, short, full, full_argument
):
    """CLI names and ENV_NAME may use different spellings of the same deployment."""
    argument, configured = (full, short) if full_argument else (short, full)
    environment_file.write_text(environment_file.read_text() + f"ENV_NAME={configured}\n")
    process = Mock(side_effect=AssertionError("No subprocess may run"))
    monkeypatch.setattr(subprocess, "run", process)
    monkeypatch.setattr(subprocess, "Popen", process)

    assert cli.main(["plan", "--env-file", str(environment_file), "--environment", argument]) == 0

    output = capsys.readouterr().err
    assert f"Environment: {short}; project: coyote4-{short};" in output
    if short != "prod":
        assert f"deploy/compose/docker-compose.{short}.yml" in output
    process.assert_not_called()


@pytest.mark.parametrize("environment", ["stage", "staging"])
def test_mismatched_profile_stops_before_any_process(environment_file, monkeypatch, environment):
    environment_file.write_text(environment_file.read_text() + "ENV_NAME=production\n")
    run = Mock(side_effect=AssertionError("No subprocess may run"))
    monkeypatch.setattr(subprocess, "run", run)
    assert (
        cli.main(["deploy", "--env-file", str(environment_file), "--environment", environment]) == 1
    )
    run.assert_not_called()


@pytest.mark.parametrize("source", ["argument", "file"])
def test_clinical_validation_is_rejected_as_a_deployment(environment_file, monkeypatch, source):
    """A sample validation profile must never select deployment files or services."""
    process = Mock(side_effect=AssertionError("No subprocess may run"))
    monkeypatch.setattr(subprocess, "run", process)
    monkeypatch.setattr(subprocess, "Popen", process)
    arguments = ["plan", "--env-file", str(environment_file)]
    if source == "argument":
        with pytest.raises(SystemExit) as error:
            cli.main([*arguments, "--environment", "validation"])
        assert error.value.code == 2
    else:
        environment_file.write_text(environment_file.read_text() + "ENV_NAME=validation\n")
        assert cli.main(arguments) == 1
    process.assert_not_called()


def test_plan_never_executes_or_prepares_storage(environment_file, monkeypatch, capsys):
    profile = Profile.load(environment_file, environment="stage")
    process = Mock(side_effect=AssertionError("No subprocess may run"))
    storage = Mock(side_effect=AssertionError("No storage may be prepared"))
    monkeypatch.setattr(subprocess, "run", process)
    monkeypatch.setattr(subprocess, "Popen", process)
    monkeypatch.setattr(compose, "prepare", storage)
    before = {
        path: path.read_bytes() for path in environment_file.parent.rglob("*") if path.is_file()
    }
    Installer(profile, Options()).plan()
    after = {
        path: path.read_bytes() for path in environment_file.parent.rglob("*") if path.is_file()
    }
    assert after == before
    assert "synthetic-secret-key" not in capsys.readouterr().err
    process.assert_not_called()
    storage.assert_not_called()


@pytest.mark.parametrize("flag", ["-v", "--volumes", "--volumes=true", "-v=true", "-vt30"])
def test_volume_removal_is_rejected_before_compose(environment_file, flag):
    runner = Mock(redactions={})
    engine = compose.Compose(Profile.load(environment_file), runner)
    with pytest.raises(ValueError, match="never remove deployment data"):
        engine.run(["down", flag])
    runner.run.assert_not_called()


def test_run_arguments_are_not_parsed_as_installer_flags(environment_file, monkeypatch):
    engine = Mock()
    monkeypatch.setattr(cli, "Compose", Mock(return_value=engine))
    assert (
        cli.main(
            [
                "compose",
                "--env-file",
                str(environment_file),
                "run",
                "--rm",
                "api",
                "echo",
                "down",
                "-v",
                "--env-file",
                "unrelated",
            ]
        )
        == 0
    )
    engine.run.assert_called_once_with(
        ["run", "--rm", "api", "echo", "down", "-v", "--env-file", "unrelated"]
    )


def test_environment_files_are_data_and_duplicate_keys_are_rejected(tmp_path):
    path = tmp_path / "literal.env"
    marker = tmp_path / "unwanted"
    path.write_text(f"VALUE=$(touch {marker})\nOTHER=value#fragment # comment\n")
    assert config.read_environment(path) == {
        "VALUE": f"$(touch {marker})",
        "OTHER": "value#fragment",
    }
    assert not marker.exists()
    path.write_text("ENV_NAME=prod\nENV_NAME=dev\n")
    with pytest.raises(ValueError, match="Duplicate environment key"):
        config.read_environment(path)


def test_process_failure_redacts_known_secrets_and_uri_credentials(monkeypatch):
    environment = {"SECRET_KEY": "synthetic-private-key"}
    result = subprocess.CompletedProcess(
        [], 1, stderr="synthetic-private-key mongodb://operator:unknown-password@synthetic.invalid"
    )
    monkeypatch.setattr(subprocess, "run", Mock(return_value=result))
    with pytest.raises(RuntimeError) as failure:
        Runner(environment).run(["fake"], label="Validation", capture=True)
    assert "synthetic-private-key" not in str(failure.value)
    assert "unknown-password" not in str(failure.value)
    assert "Validation failed" in str(failure.value)


def test_compose_service_profiles_and_overlay_order_are_preserved(environment_file):
    overlay = config.ROOT / "deploy/compose/docker-compose.redis-tls.yml"
    profile = Profile.load(
        environment_file, environment="stage", overlays=[overlay], service_profiles=["docs"]
    )
    assert profile.files[-1] == overlay
    arguments = profile.arguments()
    assert arguments[-2:] == ["--profile", "docs"]
    assert arguments[arguments.index("--env-file") + 1] == str(environment_file)
