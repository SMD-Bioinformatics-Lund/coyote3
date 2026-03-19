"""Concurrency and latency smoke tests for core API health route."""

from __future__ import annotations

import asyncio
from statistics import mean
from time import perf_counter

import httpx

from api.main import app


def test_health_endpoint_concurrency_smoke():
    """Health endpoint should sustain concurrent in-process requests.

    This is not a full load/performance benchmark; it is a guardrail that
    catches severe regressions in request handling behavior.
    """

    async def _run() -> tuple[list[int], list[float], float]:
        latencies_ms: list[float] = []
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Warm-up request to avoid one-time app startup costs skewing latency assertions.
            warmup = await client.get("/api/v1/health")
            assert warmup.status_code == 200
            started = perf_counter()
            sem = asyncio.Semaphore(40)

            async def _hit() -> int:
                async with sem:
                    t0 = perf_counter()
                    resp = await client.get("/api/v1/health")
                    latencies_ms.append((perf_counter() - t0) * 1000.0)
                    return resp.status_code

            statuses = await asyncio.gather(*[_hit() for _ in range(200)])
        total_ms = (perf_counter() - started) * 1000.0
        return statuses, latencies_ms, total_ms

    statuses, latencies_ms, total_ms = asyncio.run(_run())

    assert all(code == 200 for code in statuses)
    assert len(latencies_ms) == 200
    # Smoke threshold: average latency should remain in a healthy local-test range.
    assert mean(latencies_ms) < 400.0
    # Overall wall time should remain bounded under moderate local concurrency.
    assert total_ms < 10000.0
