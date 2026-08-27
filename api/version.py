"""Application version ownership for the FastAPI/runtime stack."""

import sys

__version__ = "4.0.0"


if __name__ == "__main__":
    sys.stdout.write(f"{__version__}\n")
