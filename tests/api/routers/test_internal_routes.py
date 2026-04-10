"""Behavior tests for internal API routes."""

from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import internal


def _admin_user():
    return SimpleNamespace(
        role="admin",
        roles=["superuser"],
        access_level=99999,
        permissions=["sample:edit:own"],
        denied_permissions=[],
        is_superuser=True,
    )


class _FakeUpload:
    """Minimal async upload stub for internal upload-route tests."""

    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self._buffer = BytesIO(payload)

    async def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    async def close(self) -> None:
        return None


def _ingest_service_stub(**methods):
    """Return a lightweight ingest-service stub for direct route calls."""
    return SimpleNamespace(**methods)


def test_get_role_levels_internal_returns_id_to_level_map(monkeypatch):
    """Test get role levels internal returns id to level map.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    roles_handler = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "admin", "level": 99}, {"role_id": "viewer"}]
    )

    payload = internal.get_role_levels_internal(request=object(), roles_handler=roles_handler)

    assert calls["token"] == 1
    assert payload["status"] == "ok"
    assert payload["role_levels"] == {"admin": 99, "viewer": 0}


def test_get_isgl_meta_internal_reads_adhoc_and_display_name(monkeypatch):
    """Test get isgl meta internal reads adhoc and display name.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    gene_list_handler = SimpleNamespace(
        is_isgl_adhoc=lambda _isgl_id: True,
        get_isgl_display_name=lambda _isgl_id: "Focus Panel",
    )

    payload = internal.get_isgl_meta_internal(
        "isgl123", request=object(), gene_list_handler=gene_list_handler
    )

    assert calls["token"] == 1
    assert payload == {
        "status": "ok",
        "isgl_id": "isgl123",
        "is_adhoc": True,
        "display_name": "Focus Panel",
    }


def test_ingest_sample_bundle_internal_accepts_spec(monkeypatch):
    """Test sample-bundle ingest route forwards structured spec payload."""
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )

    def _ingest(payload, *, allow_update=False, increment=False):
        calls["payload"] = payload
        calls["allow_update"] = allow_update
        calls["increment"] = increment
        return {
            "status": "ok",
            "sample_id": "abc",
            "sample_name": "S1",
            "written": {"snvs": 1},
            "data_counts": {"snvs": 1},
        }

    payload = internal.InternalIngestSampleBundleRequest(
        sample={
            "name": "S1",
            "assay": "assay_1",
            "subpanel": None,
            "profile": "testing",
            "genome_build": 38,
            "case_id": "CASE_1",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipe",
            "pipeline_version": "v1",
            "vcf_files": "/tmp/a.vcf",
        },
        increment=True,
    )
    response = internal.ingest_sample_bundle_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=_ingest_service_stub(ingest_sample_bundle=_ingest),
    )

    assert calls["payload"]["name"] == "S1"
    assert calls["payload"]["genome_build"] == 38
    assert calls["payload"]["vcf_files"] == "/tmp/a.vcf"
    assert calls["increment"] is True
    assert response["status"] == "ok"


