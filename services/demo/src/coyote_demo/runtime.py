# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validate demonstration isolation before starting workers or scheduled maintenance."""

import argparse
import os

from coyote_demo.deployment import runtime_validator, validate_demo_target, validate_runtime


def main(argv: list[str] | None = None) -> int | None:
    """Start a selected background service after isolation and privilege validation.

    Args:
        argv: Explicit service, log level and concurrency arguments, or None for
            the process command line. Endpoint and scheduler-path overrides are
            not accepted; they come from the reviewed demonstration settings.

    Returns:
        The background service's process exit status.

    Raises:
        ValueError: Demo settings or database privileges are unsafe.
        PyMongoError: The isolated local credential cannot be verified.
        SystemExit: Dependencies are absent or service options are invalid.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["ingest", "maintenance", "beat"])
    parser.add_argument("--concurrency", type=int)
    parser.add_argument(
        "--loglevel",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    args = parser.parse_args(argv)
    if args.concurrency is not None and (args.concurrency < 1 or args.service == "beat"):
        parser.error("--concurrency requires a worker service and a positive integer")
    settings = {key: os.environ.get(key) for key in runtime_validator.configuration_keys}
    validate_demo_target(settings)
    validate_runtime(settings)
    options = [f"--loglevel={args.loglevel}"]
    if args.service != "beat":
        options.append(f"--concurrency={args.concurrency or 1}")
    if args.service == "ingest":
        from coyote_relay.worker import main as worker_main

        return worker_main(options)
    from coyote_demo.host import start_background_service

    return start_background_service(args.service, options)


if __name__ == "__main__":
    raise SystemExit(main())
