"""Recovery boundaries for committed report artifact publication."""

from hashlib import sha256
from types import SimpleNamespace

import pytest

from coyote3.application.reporting.artifact_finalization import (
    finalize_artifacts,
    finalize_pending_reports,
)


def artifact(tmp_path):
    """Create one durable staged synthetic artifact."""
    staging = tmp_path / "r.html.pending"
    staging.write_bytes(b"report")
    return {
        "path": str(tmp_path / "r.html"),
        "staging_path": str(staging),
        "checksum": sha256(b"report").hexdigest(),
        "status": "pending",
    }


def test_finalization_is_repeatable_after_file_publication(tmp_path):
    row = artifact(tmp_path)
    finalize_artifacts([row], root=tmp_path)
    finalize_artifacts([row], root=tmp_path)
    assert (tmp_path / "r.html").read_bytes() == b"report"
    assert not (tmp_path / "r.html.pending").exists()


@pytest.mark.parametrize("corrupt", ["r.html", "r.html.pending"])
def test_finalization_preserves_corrupt_or_conflicting_content(tmp_path, corrupt):
    row = artifact(tmp_path)
    (tmp_path / corrupt).write_bytes(b"different")
    with pytest.raises(ValueError, match="checksum"):
        finalize_artifacts([row], root=tmp_path)
    assert (tmp_path / corrupt).read_bytes() == b"different"


def test_finalization_rejects_outside_storage(tmp_path):
    row = artifact(tmp_path)
    row["path"] = str(tmp_path.parent / "outside.html")
    with pytest.raises(ValueError, match="outside"):
        finalize_artifacts([row], root=tmp_path)


def test_worker_recovers_committed_artifacts_and_defers_unavailable_files(tmp_path):
    row = artifact(tmp_path)
    completed = []
    repository = SimpleNamespace(
        pending_artifacts=lambda **kwargs: [{"_id": "report", "artifacts": [row]}],
        complete_artifacts=lambda oid: completed.append(oid) or True,
    )
    assert finalize_pending_reports(repository, root=tmp_path) == {"completed": 1, "deferred": 0}
    assert completed == ["report"]
    (tmp_path / "r.html").unlink()
    assert finalize_pending_reports(repository, root=tmp_path) == {"completed": 0, "deferred": 1}


def test_concurrent_sample_deletion_does_not_leave_published_files(tmp_path):
    row = artifact(tmp_path)
    repository = SimpleNamespace(
        pending_artifacts=lambda **kwargs: [{"_id": "report", "artifacts": [row]}],
        complete_artifacts=lambda oid: False,
    )
    finalize_pending_reports(repository, root=tmp_path)
    assert list(tmp_path.iterdir()) == []