def test_ingest_sample_bundle_internal_accepts_yaml(monkeypatch):
    """Test sample-bundle ingest route accepts YAML request body."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    ingest_service = _ingest_service_stub(
        parse_yaml_payload=lambda text: {
            "name": "S2",
            "vcf_files": "/tmp/s2.vcf",
            "from_yaml": text,
        },
        ingest_sample_bundle=lambda payload, *, allow_update=False, increment=False: {
            "status": "ok",
            "sample_id": "def",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        },
    )

    payload = internal.InternalIngestSampleBundleRequest(yaml_content="name: S2")
    response = internal.ingest_sample_bundle_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=ingest_service,
    )

    assert response["sample_name"] == "S2"


def test_ingest_sample_bundle_internal_rejects_invalid_shape(monkeypatch):
    """Test sample-bundle ingest route rejects missing/duplicate body forms."""
    empty_payload = internal.InternalIngestSampleBundleRequest()
    try:
        internal.ingest_sample_bundle_internal(
            payload=empty_payload,
            user=_admin_user(),
            ingest_service=_ingest_service_stub(),
        )
        assert False, "Expected HTTPException for empty payload"
    except HTTPException as exc:
        assert "spec" in str(exc)

    dual_payload = internal.InternalIngestSampleBundleRequest(
        sample={
            "name": "X",
            "assay": "assay_1",
            "subpanel": None,
            "profile": "testing",
            "case_id": "CASE_X",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipe",
            "pipeline_version": "v1",
            "vcf_files": "/tmp/x.vcf",
        },
        yaml_content="name: X",
    )
    try:
        internal.ingest_sample_bundle_internal(
            payload=dual_payload,
            user=_admin_user(),
            ingest_service=_ingest_service_stub(),
        )
        assert False, "Expected HTTPException for duplicate payload forms"
    except HTTPException as exc:
        assert "only one" in str(exc)


def test_ingest_sample_bundle_internal_requires_sample_edit_own_permission_for_update(monkeypatch):
    """Test update mode requires authenticated user with sample:edit:own permission."""
    calls = {"enforced": 0, "allow_update": None}
    monkeypatch.setattr(
        internal,
        "_enforce_access",
        lambda _user, permission=None, min_level=None, min_role=None: calls.__setitem__(
            "enforced", 1
        ),
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )

    def _ingest(payload, *, allow_update=False, increment=False):
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "upd-1",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        }

    payload = internal.InternalIngestSampleBundleRequest(
        sample={
            "name": "S3",
            "assay": "assay_1",
            "subpanel": None,
            "profile": "testing",
            "case_id": "CASE_3",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipe",
            "pipeline_version": "v1",
            "vcf_files": "/tmp/s3.vcf",
        },
        update_existing=True,
    )
    response = internal.ingest_sample_bundle_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=_ingest_service_stub(ingest_sample_bundle=_ingest),
    )
    assert calls["enforced"] == 0
    assert calls["allow_update"] is True
    assert response["sample_id"] == "upd-1"


def test_ingest_collection_document_internal_forwards_payload(monkeypatch):
    """Single collection ingest route should forward request payload."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    ingest_service = _ingest_service_stub(
        insert_collection_document=lambda *, collection, document, ignore_duplicate=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": "abc123",
        }
    )
    payload = internal.InternalCollectionInsertRequest(
        collection="hgnc_genes",
        document={"hgnc_id": "HGNC:5", "hgnc_symbol": "A1BG"},
    )
    monkeypatch.setattr(internal, "_enforce_collection_permission", lambda **_: None)
    response = internal.ingest_collection_document_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=ingest_service,
    )
    assert response["collection"] == "hgnc_genes"
    assert response["inserted_count"] == 1


def test_ingest_collection_documents_internal_forwards_payload(monkeypatch):
    """Bulk collection ingest route should forward request payload."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    ingest_service = _ingest_service_stub(
        insert_collection_documents=lambda *, collection, documents, ignore_duplicates=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": len(documents),
            "inserted_id": None,
        }
    )
    payload = internal.InternalCollectionBulkInsertRequest(
        collection="hgnc_genes",
        documents=[
            {"hgnc_id": "HGNC:5", "hgnc_symbol": "A1BG"},
            {"hgnc_id": "HGNC:6", "hgnc_symbol": "A1CF"},
        ],
    )
    monkeypatch.setattr(internal, "_enforce_collection_permission", lambda **_: None)
    response = internal.ingest_collection_documents_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=ingest_service,
    )
    assert response["collection"] == "hgnc_genes"
    assert response["inserted_count"] == 2


def test_list_supported_ingest_collections_internal(monkeypatch):
    """List supported ingest collections route should expose registered collection names."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    ingest_service = _ingest_service_stub(
        list_supported_collections=lambda: ["asp_configs", "hgnc_genes", "samples"]
    )

    response = internal.list_supported_ingest_collections_internal(
        _user=_admin_user(),
        ingest_service=ingest_service,
    )
    assert response["status"] == "ok"
    assert response["collections"] == ["asp_configs", "hgnc_genes", "samples"]


