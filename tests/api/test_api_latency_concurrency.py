"""Concurrency and latency smoke tests for core API health route."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from time import perf_counter

from api.routers import health


def test_health_endpoint_concurrency_smoke():
    """Health endpoint should sustain concurrent in-process requests.

    This is not a full load/performance benchmark; it is a guardrail that
    catches severe regressions in request handling behavior.
    """

    latencies_ms: list[float] = []
    started = perf_counter()

    def _hit() -> dict[str, str]:
        t0 = perf_counter()
        payload = health.health()
        latencies_ms.append((perf_counter() - t0) * 1000.0)
        return payload

    with ThreadPoolExecutor(max_workers=40) as executor:
        payloads = list(executor.map(lambda _: _hit(), range(200)))
    total_ms = (perf_counter() - started) * 1000.0

    assert all(payload == {"status": "ok"} for payload in payloads)
    assert len(latencies_ms) == 200
    # Smoke threshold: average latency should remain in a healthy local-test range.
    assert mean(latencies_ms) < 400.0
    # Overall wall time should remain bounded under moderate local concurrency.
    assert total_ms < 10000.0
