"""Build the server distribution from its API and persistence source components."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CleanBuildPy(build_py):
    """Keep deleted modules out of subsequent server wheel builds."""

    def run(self) -> None:
        """Replace the disposable build tree before staging current server sources."""
        destination = Path(self.build_lib)
        if destination.is_dir():
            shutil.rmtree(destination)
        super().run()
