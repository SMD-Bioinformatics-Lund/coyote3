"""Include authoritative server resources in normal setuptools wheel builds."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class ServerBuildPy(build_py):
    """Stage server-only resources without copying them into the core source tree."""

    def run(self) -> None:
        """Build Python packages and copy release identity, defaults and demo resources."""
        super().run()
        root = Path(__file__).resolve().parent
        destination = Path(self.build_lib) / "api"
        shutil.copyfile(root / "release.toml", destination / "release.toml")
        for source, target in (
            ("config/examples/center", "config/examples/center"),
            ("demo_data/clinical_workflows", "bootstrap/demo_data/clinical_workflows"),
        ):
            shutil.copytree(root / source, destination / target, dirs_exist_ok=True)
