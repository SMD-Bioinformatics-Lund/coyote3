# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Execute a native service with its exact saved environment, excluding manager state.

Systemd may retain environment variables from unrelated login sessions. This small
standard-library entry point runs under isolated Python before importing any server
packages, then replaces itself with the selected service and configuration.
"""

import json
import os
import stat
import sys
from pathlib import Path


def main(arguments: list[str]) -> None:
    """Replace this process after validating the private environment snapshot.

    Args:
        arguments: Snapshot path followed by the service executable and arguments.

    Raises:
        ValueError: The snapshot is unsafe or the command is absent.
        OSError: The snapshot or executable cannot be accessed.
    """
    if len(arguments) < 2:
        raise ValueError("A private environment snapshot and service command are required")
    path = Path(arguments[0])
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
    ):
        raise ValueError("Native environment snapshot must be an owner-only regular file")
    environment = json.loads(path.read_text())
    if not isinstance(environment, dict) or any(
        not isinstance(key, str)
        or not key
        or "=" in key
        or "\x00" in key
        or not isinstance(value, str)
        or "\x00" in value
        for key, value in environment.items()
    ):
        raise ValueError("Native environment snapshot must contain string assignments")
    os.execvpe(arguments[1], arguments[1:], environment)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, ValueError) as error:
        print(
            f"Native service could not load its configuration ({type(error).__name__})",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
