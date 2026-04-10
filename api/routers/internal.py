"""Internal API routes for metadata and ingestion operations."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from api.contracts.internal import (
    InternalCollectionBulkInsertRequest,
    InternalCollectionInsertPayload,
    InternalCollectionInsertRequest,
    InternalCollectionSupportPayload,
    InternalCollectionUploadPayload,
    InternalCollectionUpsertPayload,
    InternalCollectionUpsertRequest,
    InternalIngestDependentsPayload,
    InternalIngestDependentsRequest,
    InternalIngestSampleBundlePayload,
    InternalIngestSampleBundleRequest,
    IsglMetaPayload,
    RoleLevelsPayload,
)
from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS
from api.deps.handlers import get_gene_list_handler, get_roles_handler
from api.deps.services import get_internal_ingest_service
from api.extensions import util
from api.observability.prometheus_metrics import render_prometheus_metrics
from api.security.access import (
    ApiUser,
    _enforce_access,
    _require_internal_token,
    require_access,
)
from api.services.ingest.service import InternalIngestService

router = APIRouter(tags=["internal"])


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
def get_role_levels_internal(request: Request, roles_handler=Depends(get_roles_handler)):
    """Return role-level mappings for trusted internal callers."""
    _require_internal_token(request)
    role_levels = {
        role.get("role_id"): role.get("level", 0)
        for role in (roles_handler.get_all_roles() or [])
        if role.get("role_id")
    }
    return util.common.convert_to_serializable({"status": "ok", "role_levels": role_levels})


@router.get("/api/v1/internal/isgl/{isgl_id}/meta", response_model=IsglMetaPayload)
def get_isgl_meta_internal(
    isgl_id: str,
    request: Request,
    gene_list_handler=Depends(get_gene_list_handler),
):
    """Return genelist metadata for trusted internal callers."""
    _require_internal_token(request)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "isgl_id": isgl_id,
            "is_adhoc": bool(gene_list_handler.is_isgl_adhoc(isgl_id)),
            "display_name": gene_list_handler.get_isgl_display_name(isgl_id),
        }
    )


@router.post(
    "/api/v1/internal/ingest/dependents",
    response_model=InternalIngestDependentsPayload,
)
def ingest_dependents_internal(
    payload: InternalIngestDependentsRequest,
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Write parsed dependent ingestion payload into Mongo collections."""
    _enforce_sample_ingest_permission(user)

    written = ingest_service.ingest_dependents(
        sample_id=str(payload.sample_id),
        sample_name=str(payload.sample_name),
        delete_existing=payload.delete_existing,
        preload=payload.preload,
    )

    return util.common.convert_to_serializable(
        {"status": "ok", "sample_id": str(payload.sample_id), "written": written}
    )


