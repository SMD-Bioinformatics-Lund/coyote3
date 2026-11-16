from __future__ import annotations

import pytest
from coyote.application.common.observability import measured_operation, timed_operation


def test_timed_operation_records_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    observations: list[tuple[str, str, float]] = []

    def observe(*, operation, outcome, duration_ms):
        observations.append((operation, outcome, duration_ms))

    with timed_operation("sample.success", observer=observe, sample="DEMO"):
        pass

    with pytest.raises(RuntimeError, match="failed"):
        with timed_operation("sample.failure", observer=observe):
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
        "coyote.application.common.observability.timed_operation",
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
