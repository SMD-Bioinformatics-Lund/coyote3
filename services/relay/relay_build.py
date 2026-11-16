"""Build the ingestion distribution without retaining modules removed from source."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CleanRelayBuildPy(build_py):
    """Replace this distribution's generated tree before copying current sources."""

    def run(self) -> None:
        """Recreate generated package output so a retired module cannot enter the wheel."""
        package = Path(self.build_lib)
        if package.is_dir():
            shutil.rmtree(package)
        super().run()
