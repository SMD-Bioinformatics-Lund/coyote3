"""AuthN/AuthZ matrix tests for internal ingest routes."""

from __future__ import annotations

import io
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import mongomock
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.application.ingest.service import InternalIngestService
from api.infra.mongo.repositories.ingest_jobs import IngestJobsRepository
from api.interfaces.http.operations import internal as internal_router
from api.security import access
from api.security.access import ApiUser


@pytest.fixture(autouse=True)
def ingest_jobs(monkeypatch):
    jobs = IngestJobsRepository(
        SimpleNamespace(ingest_jobs_collection=mongomock.MongoClient().test.ingest_jobs)
    )
    monkeypatch.setattr(internal_router, "get_ingest_jobs_repository", lambda: jobs)
    return jobs


def _user(*, role: str, level: int, permissions: list[str] | None = None) -> ApiUser:
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role=role,
        roles=[role],
        access_level=level,
        permissions=list(permissions or []),
        asp_ids=["assay_1"],
        asp_groups=["hematology"],
        envs=["production"],
        asp_map={},
        auth_type=["local"],
    )


@pytest.mark.parametrize(
    "route,request_type",
    [
        (
            internal_router.enqueue_ingest_collection_document_internal,
            internal_router.InternalCollectionInsertRequest,
        ),
        (
            internal_router.enqueue_ingest_collection_documents_internal,
            internal_router.InternalCollectionBulkInsertRequest,
        ),
        (
            internal_router.enqueue_upsert_collection_document_internal,
            internal_router.InternalCollectionUpsertRequest,
        ),
    ],
)
def test_remote_async_collection_rejected_before_acceptance(
    monkeypatch, ingest_jobs, route, request_type
):
    monkeypatch.setattr(internal_router, "_enforce_collection_permission", lambda **kwargs: None)

    def reject_target(name):
        raise ValueError("Target requires synchronous ingestion")

    values = {"collection": "users"}
    if request_type is internal_router.InternalCollectionBulkInsertRequest:
        values["documents"] = [{"username": "synthetic"}]
    else:
        values["document"] = {"username": "synthetic"}
    if request_type is internal_router.InternalCollectionUpsertRequest:
        values["match"] = {"username": "synthetic"}
    with pytest.raises(HTTPException) as exc:
        route(
            payload=request_type(**values),
            user=_user(role="superuser", level=100),
            ingest_service=SimpleNamespace(validate_async_collection=reject_target),
        )
    assert exc.value.status_code == 400
    assert ingest_jobs.get_collection().count_documents({}) == 0


def _resolve_access_dependency(method: str, path: str):
    route = next(
        (
            entry
            for entry in internal_router.router.routes
            if getattr(entry, "path", "") == path and method in getattr(entry, "methods", set())
        ),
        None,
    )
    assert route is not None
    dep = next(
        (
            entry.call
            for entry in route.dependant.dependencies
            if getattr(entry.call, "__name__", "") == "dep"
        ),
        None,
    )
    assert dep is not None
    return dep


