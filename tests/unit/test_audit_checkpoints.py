"""Archival checkpoint verification and preservation of earlier exports."""

import json

import pytest

from api.infra.observability.audit_checkpoints import archive_checkpoint


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
