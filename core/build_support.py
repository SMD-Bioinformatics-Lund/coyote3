"""Build the independent core in normal setuptools wheel builds."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CoreBuildPy(build_py):
    """Recreate the core build tree without bundling the API or database adapter."""

    def run(self) -> None:
        """Recreate this distribution's generated tree before staging current resources."""
        destination = Path(self.build_lib)
        if destination.is_dir():
            shutil.rmtree(destination)
        super().run()
