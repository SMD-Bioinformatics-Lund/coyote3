"""The common transaction boundary requires sessions and passes durable options."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.infra.mongo.transactions import run_transaction


def test_transaction_passes_session_and_snapshot_majority_options():
    session = MagicMock()
    session.__enter__.return_value = session
    seen = []

    def execute(operation, **options):
        assert options["read_concern"].document == {"level": "snapshot"}
        assert options["write_concern"].document == {"w": "majority", "j": True}
        return operation(session)

    session.with_transaction.side_effect = execute
    client = SimpleNamespace(start_session=lambda: session)
    assert run_transaction(client, lambda active: seen.append(active) or "committed") == "committed"
    assert seen == [session]


def test_session_failure_never_runs_unprotected_callback():
    def unavailable():
        raise RuntimeError("synthetic unavailable session")

    with pytest.raises(RuntimeError, match="unavailable session"):
        run_transaction(
            SimpleNamespace(start_session=unavailable),
            lambda session: pytest.fail("unprotected write"),
        )


def test_transaction_failure_is_not_retried_without_session():
    session = MagicMock()
    session.__enter__.return_value = session
    session.with_transaction.side_effect = RuntimeError("synthetic transaction failure")
    with pytest.raises(RuntimeError, match="transaction failure"):
        run_transaction(SimpleNamespace(start_session=lambda: session), lambda active: None)
    assert session.with_transaction.call_count == 1
