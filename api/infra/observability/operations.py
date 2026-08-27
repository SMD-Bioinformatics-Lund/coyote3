"""Structured timing helpers for bounded application operations."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from api.infra.observability.prometheus_metrics import observe_operation

logger = logging.getLogger("coyote.operations")

P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def timed_operation(operation: str, **context: object) -> Iterator[None]:
    """Measure one operation and emit a structured log plus Prometheus counters."""
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "failure"
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        observe_operation(operation=operation, outcome=outcome, duration_ms=duration_ms)
        logger.info(
            "operation_completed operation=%s outcome=%s duration_ms=%.2f context=%s",
            operation,
            outcome,
            duration_ms,
            context,
        )


def measured_operation(operation: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a synchronous application operation with shared timing metrics."""

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            context: dict[str, Any] = {
                key: value
                for key, value in kwargs.items()
                if isinstance(value, (str, int, float, bool, type(None)))
            }
            with timed_operation(operation, **context):
                return function(*args, **kwargs)

        return wrapped

    return decorator
