"""Internal API routes for metadata and ingestion operations."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from api.app.container import util
from api.app.deps.repositories import get_gene_list_repository, get_roles_repository
from api.app.deps.services import get_internal_ingest_service
from api.application.ingest.parsers import runtime_file_path
from api.application.ingest.service import InternalIngestService
from api.application.ingest.upload_archive import UploadedFileIndex, extract_uploaded_archive
from api.celery_app import celery_app
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
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS
from api.infra.observability.prometheus_metrics import render_prometheus_metrics
from api.interfaces.http.tags import TAG_INTERNAL
from api.security.access import (
    ApiUser,
    _enforce_access,
    _require_internal_token,
    require_access,
)
from api.tasks.ingest import (
    ingest_sample_bundle_task,
    insert_collection_document_task,
    insert_collection_documents_task,
    upsert_collection_document_task,
)

router = APIRouter(tags=[TAG_INTERNAL])


def _task_submit_payload(task, *, task_name: str, queue: str) -> dict:
    """Return the standard internal task enqueue response."""
    return {"status": "accepted", "task_id": str(task.id), "task_name": task_name, "queue": queue}


def _task_status_payload(task_id: str) -> dict:
    """Return serializable Celery task state and result/error when available."""
    result = AsyncResult(task_id, app=celery_app)
    payload: dict = {
        "status": "ok",
        "task_id": task_id,
        "state": result.state,
        "ready": bool(result.ready()),
    }
    if result.ready():
        payload["successful"] = bool(result.successful())
        if result.successful():
            payload["result"] = util.common.convert_to_serializable(result.result)
        else:
            payload["error"] = str(result.result)
    else:
        payload["successful"] = None
    return payload


def _parse_uploaded_collection_payload(filename: str, payload: bytes) -> object:
    """Parse JSON, NDJSON, or gzipped variants for collection uploads."""
    normalized_name = str(filename or "").strip().lower()
    decoded_bytes = payload
    if normalized_name.endswith(".gz"):
        decoded_bytes = gzip.decompress(payload)
        normalized_name = normalized_name[:-3]
    decoded_text = decoded_bytes.decode("utf-8")
    if normalized_name.endswith(".ndjson") or normalized_name.endswith(".jsonl"):
        rows = [json.loads(line) for line in decoded_text.splitlines() if str(line).strip()]
        return rows
    return json.loads(decoded_text)


_COLLECTION_CREATE_PERMISSION_MAP: dict[str, str] = {
    "users": "user:create",
    "roles": "role:create",
    "permissions": "permission.policy:create",
    "assay_specific_panels": "assay.panel:create",
    "asp_configs": "assay.config:create",
    "insilico_genelists": "gene_list.insilico:create",
}

_COLLECTION_UPDATE_PERMISSION_MAP: dict[str, str] = {
    "users": "user:edit",
    "roles": "role:edit",
    "permissions": "permission.policy:edit",
    "assay_specific_panels": "assay.panel:edit",
    "asp_configs": "assay.config:edit",
    "insilico_genelists": "gene_list.insilico:edit",
}

_SAMPLE_LINKED_COLLECTIONS: frozenset[str] = frozenset(
    {
        "samples",
        "sample_comments",
        "finding_comments",
        "reports",
        "variants",
        "cnvs",
        "translocations",
        "biomarkers",
        "panel_coverage",
        "fusions",
        "rna_expression",
        "rna_classification",
        "rna_qc",
        "reported_variants",
        "group_coverage",
    }
)


def _is_superuser(user: ApiUser) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _enforce_collection_permission(*, user: ApiUser, collection: str, action: str) -> None:
    """Enforce collection-level action permissions for non-superuser operators."""
    if _is_superuser(user):
        return
    if action == "create":
        permission = _COLLECTION_CREATE_PERMISSION_MAP.get(collection)
    elif action == "update":
        permission = _COLLECTION_UPDATE_PERMISSION_MAP.get(collection)
    else:
        permission = None
    if not permission and collection in _SAMPLE_LINKED_COLLECTIONS:
        permission = "sample:edit:own"
    if permission:
        _enforce_access(user, permission=permission)


def _enforce_sample_ingest_permission(user: ApiUser) -> None:
    """Require sample:edit:own for non-superuser operators."""
    if _is_superuser(user):
        return
    _enforce_access(user, permission="sample:edit:own")


@router.get("/api/v1/internal/roles/levels", response_model=RoleLevelsPayload)
def get_role_levels_internal(request: Request, roles_repository=Depends(get_roles_repository)):
    """Return role-level mappings for trusted internal callers."""
    _require_internal_token(request)
    role_levels = {
        role.get("role_id"): role.get("level", 0)
        for role in (roles_repository.get_all_roles() or [])
        if role.get("role_id")
    }
    return util.common.convert_to_serializable({"status": "ok", "role_levels": role_levels})


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    gene_list_repository=Depends(get_gene_list_repository),
):
    """Return genelist metadata for trusted internal callers."""
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(gene_list_repository.is_isgl_adhoc(isgl_id)),
            "display_name": gene_list_repository.get_isgl_display_name(isgl_id),
        }
    )


@router.get(
    "/api/v1/internal/ingest/collection/{collection}/status",
    response_model=InternalCollectionStatusPayload,
)
def get_ingest_collection_status_internal(
    collection: str,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Return collection occupancy used by first-deployment bootstrap tooling."""
    try:
        count = ingest_service.collection_document_count(collection)
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
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
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

    try:
        _enforce_sample_ingest_permission(user)
        source_payload = (
            ingest_service.parse_yaml_payload(payload.yaml_content)
            if payload.yaml_content
            else payload.sample.model_dump(exclude_none=True)
        )
        if payload.update_existing:
            _enforce_sample_ingest_permission(user)
        result = ingest_service.ingest_sample_bundle(
            source_payload,
            allow_update=payload.update_existing,
            increment=payload.increment,
        )
    except (ValueError, FileNotFoundError) as exc:
        if acknowledge:
            return _ingest_acknowledgement(error=exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    serialized = util.common.convert_to_serializable(result)
    return _ingest_acknowledgement(result=serialized) if acknowledge else serialized


def _save_upload(upload: UploadFile, destination: Path) -> str:
    digest = sha256()
    with destination.open("wb") as handle:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


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


def _prepare_uploaded_bundle(
    *,
    yaml_file: UploadFile,
    data_archive: UploadFile | None,
    staging_dir: Path,
    ingest_service: InternalIngestService,
) -> dict:
    """Parse a manifest and resolve declared paths against one uploaded ZIP archive."""
    yaml_content = yaml_file.file.read().decode("utf-8")
    source_payload = ingest_service.parse_yaml_payload(yaml_content)
    expected_keys, required_keys = ingest_service._assay_file_policy(
        assay_name=source_payload.get("asp_id"),
        omics_layer=source_payload.get("omics_layer"),
    )

    archive_index = UploadedFileIndex(exact={}, basename={}, checksums={})
    if data_archive is not None:
        if not data_archive.filename:
            raise ValueError("data_archive must include a filename")
        archive_path = staging_dir / Path(str(data_archive.filename)).name
        _save_upload(data_archive, archive_path)
        archive_index = extract_uploaded_archive(
            archive_path=archive_path,
            destination=staging_dir / "files",
        )

    runtime_files: dict[str, str] = {}
    checksums: dict[str, str] = {}
    missing: list[str] = []
    ambiguous: list[str] = []
    for key in SAMPLE_SOURCE_PATH_KEYS:
        raw_value = runtime_file_path(source_payload, key)
        if not raw_value or not raw_value.strip():
            continue
        path_value = raw_value.strip()
        if key not in expected_keys:
            raise ValueError(
                f"Manifest declares '{key}', but ASP '{source_payload.get('asp_id')}' does not accept it"
            )
        resolved = archive_index.exact.get(path_value)
        if not resolved:
            basename = Path(path_value).name
            if basename in archive_index.basename and archive_index.basename[basename] is None:
                ambiguous.append(f"{key}:{path_value}")
                continue
            resolved = archive_index.basename.get(basename)
        if resolved:
            runtime_files[key] = resolved
            checksum = archive_index.checksums.get(resolved)
            if checksum:
                checksums[key] = checksum
            continue
        if os.path.exists(path_value):
            runtime_files[key] = path_value
            continue
        missing.append(f"{key}:{path_value}")

    if ambiguous:
        raise ValueError(
            "Ambiguous archive filenames for YAML references: "
            + ", ".join(sorted(ambiguous))
            + ". Use unique basenames or archive paths matching the YAML values."
        )
    if missing:
        required_missing = [entry for entry in missing if entry.split(":", 1)[0] in required_keys]
        label = "Missing required files" if required_missing else "Missing declared files"
        raise ValueError(
            f"{label} for YAML references: "
            + ", ".join(sorted(missing))
            + ". Provide one ZIP containing matching files or make the manifest paths readable."
        )
    if runtime_files:
        source_payload["_runtime_files"] = runtime_files
    if checksums:
        source_payload["_uploaded_file_checksums"] = checksums
    return source_payload


@router.post(
    "/api/v1/internal/ingest/sample-bundle/upload",
    response_model=InternalIngestSampleBundlePayload | InternalIngestAcknowledgementPayload,
)
def ingest_sample_bundle_upload_internal(
    yaml_file: UploadFile = File(...),
    data_archive: UploadFile | None = File(None),
    update_existing: bool = Form(False),
    increment: bool = Form(False),
    acknowledge: bool = Form(False),
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Upload YAML + data files, stage runtime files server-side, and ingest sample bundle."""
    if not yaml_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yaml_file must include a filename",
        )

    staging_dir = Path(tempfile.mkdtemp(prefix="coyote3_ingest_upload_"))
    upload_refs: list[UploadFile] = [yaml_file, *([data_archive] if data_archive else [])]
    try:
        _enforce_sample_ingest_permission(user)
        source_payload = _prepare_uploaded_bundle(
            yaml_file=yaml_file,
            data_archive=data_archive,
            staging_dir=staging_dir,
            ingest_service=ingest_service,
        )
        if update_existing:
            _enforce_sample_ingest_permission(user)
        result = ingest_service.ingest_sample_bundle(
            source_payload,
            allow_update=update_existing,
            increment=increment,
        )
        serialized = util.common.convert_to_serializable(result)
        return _ingest_acknowledgement(result=serialized) if acknowledge else serialized
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
        if acknowledge:
            return _ingest_acknowledgement(error=exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
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
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Enqueue sample-bundle ingestion on the Celery ingest queue."""
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

    try:
        _enforce_sample_ingest_permission(user)
        source_payload = (
            ingest_service.parse_yaml_payload(payload.yaml_content)
            if payload.yaml_content
            else payload.sample.model_dump(exclude_none=True)
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    queue = DefaultConfig.CELERY_INGEST_QUEUE
    task = ingest_sample_bundle_task.apply_async(
        kwargs={
            "source_payload": source_payload,
            "update_existing": payload.update_existing,
            "increment": payload.increment,
        },
        queue=queue,
    )
    return _task_submit_payload(
        task, task_name="api.tasks.ingest.ingest_sample_bundle", queue=queue
    )


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
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
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
        _enforce_sample_ingest_permission(user)
        source_payload = _prepare_uploaded_bundle(
            yaml_file=yaml_file,
            data_archive=data_archive,
            staging_dir=staging_dir,
            ingest_service=ingest_service,
        )

        queue = DefaultConfig.CELERY_INGEST_QUEUE
        task = ingest_sample_bundle_task.apply_async(
            kwargs={
                "source_payload": source_payload,
                "update_existing": update_existing,
                "increment": increment,
                "staging_dir": str(staging_dir),
            },
            queue=queue,
        )
        task_enqueued = True
        return _task_submit_payload(
            task, task_name="api.tasks.ingest.ingest_sample_bundle", queue=queue
        )
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Insert one validated document into a supported collection."""
    try:
        _enforce_collection_permission(user=user, collection=payload.collection, action="create")
        result = ingest_service.insert_collection_document(
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
):
    """Enqueue insertion of one validated collection document."""
    _enforce_collection_permission(user=user, collection=payload.collection, action="create")
    queue = DefaultConfig.CELERY_INGEST_QUEUE
    task = insert_collection_document_task.apply_async(
        kwargs={
            "collection": payload.collection,
            "document": payload.document,
            "ignore_duplicate": payload.ignore_duplicate,
        },
        queue=queue,
    )
    return _task_submit_payload(
        task, task_name="api.tasks.ingest.insert_collection_document", queue=queue
    )


@router.post(
    "/api/v1/internal/ingest/collection/bulk",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_documents_internal(
    payload: InternalCollectionBulkInsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Insert many validated documents into a supported collection."""
    try:
        _enforce_collection_permission(user=user, collection=payload.collection, action="create")
        result = ingest_service.insert_collection_documents(
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
):
    """Enqueue insertion of many validated collection documents."""
    _enforce_collection_permission(user=user, collection=payload.collection, action="create")
    queue = DefaultConfig.CELERY_INGEST_QUEUE
    task = insert_collection_documents_task.apply_async(
        kwargs={
            "collection": payload.collection,
            "documents": payload.documents,
            "ignore_duplicates": payload.ignore_duplicates,
        },
        queue=queue,
    )
    return _task_submit_payload(
        task, task_name="api.tasks.ingest.insert_collection_documents", queue=queue
    )


@router.put(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionUpsertPayload,
)
def upsert_collection_document_internal(
    payload: InternalCollectionUpsertRequest,
    user: ApiUser = Depends(require_access(permission="internal.ingest:manage")),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Replace/update one validated document in a supported collection."""
    try:
        _enforce_collection_permission(user=user, collection=payload.collection, action="update")
        result = ingest_service.upsert_collection_document(
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
):
    """Enqueue replacement/update of one validated collection document."""
    _enforce_collection_permission(user=user, collection=payload.collection, action="update")
    queue = DefaultConfig.CELERY_INGEST_QUEUE
    task = upsert_collection_document_task.apply_async(
        kwargs={
            "collection": payload.collection,
            "match": payload.match,
            "document": payload.document,
            "upsert": payload.upsert,
        },
        queue=queue,
    )
    return _task_submit_payload(
        task, task_name="api.tasks.ingest.upsert_collection_document", queue=queue
    )


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
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
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
        bytes_payload = documents_file.file.read()
        parsed = _parse_uploaded_collection_payload(documents_file.filename, bytes_payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
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
            _enforce_collection_permission(user=user, collection=raw_collection, action="create")
            result = ingest_service.insert_collection_documents(
                collection=raw_collection,
                documents=parsed,
                ignore_duplicates=True,
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
            _enforce_collection_permission(user=user, collection=raw_collection, action="update")
            result = ingest_service.upsert_collection_document(
                collection=raw_collection,
                match=parsed_match,
                document=parsed,
                upsert=True,
            )
            result["mode"] = normalized_mode
            return util.common.convert_to_serializable(result)

        if not isinstance(parsed, dict):
            raise ValueError("Insert mode requires an uploaded JSON object.")
        _enforce_collection_permission(user=user, collection=raw_collection, action="create")
        result = ingest_service.insert_collection_document(
            collection=raw_collection,
            document=parsed,
            ignore_duplicate=True,
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
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """List supported collection names for validated collection-ingest endpoints."""
    return util.common.convert_to_serializable(
        {"status": "ok", "collections": ingest_service.list_supported_collections()}
    )


@router.get(
    "/api/v1/internal/tasks/{task_id}",
    response_model=InternalTaskStatusPayload,
)
def get_internal_task_status(
    task_id: str,
    _user: ApiUser = Depends(require_access(permission="internal.task:view")),
):
    """Return Celery task state and result/error when complete."""
    return _task_status_payload(task_id)


@router.get("/api/v1/internal/metrics", response_class=PlainTextResponse)
def get_prometheus_metrics_internal(request: Request):
    """Expose Prometheus metrics in text format for internal scraping."""
    _require_internal_token(request)
    return PlainTextResponse(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
