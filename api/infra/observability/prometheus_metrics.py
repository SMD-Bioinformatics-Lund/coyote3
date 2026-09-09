"""Minimal Prometheus text metrics for API request observability."""

from __future__ import annotations

import threading
from collections import defaultdict


def _label(value: str) -> str:
    """Replace label delimiters and truncate to 120 characters.

    Args:
        value: Label text; falsey values become an empty string.

    Returns:
        Text with backslashes, quotes, and newlines replaced by underscores.
    """
    return str(value or "").replace("\\", "_").replace('"', "_").replace("\n", "_")[:120]


class _ApiMetricsStore:
    """Accumulate process-local request and operation metrics under a lock."""

    def __init__(self) -> None:
        """Initialize empty counters, duration totals, gauges, and their lock."""
        self._lock = threading.Lock()
        self._requests_total: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self._latency_ms_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._latency_ms_count: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._rate_limited_total: defaultdict[str, int] = defaultdict(int)
        self._operations_total: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._operation_duration_ms_sum: defaultdict[str, float] = defaultdict(float)
        self._operation_duration_ms_count: defaultdict[str, int] = defaultdict(int)
        self._startup_phase_duration_ms: dict[str, float] = {}

    def observe_request(
        self, *, method: str, path: str, status_code: int, duration_ms: float
    ) -> None:
        """Count a request and accumulate its nonnegative duration under the lock.

        Args:
            method: HTTP method, uppercased for the label.
            path: Request path label.
            status_code: HTTP status, grouped by hundreds as a status class.
            duration_ms: Elapsed milliseconds, clamped to zero.
        """
        status_class = f"{int(status_code) // 100}xx"
        key = (_label(method.upper()), _label(path), _label(status_class))
        latency_key = (_label(method.upper()), _label(path))
        with self._lock:
            self._requests_total[key] += 1
            self._latency_ms_sum[latency_key] += max(float(duration_ms), 0.0)
            self._latency_ms_count[latency_key] += 1

    def inc_rate_limited(self, *, path: str) -> None:
        """Increment the rejection counter for a sanitized path label.

        Args:
            path: Path whose rate limit rejected a request.
        """
        with self._lock:
            self._rate_limited_total[_label(path)] += 1

    def observe_operation(self, *, operation: str, outcome: str, duration_ms: float) -> None:
        """Count an operation outcome and accumulate duration across outcomes.

        Args:
            operation: Operation name used as a sanitized label.
            outcome: Outcome label for the invocation counter.
            duration_ms: Elapsed milliseconds, clamped to zero.
        """
        operation_label = _label(operation)
        with self._lock:
            self._operations_total[(operation_label, _label(outcome))] += 1
            self._operation_duration_ms_sum[operation_label] += max(float(duration_ms), 0.0)
            self._operation_duration_ms_count[operation_label] += 1

    def set_startup_phase_duration(self, *, phase: str, duration_ms: float) -> None:
        """Replace the latest duration gauge for a startup phase.

        Args:
            phase: Startup phase name used as a sanitized label.
            duration_ms: Elapsed milliseconds, clamped to zero.
        """
        with self._lock:
            self._startup_phase_duration_ms[_label(phase)] = max(float(duration_ms), 0.0)

    def render(self) -> str:
        """Serialize a locked snapshot in Prometheus text format.

        Returns:
            Metric declarations and sorted observations with a trailing newline;
            duration values use milliseconds and six decimal places.
        """
        with self._lock:
            lines: list[str] = [
                "# HELP coyote3_api_requests_total Total API requests by method/path/status class.",
                "# TYPE coyote3_api_requests_total counter",
            ]
            for (method, path, status_class), count in sorted(self._requests_total.items()):
                lines.append(
                    'coyote3_api_requests_total{method="%s",path="%s",status_class="%s"} %d'
                    % (method, path, status_class, count)
                )

            lines.extend(
                [
                    "# HELP coyote3_api_request_duration_ms_sum Cumulative API request duration in milliseconds.",
                    "# TYPE coyote3_api_request_duration_ms_sum counter",
                ]
            )
            for (method, path), value in sorted(self._latency_ms_sum.items()):
                lines.append(
                    'coyote3_api_request_duration_ms_sum{method="%s",path="%s"} %.6f'
                    % (method, path, value)
                )

            lines.extend(
                [
                    "# HELP coyote3_api_request_duration_ms_count API request observations for duration metric.",
                    "# TYPE coyote3_api_request_duration_ms_count counter",
                ]
            )
            for (method, path), count in sorted(self._latency_ms_count.items()):
                lines.append(
                    'coyote3_api_request_duration_ms_count{method="%s",path="%s"} %d'
                    % (method, path, count)
                )

            lines.extend(
                [
                    "# HELP coyote3_api_rate_limited_total API requests rejected by rate limiter.",
                    "# TYPE coyote3_api_rate_limited_total counter",
                ]
            )
            for path, count in sorted(self._rate_limited_total.items()):
                lines.append('coyote3_api_rate_limited_total{path="%s"} %d' % (path, count))
            lines.extend(
                [
                    "# HELP coyote3_operation_total Application operations by name and outcome.",
                    "# TYPE coyote3_operation_total counter",
                ]
            )
            for (operation, outcome), count in sorted(self._operations_total.items()):
                lines.append(
                    'coyote3_operation_total{operation="%s",outcome="%s"} %d'
                    % (operation, outcome, count)
                )
            lines.extend(
                [
                    "# HELP coyote3_operation_duration_ms_sum Cumulative application operation duration.",
                    "# TYPE coyote3_operation_duration_ms_sum counter",
                ]
            )
            for operation, value in sorted(self._operation_duration_ms_sum.items()):
                lines.append(
                    'coyote3_operation_duration_ms_sum{operation="%s"} %.6f' % (operation, value)
                )
            lines.extend(
                [
                    "# HELP coyote3_operation_duration_ms_count Application operation observations.",
                    "# TYPE coyote3_operation_duration_ms_count counter",
                ]
            )
            for operation, count in sorted(self._operation_duration_ms_count.items()):
                lines.append(
                    'coyote3_operation_duration_ms_count{operation="%s"} %d' % (operation, count)
                )
            lines.extend(
                [
                    "# HELP coyote3_startup_phase_duration_ms Latest startup phase duration.",
                    "# TYPE coyote3_startup_phase_duration_ms gauge",
                ]
            )
            for phase, value in sorted(self._startup_phase_duration_ms.items()):
                lines.append('coyote3_startup_phase_duration_ms{phase="%s"} %.6f' % (phase, value))
            lines.append("")
            return "\n".join(lines)


_STORE = _ApiMetricsStore()


def observe_request(*, method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Record a request in the process-local metrics store.

    Args:
        method: HTTP method, uppercased for aggregation.
        path: Request path label.
        status_code: HTTP status, aggregated by status class.
        duration_ms: Elapsed milliseconds; negative values contribute zero.
    """
    _STORE.observe_request(
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def record_rate_limited(*, path: str) -> None:
    """Count a rate-limit rejection in the process-local store.

    Args:
        path: Rejected request's path label.
    """
    _STORE.inc_rate_limited(path=path)


def observe_operation(*, operation: str, outcome: str, duration_ms: float) -> None:
    """Record a bounded application operation metric."""
    _STORE.observe_operation(operation=operation, outcome=outcome, duration_ms=duration_ms)


def set_startup_phase_duration(*, phase: str, duration_ms: float) -> None:
    """Record the latest duration for a process startup phase."""
    _STORE.set_startup_phase_duration(phase=phase, duration_ms=duration_ms)


def render_prometheus_metrics() -> str:
    """Render the current process's accumulated Prometheus metrics.

    Returns:
        Newline-terminated Prometheus text containing counters and duration gauges.
    """
    return _STORE.render()
