# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Run the installed Coyote4 ASGI server with explicit listener options."""

import argparse


def main() -> None:
    """Start coyote_api.app.main:app after operators configure the deployment environment.

    Raises:
        SystemExit: Listener arguments are invalid or API dependencies are not installed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    try:
        import uvicorn
    except ImportError:
        parser.error("Install coyote-api and its declared dependencies from the retained wheels")
    uvicorn.run("coyote_api.app.main:app", host=args.host, port=args.port, workers=args.workers)