@router.post(
    "/api/v1/internal/ingest/sample-bundle",
    response_model=InternalIngestSampleBundlePayload,
)
def ingest_sample_bundle_internal(
    payload: InternalIngestSampleBundleRequest,
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Create a fresh sample and all dependent analysis documents atomically."""
    if not payload.sample and not payload.yaml_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either `spec` or `yaml_content`",
        )
    if payload.sample and payload.yaml_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of `spec` or `yaml_content`",
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return util.common.convert_to_serializable(result)


async def _save_upload(upload: UploadFile, destination: Path) -> str:
    digest = sha256()
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


@router.post(
    "/api/v1/internal/ingest/sample-bundle/upload",
    response_model=InternalIngestSampleBundlePayload,
)
async def ingest_sample_bundle_upload_internal(
    yaml_file: UploadFile = File(...),
    data_files: list[UploadFile] = File(default_factory=list),
    update_existing: bool = Form(False),
    increment: bool = Form(False),
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """Upload YAML + data files, stage runtime files server-side, and ingest sample bundle."""
    if not yaml_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="yaml_file must include a filename",
        )

    staging_dir = Path(tempfile.mkdtemp(prefix="coyote3_ingest_upload_"))
    uploads_by_exact: dict[str, str] = {}
    uploads_by_basename: dict[str, str | None] = {}
    uploaded_sha256_by_path: dict[str, str] = {}
    upload_refs: list[UploadFile] = [yaml_file, *data_files]
    try:
        _enforce_sample_ingest_permission(user)
        yaml_bytes = await yaml_file.read()
        yaml_content = yaml_bytes.decode("utf-8")
        source_payload = ingest_service.parse_yaml_payload(yaml_content)

        for upload in data_files:
            if not upload.filename:
                continue
            original_name = str(upload.filename).strip()
            if not original_name:
                continue
            base_name = Path(original_name).name
            if not base_name:
                continue

            destination = staging_dir / base_name
            suffix = 1
            while destination.exists():
                destination = staging_dir / f"{destination.stem}_{suffix}{destination.suffix}"
                suffix += 1
            checksum = await _save_upload(upload, destination)
            uploaded_sha256_by_path[str(destination)] = checksum

            uploads_by_exact[original_name] = str(destination)
            existing = uploads_by_basename.get(base_name)
            if existing and existing != str(destination):
                uploads_by_basename[base_name] = None
            elif existing is None and base_name in uploads_by_basename:
                pass
            else:
                uploads_by_basename[base_name] = str(destination)

        runtime_files: dict[str, str] = {}
        missing: list[str] = []
        ambiguous: list[str] = []
        for key in SAMPLE_SOURCE_PATH_KEYS:
            raw_value = source_payload.get(key)
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue
            path_value = raw_value.strip()
            resolved = uploads_by_exact.get(path_value)
            if not resolved:
                base_name = Path(path_value).name
                if base_name in uploads_by_basename and uploads_by_basename[base_name] is None:
                    ambiguous.append(f"{key}:{path_value}")
                    continue
                resolved = uploads_by_basename.get(base_name)
            if not resolved:
                if os.path.exists(path_value):
                    runtime_files[key] = path_value
                else:
                    missing.append(f"{key}:{path_value}")
                continue
            runtime_files[key] = resolved

        if ambiguous:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ambiguous uploaded filenames for YAML references: "
                    + ", ".join(sorted(ambiguous))
                    + ". Provide unique basenames or exact filename matches."
                ),
            )
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Missing files for YAML references: "
                    + ", ".join(sorted(missing))
                    + ". Upload matching files with the request."
                ),
            )

        if runtime_files:
            source_payload["_runtime_files"] = runtime_files
            checksums: dict[str, str] = {}
            for source_key, resolved_path in runtime_files.items():
                uploaded_checksum: str | None = uploaded_sha256_by_path.get(resolved_path)
                if uploaded_checksum:
                    checksums[source_key] = uploaded_checksum
            if checksums:
                source_payload["_uploaded_file_checksums"] = checksums

        if update_existing:
            _enforce_sample_ingest_permission(user)
        result = ingest_service.ingest_sample_bundle(
            source_payload,
            allow_update=update_existing,
            increment=increment,
        )
        return util.common.convert_to_serializable(result)
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        for upload in upload_refs:
            try:
                await upload.close()
            except Exception:
                pass
        shutil.rmtree(staging_dir, ignore_errors=True)


@router.post(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_document_internal(
    payload: InternalCollectionInsertRequest,
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
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
    "/api/v1/internal/ingest/collection/bulk",
    response_model=InternalCollectionInsertPayload,
)
def ingest_collection_documents_internal(
    payload: InternalCollectionBulkInsertRequest,
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
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


@router.put(
    "/api/v1/internal/ingest/collection",
    response_model=InternalCollectionUpsertPayload,
)
def upsert_collection_document_internal(
    payload: InternalCollectionUpsertRequest,
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
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


@router.post(
    "/api/v1/internal/ingest/collection/upload",
    response_model=InternalCollectionUploadPayload,
)
async def ingest_collection_upload_internal(
    collection: str = Form(...),
    mode: str = Form("insert"),
    documents_file: UploadFile = File(...),
    match_json: str | None = Form(default=None),
    user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
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
        bytes_payload = await documents_file.read()
        parsed = _parse_uploaded_collection_payload(documents_file.filename, bytes_payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON/NDJSON upload: {exc}",
        ) from exc
    finally:
        try:
            await documents_file.close()
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
    _user: ApiUser = Depends(require_access(min_role="developer", min_level=9999)),
    ingest_service: InternalIngestService = Depends(get_internal_ingest_service),
):
    """List supported collection names for validated collection-ingest endpoints."""
    return util.common.convert_to_serializable(
        {"status": "ok", "collections": ingest_service.list_supported_collections()}
    )


@router.get("/api/v1/internal/metrics", response_class=PlainTextResponse)
def get_prometheus_metrics_internal(request: Request):
    """Expose Prometheus metrics in text format for internal scraping."""
    _require_internal_token(request)
    return PlainTextResponse(
        content=render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
