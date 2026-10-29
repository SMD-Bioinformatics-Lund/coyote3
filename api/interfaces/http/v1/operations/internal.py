"""Internal API routes for metadata and ingestion operations."""

from __future__ import annotations

import gzip
import json
import logging
import shutil
import tempfile
from functools import partial
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from api.app.container import util
from api.app.deps.application import get_ingestion, get_internal_references, get_sample_ingestion
from api.app.deps.services import get_audit_service
from api.config.paths import INGEST_STAGING_DIR
from api.config.runtime_settings import DefaultConfig
from api.contracts.internal import (
    InternalCollectionBulkInsertRequest,
    InternalCollectionInsertPayload,
    InternalCollectionInsertRequest,
    InternalCollectionStatusPayload,
    InternalCollectionSupportPayload,
    InternalCollectionUploadPayload,
    InternalCollectionUpsertPayload,
    InternalCollectionUpsertRequest,
    InternalIngestAcknowledgementPayload,
    InternalIngestSampleBundlePayload,
    InternalIngestSampleBundleRequest,
    InternalTaskStatusPayload,
    InternalTaskSubmitPayload,
    IsglMetaPayload,
    RoleLevelsPayload,
)
from api.infra.observability.prometheus_metrics import render_prometheus_metrics
from api.interfaces.http.tags import TAG_INTERNAL
from api.interfaces.http.v1.operations.ingest_stream import stream_ingest
from api.security.access import (
    ApiUser,
    _require_internal_token,
    require_access,
    require_sample_ingest_access,
)
from coyote3.application.operations.ingest import Ingestion
from coyote3.application.operations.ingest_audit import IngestionAuditAttempt
from coyote3.application.operations.internal_references import InternalReferences
from coyote3.domain.exceptions import AppError

router = APIRouter(tags=[TAG_INTERNAL])


def _record_upload_error(user: ApiUser, exc: Exception, *, error_id: str = "") -> None:
    """Record the actionable upload rejection in both logs and the audit."""
    logger = logging.getLogger(__name__)
    logger.exception("Ingest failed: %s: %s error_id=%s", type(exc).__name__, exc, error_id)
    try:
        audit = get_audit_service()
        if audit:
            audit.record(
                "ingest.upload.rejected",
                f"Ingest upload rejected: {exc}"[:500],
                category="data",
                severity="warning",
                outcome="failure",
                actor=user,
                tags=["ingest", "upload"],
                metadata={
                    "error": str(exc)[:1000],
                    "error_type": type(exc).__name__,
                    "error_id": error_id,
                },
            )
    except Exception:
        logger.exception("Could not record upload rejection in audit")


def _ingest_failure(user: ApiUser, exc: Exception, *, acknowledge: bool = False):
    """Report ingest failures consistently without claiming uncertain writes failed.

    Validation failures may produce a terminal acknowledgement. Unexpected
    exceptions retain HTTP 500 and an error ID shared with logs and audit.
    """
    error_id = uuid4().hex
    _record_upload_error(user, exc, error_id=error_id)
    if isinstance(exc, (HTTPException, AppError)):
        raise exc
    if isinstance(exc, (ValueError, FileNotFoundError, UnicodeDecodeError)):
        if acknowledge:
            return _ingest_acknowledgement(error=exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "error": "Ingest failed. Contact an administrator with the request ID.",
            "request_id": error_id,
            "hint": "See the matching error_id in the API log and ingest audit; outcome is unconfirmed.",
        },
    )