def test_upsert_collection_document_internal_forwards_payload(monkeypatch):
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(internal, "_enforce_collection_permission", lambda **_: None)
    ingest_service = _ingest_service_stub(
        upsert_collection_document=lambda *, collection, match, document, upsert=False: {
            "status": "ok",
            "collection": collection,
            "matched_count": 1,
            "modified_count": 1,
            "upserted_id": None,
        }
    )
    payload = internal.InternalCollectionUpsertRequest(
        collection="asp_configs",
        match={"aspc_id": "assay_1:prod"},
        document={"aspc_id": "assay_1:prod"},
        upsert=True,
    )
    response = internal.upsert_collection_document_internal(
        payload=payload,
        user=_admin_user(),
        ingest_service=ingest_service,
    )
    assert response["collection"] == "asp_configs"
    assert response["matched_count"] == 1


def test_ingest_sample_bundle_upload_internal_stages_files(monkeypatch):
    """Multipart upload route should stage referenced files and ingest bundle."""
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "parse_yaml_payload",
        lambda _text: {
            "name": "UPLOAD_SAMPLE",
            "assay": "assay_1",
            "profile": "testing",
            "genome_build": 38,
            "case_id": "CASE_UPLOAD",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipeline",
            "pipeline_version": "v1",
            "vcf_files": "generic_case_control.final.filtered.vcf",
            "cnv": "generic_case_control.cnvs.merged.json",
        },
    )

    def _ingest(payload, *, allow_update=False, increment=False):
        calls["payload"] = payload
        calls["allow_update"] = allow_update
        calls["increment"] = increment
        return {
            "status": "ok",
            "sample_id": "upload-1",
            "sample_name": payload["name"],
            "written": {"snvs": 1},
            "data_counts": {"snvs": 1},
        }

    ingest_service = _ingest_service_stub(
        parse_yaml_payload=lambda _text: {
            "name": "UPLOAD_SAMPLE",
            "assay": "assay_1",
            "profile": "testing",
            "genome_build": 38,
            "case_id": "CASE_UPLOAD",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipeline",
            "pipeline_version": "v1",
            "vcf_files": "generic_case_control.final.filtered.vcf",
            "cnv": "generic_case_control.cnvs.merged.json",
        },
        ingest_sample_bundle=_ingest,
    )

    yaml_upload = _FakeUpload(filename="ingest.yaml", payload=b"name: UPLOAD_SAMPLE")
    files = [
        _FakeUpload(
            filename="generic_case_control.final.filtered.vcf",
            payload=b"##fileformat=VCFv4.2\n",
        ),
        _FakeUpload(
            filename="generic_case_control.cnvs.merged.json",
            payload=b"[]",
        ),
    ]

    response = asyncio.run(
        internal.ingest_sample_bundle_upload_internal(
            yaml_file=yaml_upload,
            data_files=files,
            update_existing=False,
            increment=True,
            user=_admin_user(),
            ingest_service=ingest_service,
        )
    )
    assert response["status"] == "ok"
    payload = calls["payload"]
    assert isinstance(payload, dict)
    runtime = payload.get("_runtime_files")
    assert isinstance(runtime, dict)
    assert runtime["vcf_files"].endswith(".vcf")
    assert runtime["cnv"].endswith(".json")
    checksums = payload.get("_uploaded_file_checksums")
    assert isinstance(checksums, dict)
    assert "vcf_files" in checksums
    assert "cnv" in checksums
    assert calls["increment"] is True
    assert calls["allow_update"] is False


