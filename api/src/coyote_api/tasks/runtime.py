# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime initialization and JSON transport for server-backed workers."""

from typing import Any

from celery.signals import worker_process_shutdown, worker_shutdown

from coyote_api.app.lifecycle import ensure_runtime_initialized, shutdown_runtime
from coyote_api.app.utilities.serialization import convert_to_serializable
from coyote_api.config.security import get_runtime_mode_flags


@worker_process_shutdown.connect
@worker_shutdown.connect
def close_worker_runtime(**_kwargs: Any) -> None:
    """Close dependencies owned by an exiting Celery child or solo worker."""
    shutdown_runtime()


def ensure_worker_runtime() -> None:
    """Initialize runtime dependencies in the Celery worker process."""
    mode_flags = get_runtime_mode_flags()
    ensure_runtime_initialized(
        testing=mode_flags["testing"],
        development=mode_flags["development"],
    )


def serializable(payload: Any) -> Any:
    """Convert ingest results for Celery's JSON result transport.

    Args:
        payload: Result containing nested mappings, sequences and BSON values.

    Returns:
        The result after conversion by the shared serialization utility.
    """
    return convert_to_serializable(payload)