def _request_for(path: str, method: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


class _Upload:
    def __init__(self, *, filename: str, content: bytes):
        self.filename = filename
        self._handle = io.BytesIO(content)
        self.file = self._handle
        self.closed = False

    async def read(self, size: int = -1):
        return self._handle.read(size)

    async def close(self):
        self.closed = True


def _zip_upload(*entries: tuple[str, bytes]) -> _Upload:
    payload = io.BytesIO()
    with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return _Upload(filename="bundle.zip", content=payload.getvalue())


def test_internal_ingest_collection_requires_auth_and_admin(monkeypatch):
    """Collection ingest requires authenticated admin-level user."""
    monkeypatch.setattr(
        InternalIngestService,
        "insert_collection_document",
        lambda **_: {"status": "ok", "collection": "users", "inserted_count": 1},
    )
    dep = _resolve_access_dependency("POST", "/api/v1/internal/ingest/collection")
    request = _request_for("/api/v1/internal/ingest/collection", "POST")
    payload = internal_router.InternalCollectionInsertRequest(
        collection="users",
        document={
            "email": "admin@your-center.org",
            "role": "admin",
            "environments": ["production"],
        },
    )

    def _raise_unauth(_request):
        raise HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})

    monkeypatch.setattr(access, "_decode_session_user", _raise_unauth)
    with pytest.raises(HTTPException) as unauth_exc:
        next(dep(request))
    assert unauth_exc.value.status_code == 401

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="viewer", level=10),
    )
    with pytest.raises(HTTPException) as forbidden_exc:
        next(dep(request))
    assert forbidden_exc.value.status_code == 403

    monkeypatch.setattr(
        access,
        "_decode_session_user",
        lambda _request: _user(role="developer", level=9999, permissions=["user:create"]),
    )
    monkeypatch.setattr(access, "_enforce_access", lambda *_args, **_kwargs: None)
    user = next(dep(request))
    monkeypatch.setattr(internal_router, "_enforce_access", lambda *_args, **_kwargs: None)
    ingest_service = SimpleNamespace(
        insert_collection_document=lambda **_: {
            "status": "ok",
            "collection": "users",
            "inserted_count": 1,
        }
    )
    with pytest.raises(HTTPException) as identity_error:
        internal_router.ingest_collection_document_internal(
            payload=payload,
            user=user,
            ingest_service=ingest_service,
        )
    assert identity_error.value.status_code == 403


def test_internal_ingest_collection_status_reports_empty_and_rejects_unknown_collection():
    user = _user(
        role="developer",
        level=9999,
        permissions=["internal.ingest:manage"],
    )
    result = internal_router.get_ingest_collection_status_internal(
        collection="hgnc_genes",
        user=user,
        ingest_service=SimpleNamespace(collection_document_count=lambda _collection: 0),
    )

    assert result == {
        "status": "ok",
        "collection": "hgnc_genes",
        "document_count": 0,
        "empty": True,
    }

    def _unsupported(_collection):
        raise ValueError("Unsupported collection: unknown")

    with pytest.raises(HTTPException) as exc_info:
        internal_router.get_ingest_collection_status_internal(
            collection="unknown",
            user=user,
            ingest_service=SimpleNamespace(collection_document_count=_unsupported),
        )
    assert exc_info.value.status_code == 400


def test_internal_ingest_sample_bundle_update_requires_sample_edit_own_permission(monkeypatch):
    """Update mode requires sample:edit:own for developer-level operators."""
    calls: dict[str, object] = {}

    def _ingest(payload, *, allow_update=False, increment=False):
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "S1",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        }

    monkeypatch.setattr(InternalIngestService, "ingest_sample_bundle", _ingest)
    payload = internal_router.InternalIngestSampleBundleRequest(
        sample={
            "name": "seed_sample",
            "asp_id": "assay_1",
            "subpanel_id": None,
            "environment": "testing",
            "case_id": "CASE_001",
            "sample_no": 1,
            "paired": False,
            "sequencing_scope": "panel",
            "omics_layer": "dna",
            "pipeline": "pipe",
            "pipeline_version": "v1",
            "vcf_files": "/tmp/demo.vcf",
        },
        update_existing=True,
    )

    monkeypatch.setattr(
        internal_router,
        "_enforce_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=403)),
    )
    with pytest.raises(HTTPException) as missing_perm_exc:
        internal_router.ingest_sample_bundle_internal(
            payload=payload,
            user=_user(role="developer", level=50, permissions=[]),
            ingest_service=SimpleNamespace(
                parse_yaml_payload=lambda raw: raw,
                ingest_sample_bundle=_ingest,
            ),
        )
    assert missing_perm_exc.value.status_code == 403

    monkeypatch.setattr(internal_router, "_enforce_access", lambda *_args, **_kwargs: None)

    response = internal_router.ingest_sample_bundle_internal(
        payload=payload,
        user=_user(role="developer", level=50, permissions=["sample:edit:own"]),
        ingest_service=SimpleNamespace(
            parse_yaml_payload=lambda raw: raw,
            ingest_sample_bundle=_ingest,
        ),
    )
    assert response["status"] == "ok"
    assert calls["allow_update"] is True


