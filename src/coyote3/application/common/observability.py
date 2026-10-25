"""Structured timing helpers for bounded application operations."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger("coyote.operations")

P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def timed_operation(
    operation: str, *, observer: Callable[..., None] | None = None, **context: object
) -> Iterator[None]:
    """Log operation timing and notify the optional metrics adapter.

    Args:
        operation: Stable operation identifier used in logs and metrics.
        observer: Optional callback receiving operation, outcome and duration_ms.
        **context: Scalar diagnostic fields accompanying the completion log.

    Yields:
        Control to the measured operation; failures propagate after recording timing.
    """
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except Exception:
        outcome = "failure"
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        if observer is not None:
            observer(operation=operation, outcome=outcome, duration_ms=duration_ms)
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
        """Wrap the supplied callable with this operation's timing context.

        Args:
            function: Synchronous callable to measure.

        Returns:
            Wrapper preserving the callable's metadata and return value.
        """

        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            """Invoke the callable while logging scalar keyword context and timing.

            Args:
                *args: Positional arguments forwarded unchanged.
                **kwargs: Keyword arguments forwarded unchanged; scalar values and
                    ``None`` are also included in timing log context.

            Returns:
                The wrapped callable's return value.

            Notes:
                Exceptions propagate after the timing context records failure.
            """
            context: dict[str, Any] = {
                key: value
                for key, value in kwargs.items()
                if isinstance(value, (str, int, float, bool, type(None)))
            }
            observer = getattr(args[0], "operation_observer", None) if args else None
            with timed_operation(operation, observer=observer, **context):
                return function(*args, **kwargs)

        return wrapped

    return decorator
