"""Include authoritative server resources in normal setuptools wheel builds."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class ServerBuildPy(build_py):
    """Stage server-only resources without copying them into the core source tree."""

    def run(self) -> None:
        """Replace generated packages, then copy current code and server resources."""
        for name in ("api", "coyote3"):
            package = Path(self.build_lib) / name
            if package.is_dir():
                shutil.rmtree(package)
        super().run()
        root = Path(__file__).resolve().parent
        destination = Path(self.build_lib) / "api"
        shutil.copyfile(root / "release.toml", destination / "release.toml")
        for source, target in (
            ("config/examples/center", "config/examples/center"),
            ("demo_data/clinical_workflows", "bootstrap/demo_data/clinical_workflows"),
        ):
            shutil.copytree(root / source, destination / target, dirs_exist_ok=True)