def _parse_uploaded_collection_payload(filename: str, payload: bytes) -> object:
    """Parse collection JSON within the configured compressed and expanded byte limit.

    Args:
        filename: Upload name identifying JSON, NDJSON, or their gzip variants.
        payload: Uploaded bytes; must fit INGEST_COLLECTION_UPLOAD_MAX_BYTES.

    Returns:
        Decoded JSON document or list of NDJSON documents.

    Raises:
        HTTPException: HTTP 413 when compressed or expanded input exceeds the limit.
        ValueError: Invalid JSON or UTF-8 content.
        OSError: Invalid gzip content.
        EOFError: Truncated gzip content.
    """
    limit = DefaultConfig.INGEST_COLLECTION_UPLOAD_MAX_BYTES
    if limit <= 0:
        raise RuntimeError("INGEST_COLLECTION_UPLOAD_MAX_BYTES must be positive")
    if len(payload) > limit:
        raise HTTPException(413, "Collection upload exceeds the configured byte limit")
    normalized_name = str(filename or "").strip().lower()
    decoded_bytes = payload
    if normalized_name.endswith(".gz"):
        with gzip.GzipFile(fileobj=BytesIO(payload)) as stream:
            decoded_bytes = stream.read(limit + 1)
        if len(decoded_bytes) > limit:
            raise HTTPException(413, "Expanded collection upload exceeds the configured byte limit")
        normalized_name = normalized_name[:-3]
    decoded_text = decoded_bytes.decode("utf-8")
    if normalized_name.endswith(".ndjson") or normalized_name.endswith(".jsonl"):
        rows = [json.loads(line) for line in decoded_text.splitlines() if str(line).strip()]
        return rows
    return json.loads(decoded_text)


@router.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(
    request: Request, service: InternalReferences = Depends(get_internal_references)
):
    """Return role-level mappings for trusted internal callers."""
    return util.common.convert_to_serializable(service.role_levels())


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    service: InternalReferences = Depends(get_internal_references),
):
    """Return genelist metadata for trusted internal callers."""
    return util.common.convert_to_serializable(service.gene_list_metadata(isgl_id))


