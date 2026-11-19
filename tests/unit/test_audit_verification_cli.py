"""Scheduled audit acceptance fails closed without independent, fresh evidence."""

import json
from unittest.mock import MagicMock, Mock

import pytest

from scripts.database import verify_audit_chain as cli


def test_schedule_check_requires_independent_anchor_before_connecting(monkeypatch):
    client = Mock()
    monkeypatch.setattr(cli, "MongoClient", client)
    monkeypatch.setattr("sys.argv", ["verify-audit", "--check-schedule"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    client.assert_not_called()


@pytest.mark.parametrize("archive", ["", "missing"])
def test_disabled_or_missing_export_fails_without_database_access(monkeypatch, tmp_path, archive):
    client = Mock()
    monkeypatch.setattr(cli, "MongoClient", client)
    monkeypatch.setenv("IDENTITY_DB", "synthetic_identity")
    monkeypatch.setenv("AUDIT_CHECKPOINT_DIRECTORY", str(tmp_path / archive) if archive else "")
    anchor = tmp_path / "trusted.json"
    anchor.write_text('{"valid": true, "chains": []}')
    monkeypatch.setattr(
        "sys.argv", ["verify-audit", "--check-schedule", "--checkpoint", str(anchor)]
    )
    assert cli.main() == 1
    client.assert_not_called()


def test_fresh_export_does_not_override_independent_anchor_failure(monkeypatch, tmp_path, capsys):
    anchor = tmp_path / "trusted.json"
    anchor.write_text('{"valid": true, "chains": []}')
    monkeypatch.setenv("IDENTITY_DB", "synthetic_identity")
    monkeypatch.setenv("AUDIT_CHECKPOINT_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(cli, "latest_checkpoint", Mock(return_value=({"valid": True}, 30)))
    monkeypatch.setattr(cli, "mongo_uri", Mock(return_value="mongodb://synthetic.invalid"))
    monkeypatch.setattr(cli, "MongoClient", MagicMock())
    verify = Mock(side_effect=[{"valid": False, "errors": ["anchor mismatch"]}, {"valid": True}])
    monkeypatch.setattr(cli, "verify_chain", verify)
    monkeypatch.setattr(
        "sys.argv", ["verify-audit", "--check-schedule", "--checkpoint", str(anchor)]
    )
    assert cli.main() == 1
    assert verify.call_count == 2
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is False
    assert result["scheduled_export"]["valid"] is True
