"""Remove stale generated sources before building this independent distribution."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CleanBuildPy(build_py):
    """Build from the current source tree without resurrecting deleted modules."""

    def run(self) -> None:
        """Replace the disposable build tree before copying current package files."""
        destination = Path(self.build_lib)
        if destination.is_dir():
            shutil.rmtree(destination)
        super().run()