@router.get(
    "/api/v1/internal/ingest/collection/{collection}/status",
    response_model=InternalCollectionStatusPayload,
)
def get_ingest_collection_status_internal(
    collection: str,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Return collection occupancy used by first-deployment bootstrap tooling."""
    try:
        count = ingest_service.collection_count(collection)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "status": "ok",
        "collection": collection,
        "document_count": count,
        "empty": count == 0,
    }


@router.post(
    "/api/v1/internal/ingest/sample-bundle",
    response_model=InternalIngestSampleBundlePayload | InternalIngestAcknowledgementPayload,
)
def ingest_sample_bundle_internal(
    payload: InternalIngestSampleBundleRequest,
    acknowledge: bool = False,
    user: ApiUser = Depends(require_sample_ingest_access),
    ingest_service: Ingestion = Depends(get_sample_ingestion),
):
    """Create a fresh sample and all dependent analysis documents atomically."""
    if not payload.sample and not payload.yaml_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either `sample` or `yaml_content`",
        )
    if payload.sample and payload.yaml_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of `sample` or `yaml_content`",
        )

    attempt = IngestionAuditAttempt(
        get_audit_service(),
        actor=user,
        source="api",
        update_existing=payload.update_existing,
        increment=payload.increment,
    )
    try:
        ingest_service.authorize_sample()
        source_payload = (
            ingest_service.parse_yaml(payload.yaml_content)
            if payload.yaml_content
            else payload.sample.model_dump(exclude_none=True)
        )
        ingest_service.authorize_sample(source_payload)
        result = ingest_service.sample_bundle(
            source_payload,
            allow_update=payload.update_existing,
            increment=payload.increment,
            source="api",
        ).model_dump()
    except Exception as exc:
        attempt.failed(exc)
        return _ingest_failure(user, exc, acknowledge=acknowledge)
    attempt.succeeded(result)
    serialized = util.common.convert_to_serializable(result)
    return _ingest_acknowledgement(result=serialized) if acknowledge else serialized


def _ingest_acknowledgement(
    *,
    result: dict | None = None,
    error: Exception | None = None,
) -> dict:
    """Return a stable terminal result for cron-managed manifest handoff."""
    if error is not None:
        return {
            "status": "failed",
            "sample_name": None,
            "sample_id": None,
            "message": str(error),
            "result": None,
        }
    payload = dict(result or {})
    return {
        "status": "ok",
        "sample_name": payload.get("sample_name"),
        "sample_id": payload.get("sample_id"),
        "message": "Sample bundle ingested successfully",
        "result": payload,
    }


@router.post(
    "/api/v1/internal/ingest/sample-bundle/upload",
    response_model=InternalIngestSampleBundlePayload | InternalIngestAcknowledgementPayload,
    responses={200: {"content": {"application/x-ndjson": {"schema": {"type": "string"}}}}},
)
def ingest_sample_bundle_upload_internal(
    yaml_file: UploadFile = File(...),
    data_archive: UploadFile | None = File(None),
    update_existing: bool = Form(False),
    increment: bool = Form(False),
    acknowledge: bool = Form(False),
    user: ApiUser = Depends(require_sample_ingest_access),
    ingest_service: Ingestion = Depends(get_sample_ingestion),
    verbose: bool = Form(False),
):
    """Upload and ingest YAML; verbose streams request-local logs and the final result.

    With verbose=true the response is NDJSON: log/heartbeat events followed by
    result or error. An error event carries its status_code because HTTP headers
    have already been sent. No terminal event means the outcome is unconfirmed.
    """
    if not yaml_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yaml_file must include a filename",
        )

    ingest_service.authorize_sample()
    operation = partial(
        _execute_sample_bundle_upload,
        yaml_file=yaml_file,
        data_archive=data_archive,
        update_existing=update_existing,
        increment=increment,
        acknowledge=acknowledge,
        user=user,
        ingest_service=ingest_service,
    )
    return stream_ingest(operation) if verbose is True else operation()


def _execute_sample_bundle_upload(
    *,
    yaml_file: UploadFile,
    data_archive: UploadFile | None,
    update_existing: bool,
    increment: bool,
    acknowledge: bool,
    user: ApiUser,
    ingest_service: Ingestion,
):
    """Stage, execute, and clean up one authenticated bundle upload."""

    logging.getLogger(__name__).info("Ingest upload started: manifest=%s", yaml_file.filename)
    attempt = IngestionAuditAttempt(
        get_audit_service(),
        actor=user,
        source="upload",
        manifest=yaml_file.filename,
        update_existing=update_existing,
        increment=increment,
    )
    staging_dir = Path(tempfile.mkdtemp(prefix="coyote3_ingest_upload_"))
    upload_refs: list[UploadFile] = [yaml_file, *([data_archive] if data_archive else [])]
    try:
        ingest_service.authorize_sample()
        source_payload = ingest_service.prepare_upload(
            yaml_file=yaml_file,
            data_archive=data_archive,
            staging_dir=staging_dir,
            allow_update=update_existing,
            increment=increment,
        )
        ingest_service.authorize_sample(source_payload)
        result = ingest_service.sample_bundle(
            {key: value for key, value in source_payload.items() if key != "_ingest_warnings"},
            allow_update=update_existing,
            increment=increment,
            source="upload",
        ).model_dump()
        serialized = util.common.convert_to_serializable(result)
        if source_payload.get("_ingest_warnings"):
            serialized["warnings"] = [
                *serialized.get("warnings", []),
                *source_payload["_ingest_warnings"],
            ]
        logging.getLogger(__name__).info("Ingest upload completed: manifest=%s", yaml_file.filename)
        attempt.succeeded(result)
        return _ingest_acknowledgement(result=serialized) if acknowledge else serialized
    except Exception as exc:
        attempt.failed(exc)
        return _ingest_failure(user, exc, acknowledge=acknowledge)
    finally:
        for upload in upload_refs:
            try:
                upload.file.close()
            except Exception:
                pass
        shutil.rmtree(staging_dir, ignore_errors=True)


@router.post(
    "/api/v1/internal/ingest/sample-bundle/async",
    response_model=InternalTaskSubmitPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_ingest_sample_bundle_internal(
    payload: InternalIngestSampleBundleRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Enqueue sample-bundle ingestion on the Celery ingest queue."""
    try:
        source = ingest_service.manifest(
            sample=payload.sample.model_dump(exclude_none=True) if payload.sample else None,
            yaml_content=payload.yaml_content,
        )
        return ingest_service.enqueue_sample_bundle(
            source, allow_update=payload.update_existing, increment=payload.increment
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/api/v1/internal/ingest/sample-bundle/upload/async",
    response_model=InternalTaskSubmitPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_ingest_sample_bundle_upload_internal(
    yaml_file: UploadFile = File(...),
    data_archive: UploadFile | None = File(None),
    update_existing: bool = Form(False),
    increment: bool = Form(False),
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Upload a YAML + optional ZIP archive, stage it durably, and queue ingest."""
    if not yaml_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yaml_file must include a filename",
        )

    staging_root = INGEST_STAGING_DIR
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix="sample_bundle_", dir=str(staging_root)))
    upload_refs: list[UploadFile] = [yaml_file, *([data_archive] if data_archive else [])]
    task_enqueued = False
    try:
        ingest_service.authorize_sample()
        source_payload = ingest_service.prepare_upload(
            yaml_file=yaml_file,
            data_archive=data_archive,
            staging_dir=staging_dir,
            allow_update=update_existing,
            increment=increment,
        )

        response = ingest_service.enqueue_sample_bundle(
            source_payload,
            allow_update=update_existing,
            increment=increment,
            staging_dir=str(staging_dir),
        )
        task_enqueued = True
        response["warnings"] = source_payload.get("_ingest_warnings", [])
        return response
    except Exception as exc:
        return _ingest_failure(user, exc)
    finally:
        for upload in upload_refs:
            try:
                upload.file.close()
            except Exception:
                pass
        if not task_enqueued:
            shutil.rmtree(staging_dir, ignore_errors=True)


@router.post(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_document_internal(
    payload: InternalCollectionInsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Insert one validated document into a supported collection."""
    try:
        ingest_service.authorize_collection(collection=payload.collection, action="create")
        result = ingest_service.insert_document(
            collection=payload.collection,
            document=payload.document,
            ignore_duplicate=payload.ignore_duplicate,
        )
        return util.common.convert_to_serializable(result)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/internal/ingest/collection/async",
    response_model=InternalTaskSubmitPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_ingest_collection_document_internal(
    payload: InternalCollectionInsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Enqueue insertion of one validated collection document."""
    try:
        return ingest_service.enqueue_collection("insert_document", payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/api/v1/internal/ingest/collection/bulk",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_documents_internal(
    payload: InternalCollectionBulkInsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Insert many validated documents into a supported collection."""
    try:
        ingest_service.authorize_collection(collection=payload.collection, action="create")
        result = ingest_service.insert_documents(
            collection=payload.collection,
            documents=payload.documents,
            ignore_duplicates=payload.ignore_duplicates,
        )
        return util.common.convert_to_serializable(result)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/internal/ingest/collection/bulk/async",
    response_model=InternalTaskSubmitPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_ingest_collection_documents_internal(
    payload: InternalCollectionBulkInsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Enqueue insertion of many validated collection documents."""
    try:
        return ingest_service.enqueue_collection("insert_documents", payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionUpsertPayload,
)
def upsert_collection_document_internal(
    payload: InternalCollectionUpsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Replace/update one validated document in a supported collection."""
    try:
        ingest_service.authorize_collection(collection=payload.collection, action="update")
        result = ingest_service.upsert_document(
            collection=payload.collection,
            match=payload.match,
            document=payload.document,
            upsert=payload.upsert,
        )
        return util.common.convert_to_serializable(result)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put(
    "/api/v1/internal/ingest/collection/async",
    response_model=InternalTaskSubmitPayload,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_upsert_collection_document_internal(
    payload: InternalCollectionUpsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Enqueue replacement/update of one validated collection document."""
    try:
        return ingest_service.enqueue_collection("upsert_document", payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/api/v1/internal/ingest/collection/upload",
    response_model=InternalCollectionUploadPayload,
)
def ingest_collection_upload_internal(
    collection: str = Form(...),
    mode: str = Form("insert"),
    documents_file: UploadFile = File(...),
    match_json: str | None = Form(default=None),
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Validate and ingest collection documents from uploaded JSON payload."""
    raw_collection = str(collection or "").strip()
    normalized_mode = str(mode or "insert").strip().lower()
    if normalized_mode not in {"insert", "bulk", "upsert"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode must be one of: insert, bulk, upsert",
        )
    if not documents_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="documents_file must include a filename",
        )

    try:
        ingest_service.authorize_collection(
            collection=raw_collection, action="update" if normalized_mode == "upsert" else "create"
        )
        limit = DefaultConfig.INGEST_COLLECTION_UPLOAD_MAX_BYTES
        if limit <= 0:
            raise RuntimeError("INGEST_COLLECTION_UPLOAD_MAX_BYTES must be positive")
        bytes_payload = documents_file.file.read(limit + 1)
        parsed = _parse_uploaded_collection_payload(documents_file.filename, bytes_payload)
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON/NDJSON upload: {exc}",
        ) from exc
    finally:
        try:
            documents_file.file.close()
        except Exception:
            pass

    try:
        if normalized_mode == "bulk":
            if not isinstance(parsed, list):
                raise ValueError("Bulk mode requires an uploaded JSON array.")
            ingest_service.authorize_collection(collection=raw_collection, action="create")
            result = ingest_service.insert_documents(
                collection=raw_collection, documents=parsed, ignore_duplicates=True
            )
            result["mode"] = normalized_mode
            return util.common.convert_to_serializable(result)

        if normalized_mode == "upsert":
            if not isinstance(parsed, dict):
                raise ValueError("Upsert mode requires an uploaded JSON object.")
            if not match_json:
                raise ValueError("Upsert mode requires match_json form field.")
            parsed_match = json.loads(match_json)
            if not isinstance(parsed_match, dict) or not parsed_match:
                raise ValueError("match_json must be a non-empty JSON object.")
            ingest_service.authorize_collection(collection=raw_collection, action="update")
            result = ingest_service.upsert_document(
                collection=raw_collection, match=parsed_match, document=parsed, upsert=True
            )
            result["mode"] = normalized_mode
            return util.common.convert_to_serializable(result)

        if not isinstance(parsed, dict):
            raise ValueError("Insert mode requires an uploaded JSON object.")
        ingest_service.authorize_collection(collection=raw_collection, action="create")
        result = ingest_service.insert_document(
            collection=raw_collection, document=parsed, ignore_duplicate=True
        )
        result["mode"] = normalized_mode
        return util.common.convert_to_serializable(result)
    except (ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/internal/ingest/collections",
    response_model=InternalCollectionSupportPayload,
)
def list_supported_ingest_collections_internal(
    _user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """List supported collection names for validated collection-ingest endpoints."""
    return util.common.convert_to_serializable(
        {"status": "ok", "collections": ingest_service.supported_collections()}
    )


@router.get(
    "/api/v1/internal/tasks/{task_id}",
    response_model=InternalTaskStatusPayload,
)
def get_internal_task_status(
    task_id: str,
    _user: ApiUser = Depends(require_access(permission="internal.task:view")),
    ingest_service: Ingestion = Depends(get_ingestion),
):
    """Return ingest status to its submitter or a superuser with internal.task:view."""
    return ingest_service.job_status(task_id)


@router.get("/api/v1/internal/metrics", response_class=PlainTextResponse)
def get_prometheus_metrics_internal(request: Request):
    """Expose Prometheus metrics in text format for internal scraping."""
    _require_internal_token(request)
    return PlainTextResponse(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
