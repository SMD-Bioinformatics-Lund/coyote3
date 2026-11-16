"""Unit tests for internal ingestion service helpers and orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_upload_preflight_runs_before_archive_and_file_policy(tmp_path):
    from io import BytesIO

    from coyote.application.ingest.upload_bundle import prepare_uploaded_bundle
    from fastapi import UploadFile

    def reject(payload):
        assert payload["name"] == "CASE"
        raise ValueError("Sample already exists; set increment=true")

    service = SimpleNamespace(
        parse_yaml_payload=lambda _: {"name": "CASE"},
        _assay_file_policy=lambda **_: pytest.fail("File policy ran before preflight"),
    )
    archive = BytesIO(b"unread archive")
    with pytest.raises(ValueError, match="increment=true"):
        prepare_uploaded_bundle(
            yaml_file=UploadFile(filename="sample.yaml", file=BytesIO(b"name: CASE")),
            data_archive=UploadFile(filename="data.zip", file=archive),
            staging_dir=tmp_path,
            ingest_service=service,
            preflight=reject,
        )
    assert archive.tell() == 0
    assert not list(tmp_path.iterdir())
