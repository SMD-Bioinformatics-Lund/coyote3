"""Archival checkpoint verification and preservation of earlier exports."""

import json

import pytest
from coyote_mongo.audit_checkpoints import archive_checkpoint


def test_checkpoint_archive_preserves_previous_files_and_rejects_failed_verification(tmp_path):
    checkpoint = {"valid": True, "errors": [], "chains": [], "unchained_legacy_events": 0}
    first = archive_checkpoint(checkpoint, tmp_path)
    second = archive_checkpoint(checkpoint, tmp_path)
    assert first != second
    assert json.loads(first.read_text()) == checkpoint
    assert first.stat().st_mode & 0o777 == 0o440
    with pytest.raises(ValueError, match="Failed audit verification"):
        archive_checkpoint({**checkpoint, "valid": False}, tmp_path)
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(ValueError, match="existing dedicated directory"):
        archive_checkpoint(checkpoint, tmp_path / "not-mounted")


def test_scheduled_checkpoint_must_be_present_fresh_and_successful(tmp_path):
    import os
    from datetime import datetime, timezone

    from coyote_mongo.audit_checkpoints import latest_checkpoint

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="No scheduled"):
        latest_checkpoint(tmp_path, max_age_seconds=7200, now=now)
    checkpoint = {"valid": True, "chains": []}
    path = archive_checkpoint(checkpoint, tmp_path)
    os.utime(path, (now.timestamp() - 3600, now.timestamp() - 3600))
    assert latest_checkpoint(tmp_path, max_age_seconds=7200, now=now) == (checkpoint, 3600)
    with pytest.raises(ValueError, match="stale"):
        latest_checkpoint(tmp_path, max_age_seconds=1800, now=now)
    os.utime(path, (now.timestamp() + 120, now.timestamp() + 120))
    with pytest.raises(ValueError, match="future"):
        latest_checkpoint(tmp_path, max_age_seconds=7200, now=now)


def test_new_invalid_checkpoint_cannot_be_hidden_by_an_older_success(tmp_path):
    from coyote_mongo.audit_checkpoints import latest_checkpoint

    archive_checkpoint({"valid": True, "chains": []}, tmp_path)
    failed = tmp_path / "audit-failed.json"
    failed.write_text('{"valid": false}')
    with pytest.raises(ValueError, match="not a successful"):
        latest_checkpoint(tmp_path, max_age_seconds=7200)
