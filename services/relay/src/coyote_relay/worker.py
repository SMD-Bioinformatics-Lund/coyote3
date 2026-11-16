# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Command-line entry point for the separately installed ingestion worker."""

import sys


def main(argv: list[str] | None = None) -> int | None:
    """Run Celery on the configured ingestion queue using the server runtime.

    Args:
        argv: Celery worker options; None reads process arguments. An explicit
            queue option is forwarded, otherwise the configured ingest queue is used.

    Returns:
        Celery's exit status, including nonzero startup or command errors.

    Raises:
        SystemExit: Worker dependencies are missing or Celery rejects the arguments.
    """
    try:
        from coyote_api.config.runtime_settings import DefaultConfig

        from coyote_relay.celery_app import celery_app
    except ModuleNotFoundError as exc:
        if exc.name in {"coyote_api", "celery"}:
            raise SystemExit("Worker execution requires coyote-relay[worker].") from exc
        raise
    options = sys.argv[1:] if argv is None else argv
    return celery_app.start(["worker", "--queues", DefaultConfig.CELERY_INGEST_QUEUE, *options])


if __name__ == "__main__":
    raise SystemExit(main())
