"""Registered artifact paths cannot escape the mounted sample data root."""

import pytest

from api.application.common.file_access import resolve_sample_file_path
from api.domain.core.exceptions import AppError


def test_artifact_root_rejects_external_paths_and_symlinks(tmp_path, monkeypatch):
    """Existing files outside the data mount remain inaccessible through symlinks."""
    root = tmp_path / "data"
    root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"synthetic")
    inside = root / "inside.png"
    inside.write_bytes(b"synthetic")
    link = root / "link.png"
    link.symlink_to(outside)
    monkeypatch.setattr("api.application.common.file_access.DATA_CONTAINER_ROOT", root)
    assert resolve_sample_file_path(str(inside)) == inside
    for candidate in (outside, link, root / "missing.png"):
        with pytest.raises(AppError):
            resolve_sample_file_path(str(candidate))