def test_internal_ingest_async_collection_enqueues_after_permission_check(monkeypatch, ingest_jobs):
    """Async collection ingest enqueues the Celery task after route-level permission checks."""
    captured: dict[str, object] = {}

    def _fake_apply_async(*, kwargs, queue, task_id):
        captured["kwargs"] = kwargs
        captured["queue"] = queue
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr(
        internal_router.insert_collection_document_task, "apply_async", _fake_apply_async
    )
    monkeypatch.setattr(internal_router, "_enforce_access", lambda *_args, **_kwargs: None)
    payload = internal_router.InternalCollectionInsertRequest(
        collection="users",
        document={"username": "new.user", "email": "new.user@example.org"},
        ignore_duplicate=True,
    )
    operator = _user(role="superuser", level=100, permissions=["user:create"])
    response = internal_router.enqueue_ingest_collection_document_internal(
        payload=payload,
        user=operator,
        ingest_service=SimpleNamespace(validate_async_collection=lambda name: None),
    )

    assert response == {
        "status": "accepted",
        "task_id": captured["kwargs"]["job_id"],
        "task_name": "api.tasks.ingest.insert_collection_document",
        "queue": "ingest",
    }
    assert captured["queue"] == "ingest"
    assert ingest_jobs.get(response["task_id"])["source_payload"] == {
        "collection": "users",
        "document": {"username": "new.user", "email": "new.user@example.org"},
        "ignore_duplicate": True,
    }


def test_internal_ingest_async_sample_bundle_enqueues_yaml_payload(monkeypatch, ingest_jobs):
    """Async sample-bundle ingest parses YAML on the API side and enqueues worker execution."""
    captured: dict[str, object] = {}

    def _fake_apply_async(*, kwargs, queue, task_id):
        captured["kwargs"] = kwargs
        captured["queue"] = queue
        return SimpleNamespace(id="task-sample")

    monkeypatch.setattr(internal_router.ingest_sample_bundle_task, "apply_async", _fake_apply_async)
    monkeypatch.setattr(internal_router, "_enforce_access", lambda *_args, **_kwargs: None)
    payload = internal_router.InternalIngestSampleBundleRequest(
        yaml_content="name: SAMPLE_1\nassay: assay_1\n",
        update_existing=True,
        increment=True,
    )
    response = internal_router.enqueue_ingest_sample_bundle_internal(
        payload=payload,
        user=_user(role="developer", level=50, permissions=["sample:edit:own"]),
        ingest_service=SimpleNamespace(
            parse_yaml_payload=lambda raw: {
                "name": "SAMPLE_1",
                "asp_id": "assay_1",
                "environment": "production",
            }
        ),
    )

    assert response["status"] == "accepted"
    assert response["task_id"] == captured["kwargs"]["job_id"]
    assert captured["queue"] == "ingest"
    job = ingest_jobs.get(response["task_id"])
    assert job["source_payload"] == {
        "name": "SAMPLE_1",
        "asp_id": "assay_1",
        "environment": "production",
    }
    assert job["update_existing"] is True
    assert job["increment"] is True


