"""Build the independent HTTP client without retaining modules removed from source."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CleanClientBuildPy(build_py):
    """Replace this distribution's generated package tree before copying current sources."""

    def run(self) -> None:
        """Recreate this distribution's generated tree before copying current modules."""
        package = Path(self.build_lib)
        if package.is_dir():
            shutil.rmtree(package)
        super().run()
