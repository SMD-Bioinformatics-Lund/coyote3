from __future__ import annotations

from coyote_api.infra.observability.prometheus_metrics import _ApiMetricsStore


def test_metrics_store_renders_requests_operations_and_startup_phases() -> None:
    store = _ApiMetricsStore()
    store.observe_request(method="get", path='/samples/"unsafe"', status_code=200, duration_ms=12.5)
    store.inc_rate_limited(path="/samples")
    store.observe_operation(operation="query.samples", outcome="success", duration_ms=7.25)
    store.set_startup_phase_duration(phase="mongo_indexes", duration_ms=41.0)

    rendered = store.render()

    assert 'method="GET"' in rendered
    assert 'path="/samples/_unsafe_"' in rendered
    assert 'operation="query.samples",outcome="success"' in rendered
    assert 'phase="mongo_indexes"} 41.000000' in rendered
    assert 'coyote4_api_rate_limited_total{path="/samples"} 1' in rendered
