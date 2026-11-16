"""Build the demonstration distribution without retaining retired source modules."""

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


class CleanDemoBuildPy(build_py):
    """Replace generated package output before copying authoritative sources and resources."""

    def run(self) -> None:
        """Remove stale build output so deleted datasets cannot remain in a release wheel."""
        package = Path(self.build_lib)
        if package.is_dir():
            shutil.rmtree(package)
        super().run()
