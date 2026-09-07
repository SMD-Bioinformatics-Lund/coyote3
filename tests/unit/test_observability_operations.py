from __future__ import annotations

import pytest

from api.infra.observability.operations import measured_operation, timed_operation
from api.infra.observability.prometheus_metrics import _ApiMetricsStore


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
    assert 'coyote3_api_rate_limited_total{path="/samples"} 1' in rendered


def test_timed_operation_records_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    observations: list[tuple[str, str, float]] = []
    monkeypatch.setattr(
        "api.infra.observability.operations.observe_operation",
        lambda *, operation, outcome, duration_ms: observations.append(
            (operation, outcome, duration_ms)
        ),
    )

    with timed_operation("sample.success", sample="DEMO"):
        pass

    with pytest.raises(RuntimeError, match="failed"):
        with timed_operation("sample.failure"):
            raise RuntimeError("failed")

    assert observations[0][0:2] == ("sample.success", "success")
    assert observations[1][0:2] == ("sample.failure", "failure")
    assert all(item[2] >= 0 for item in observations)


def test_measured_operation_preserves_return_value_and_function_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    class _Context:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(
        "api.infra.observability.operations.timed_operation",
        lambda operation, **_context: observed.append(operation) or _Context(),
    )

    @measured_operation("query.example")
    def example(value: int) -> int:
        """Example operation."""
        return value + 1

    assert example(3) == 4
    assert example.__name__ == "example"
    assert example.__doc__ == "Example operation."
    assert observed == ["query.example"]
