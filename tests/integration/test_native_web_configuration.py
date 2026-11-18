"""Validate native web artifacts with disposable, network-disabled Nginx containers."""

import os
import shutil
import subprocess

import pytest

from deploy.installer.config import ROOT, Profile
from deploy.installer.native import NativeInstaller
from deploy.installer.process import Runner
from deploy.installer.workflow import Options


@pytest.mark.parametrize("prefix", ["", "/synthetic"])
def test_native_web_configuration_is_accepted_by_nginx(tmp_path, prefix, monkeypatch):
    """Catch conflicts when frontend, documentation and proxy share one Nginx process."""
    if not shutil.which("docker"):
        pytest.skip("Local Docker CLI is unavailable")
    # This test cannot use a remote Docker context, pull an image or connect to a DB.
    docker = ["docker", "--host", "unix:///var/run/docker.sock"]
    available = subprocess.run(
        [*docker, "image", "inspect", "nginx:1.27-alpine"],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if available.returncode:
        pytest.skip("Local disposable Nginx image/daemon unavailable")
    monkeypatch.delenv("ENV_NAME", raising=False)
    settings = tmp_path / "application.env"
    settings.write_text(
        "ENV_NAME=stage\nCOYOTE4_DB=synthetic_app\nIDENTITY_DB=synthetic_identity\n"
        f"PUBLIC_BASE_URL=http://127.0.0.1:6801\nSCRIPT_NAME={prefix}\n"
    )
    profile = Profile.load(settings, mode="native", directory=tmp_path / "runtime")

    class ValidationRunner(Runner):
        """Run renderers locally and only the Nginx syntax check inside the container."""

        def run(self, command, **kwargs):
            if command[0] == "nginx":
                command = [
                    *docker,
                    "run",
                    "--rm",
                    "--network=none",
                    "--pull=never",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--mount",
                    f"type=bind,src={profile.directory},dst={profile.directory}",
                    "--mount",
                    f"type=bind,src={ROOT / 'deploy/compose/nginx/error-pages'},dst={ROOT / 'deploy/compose/nginx/error-pages'},readonly",
                    "nginx:1.27-alpine",
                    *command,
                ]
            return super().run(command, **kwargs)

    installer = NativeInstaller(profile, Options(), runner=ValidationRunner(profile.process_env))
    installer._prepare()
    installer._web_configuration()
