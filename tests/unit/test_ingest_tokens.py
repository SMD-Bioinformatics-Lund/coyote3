"""Expiring pipeline credentials reject tampering and cross-environment use."""

import pytest

from api.security import ingest_tokens


def test_token_expiry_and_audience(monkeypatch):
    monkeypatch.setattr(ingest_tokens.time, "time", lambda: 1000)
    token = ingest_tokens.issue_token("synthetic-key", "development", 1)
    assert ingest_tokens.verify_token(token, "synthetic-key", "dev")["scope"] == "sample-ingest"
    for key, environment in [("wrong", "dev"), ("synthetic-key", "prod")]:
        with pytest.raises(ValueError):
            ingest_tokens.verify_token(token, key, environment)
    with pytest.raises(ValueError):
        ingest_tokens.verify_token(token + "invalid", "synthetic-key", "dev")
    monkeypatch.setattr(ingest_tokens.time, "time", lambda: 4600)
    with pytest.raises(ValueError):
        ingest_tokens.verify_token(token, "synthetic-key", "dev")


@pytest.mark.parametrize("hours", [0, -1, 721])
def test_invalid_lifetime(hours):
    with pytest.raises(ValueError):
        ingest_tokens.issue_token("synthetic-key", "dev", hours)
