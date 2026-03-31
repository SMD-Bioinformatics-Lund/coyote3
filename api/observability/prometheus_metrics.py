"""Minimal Prometheus text metrics for API request observability."""

from __future__ import annotations

import threading
from collections import defaultdict


def _label(value: str) -> str:
    return str(value or "").replace("\\", "_").replace('"', "_").replace("\n", "_")[:120]


class _ApiMetricsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_total: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self._latency_ms_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._latency_ms_count: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._rate_limited_total: defaultdict[str, int] = defaultdict(int)

    def observe_request(
        self, *, method: str, path: str, status_code: int, duration_ms: float
    ) -> None:
        status_class = f"{int(status_code) // 100}xx"
        key = (_label(method.upper()), _label(path), _label(status_class))
        latency_key = (_label(method.upper()), _label(path))
        with self._lock:
            self._requests_total[key] += 1
            self._latency_ms_sum[latency_key] += max(float(duration_ms), 0.0)
            self._latency_ms_count[latency_key] += 1

    def inc_rate_limited(self, *, path: str) -> None:
        with self._lock:
            self._rate_limited_total[_label(path)] += 1

    def render(self) -> str:
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
            lines.append("")
            return "\n".join(lines)


_STORE = _ApiMetricsStore()


def observe_request(*, method: str, path: str, status_code: int, duration_ms: float) -> None:
    _STORE.observe_request(
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def record_rate_limited(*, path: str) -> None:
    _STORE.inc_rate_limited(path=path)


def render_prometheus_metrics() -> str:
    return _STORE.render()