def test_internal_ingest_async_sample_bundle_upload_stages_files(
    monkeypatch, tmp_path, ingest_jobs
):
    """Async upload ingest stages uploaded files durably before enqueueing."""
    captured: dict[str, object] = {}

    def _fake_apply_async(*, kwargs, queue, task_id):
        captured["kwargs"] = kwargs
        captured["queue"] = queue
        return SimpleNamespace(id="task-upload")

    monkeypatch.setattr(internal_router, "INGEST_STAGING_DIR", tmp_path)
    monkeypatch.setattr(internal_router.ingest_sample_bundle_task, "apply_async", _fake_apply_async)
    monkeypatch.setattr(internal_router, "_enforce_access", lambda *_args, **_kwargs: None)
    yaml_upload = _Upload(
        filename="sample.yaml",
        content=b"name: SAMPLE_1\nassay: assay_1\nvcf_files: case.vcf\n",
    )
    data_archive = _zip_upload(("case.vcf", b"##fileformat=VCFv4.2\n"))
    service = SimpleNamespace(
        parse_yaml_payload=lambda _raw: {
            "name": "SAMPLE_1",
            "asp_id": "assay_1",
            "environment": "production",
            "omics_layer": "dna",
            "vcf_files": "case.vcf",
        },
        _assay_file_policy=lambda **_: ({"vcf_files"}, {"vcf_files"}),
    )

    response = internal_router.enqueue_ingest_sample_bundle_upload_internal(
        yaml_file=yaml_upload,
        data_archive=data_archive,
        update_existing=False,
        increment=False,
        user=_user(role="developer", level=50, permissions=["sample:edit:own"]),
        ingest_service=service,
    )

    assert response["status"] == "accepted"
    assert response["task_id"] == captured["kwargs"]["job_id"]
    kwargs = ingest_jobs.get(response["task_id"])
    assert kwargs["staging_dir"].startswith(str(tmp_path))
    staged_vcf = kwargs["source_payload"]["_runtime_files"]["vcf_files"]
    assert staged_vcf.startswith(kwargs["staging_dir"])
    assert kwargs["source_payload"]["_uploaded_file_checksums"]["vcf_files"]


def test_upload_ignores_excluded_file_without_resolving_it(tmp_path):
    service = SimpleNamespace(
        parse_yaml_payload=lambda _: {
            "asp_id": "synthetic",
            "omics_layer": "dna",
            "cnv": "missing.json",
            "files": {"cnv": "missing.json"},
            "_runtime_files": {"cnv": "missing.json"},
            "_uploaded_file_checksums": {"cnv": "old-checksum"},
        },
        _assay_file_policy=lambda **_: ({"vcf_files"}, {"vcf_files"}),
    )
    result = internal_router._prepare_uploaded_bundle(
        yaml_file=_Upload(filename="sample.yaml", content=b"synthetic"),
        data_archive=None,
        staging_dir=tmp_path,
        ingest_service=service,
    )
    assert "cnv" not in result
    for field in ("files", "_runtime_files", "_uploaded_file_checksums"):
        assert "cnv" not in result[field]
    assert result["_ingest_warnings"] == [
        "Ignored 'cnv': ASP 'synthetic' does not accept this file."
    ]


def test_internal_task_status_payload_success(monkeypatch):
    """Task status endpoint returns successful Celery result payloads."""

    class _Result:
        state = "SUCCESS"
        result = {"status": "ok"}

        def __init__(self, task_id, app=None):
            self.task_id = task_id
            self.app = app

        def ready(self):
            return True

        def successful(self):
            return True

    monkeypatch.setattr(internal_router, "AsyncResult", _Result)
    response = internal_router.get_internal_task_status(
        task_id="task-123",
        _user=_user(role="developer", level=50),
    )

    assert response == {
        "status": "ok",
        "task_id": "task-123",
        "state": "SUCCESS",
        "ready": True,
        "successful": True,
        "result": {"status": "ok"},
    }


def test_durable_job_status_is_limited_to_submitter_or_superuser(ingest_jobs):
    identity = ingest_jobs.submit(source_payload={}, submitted_by="another.user")
    with pytest.raises(HTTPException) as error:
        internal_router.get_internal_task_status(
            task_id=identity, _user=_user(role="developer", level=50)
        )
    assert error.value.status_code == 403
    response = internal_router.get_internal_task_status(
        task_id=identity, _user=_user(role="superuser", level=100)
    )
    assert response["state"] == "PENDING"