def test_ingest_sample_bundle_upload_internal_rejects_missing_file(monkeypatch):
    """Multipart upload route should fail when YAML references non-uploaded files."""
    ingest_service = _ingest_service_stub(
        parse_yaml_payload=lambda _text: {
            "name": "UPLOAD_SAMPLE",
            "assay": "assay_1",
            "profile": "testing",
            "genome_build": 38,
            "case_id": "CASE_UPLOAD",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipeline",
            "pipeline_version": "v1",
            "vcf_files": "required.vcf",
        }
    )

    yaml_upload = _FakeUpload(filename="ingest.yaml", payload=b"name: UPLOAD_SAMPLE")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            internal.ingest_sample_bundle_upload_internal(
                yaml_file=yaml_upload,
                data_files=[],
                update_existing=False,
                increment=True,
                user=_admin_user(),
                ingest_service=ingest_service,
            )
        )
    assert exc_info.value.status_code == 400
    assert "Missing files for YAML references" in str(exc_info.value)


def test_ingest_collection_upload_internal_insert(monkeypatch):
    """Multipart collection upload should validate JSON object for insert mode."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(internal, "_enforce_collection_permission", lambda **_: None)
    ingest_service = _ingest_service_stub(
        insert_collection_document=lambda *, collection, document, ignore_duplicate=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": "seed-1",
        }
    )
    upload = _FakeUpload(
        filename="users.json",
        payload=b'{"username":"analyst1","email":"analyst@example.org"}',
    )
    response = asyncio.run(
        internal.ingest_collection_upload_internal(
            collection="users",
            mode="insert",
            documents_file=upload,
            match_json=None,
            user=_admin_user(),
            ingest_service=ingest_service,
        )
    )
    assert response["status"] == "ok"
    assert response["collection"] == "users"
    assert response["mode"] == "insert"
    assert response["inserted_count"] == 1


def test_ingest_collection_upload_internal_bulk(monkeypatch):
    """Multipart collection upload should accept JSON arrays for bulk mode."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(internal, "_enforce_collection_permission", lambda **_: None)
    ingest_service = _ingest_service_stub(
        insert_collection_documents=lambda *, collection, documents, ignore_duplicates=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": len(documents),
        }
    )
    upload = _FakeUpload(
        filename="roles.json",
        payload=b'[{"role_id":"viewer","level":10},{"role_id":"analyst","level":20}]',
    )
    response = asyncio.run(
        internal.ingest_collection_upload_internal(
            collection="roles",
            mode="bulk",
            documents_file=upload,
            match_json=None,
            user=_admin_user(),
            ingest_service=ingest_service,
        )
    )
    assert response["status"] == "ok"
    assert response["collection"] == "roles"
    assert response["mode"] == "bulk"
    assert response["inserted_count"] == 2


def test_ingest_collection_upload_internal_upsert_requires_match_json(monkeypatch):
    """Multipart collection upload should enforce match_json in upsert mode."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    upload = _FakeUpload(
        filename="permissions.json",
        payload=b'{"permission_id":"sample:edit:own","name":"Edit sample"}',
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            internal.ingest_collection_upload_internal(
                collection="permissions",
                mode="upsert",
                documents_file=upload,
                match_json=None,
                user=_admin_user(),
                ingest_service=_ingest_service_stub(),
            )
        )
    assert exc_info.value.status_code == 400
    assert "match_json" in str(exc_info.value)


def test_get_prometheus_metrics_internal_requires_internal_token(monkeypatch):
    calls = {"checked": 0}
    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("checked", 1)
    )
    monkeypatch.setattr(
        internal,
        "render_prometheus_metrics",
        lambda: "# HELP coyote3_api_requests_total test\n",
    )

    response = internal.get_prometheus_metrics_internal(request=object())

    assert calls["checked"] == 1
    assert response.status_code == 200
    assert "coyote3_api_requests_total" in response.body.decode("utf-8")
