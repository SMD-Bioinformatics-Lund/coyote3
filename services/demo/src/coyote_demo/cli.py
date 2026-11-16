# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Plan or install packaged synthetic resources in an isolated local demonstration."""

from __future__ import annotations

import argparse
import json
import os

from coyote_demo.deployment import (
    runtime_validator,
    validate_demo_target,
)


def main(argv: list[str] | None = None) -> None:
    """Validate configured targets and credentials before planning or installing demo resources.

    Args:
        argv: Explicit CLI arguments; None reads the current process argument vector.

    Raises:
        ValueError: The isolated target, privileges or actor are invalid.
        AppError: Existing resources conflict or a protected sample cannot be replaced.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", help="Override COYOTE4_MONGO_URI within the demo policy")
    parser.add_argument("--db", help="Override COYOTE4_DB; only coyote4_demo is permitted")
    parser.add_argument("--actor", required=True, help="Existing demonstration administrator")
    parser.add_argument(
        "--starter", action="store_true", help="Include synthetic DNA/RNA starter samples"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Install after validation; otherwise plan only"
    )
    args = parser.parse_args(argv)
    settings = {key: os.environ.get(key) for key in runtime_validator.configuration_keys}
    if args.mongo_uri is not None:
        settings["COYOTE4_MONGO_URI"] = args.mongo_uri
    if args.db is not None:
        settings["COYOTE4_DB"] = args.db
    validate_demo_target(settings)
    if not args.actor.strip():
        raise ValueError("Actor must not be blank")

    from coyote_demo.host import install_resources

    result = install_resources(settings, actor=args.actor, starter=args.starter, apply=args.apply)
    print(json.dumps(result, indent=2))
    if not args.apply:
        print("Plan only; repeat with --apply to install synthetic resources")


if __name__ == "__main__":
    main()
