"""Sample-bundle orchestration helpers for internal ingest workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.application.ingest.dependent_writes import cleanup, data_counts, write_dependents
from api.application.ingest.helpers import (
    _normalize_uploaded_checksums,
    assay_default_filters_from_aspc_collection,
    build_sample_meta_dict,
    normalize_sample_version_metadata,
)
from api.application.ingest.sample_updates import ingest_update, next_unique_name
from api.contracts.schemas.samples import SamplesDoc
from api.domain.common.sample_filters import sample_filters_from_aspc_filters


def ingest_sample_bundle(
    service: Any,
    payload: dict[str, Any],
    *,
    allow_update: bool = False,
    increment: bool = False,
) -> dict[str, Any]:
    """Create a new sample and dependent analysis data, or update an existing one."""
    if not payload:
        raise ValueError("sample payload is required")

    parsed_payload = dict(payload)
    parsed_payload.pop("_id", None)
    parsed_payload.pop("data_counts", None)
    parsed_payload.pop("time_added", None)
    parsed_payload.pop("ingest_status", None)
    parsed_payload.pop("report_num", None)
    parsed_payload.pop("increment", None)
    parsed_payload.pop("update_existing", None)
    uploaded_checksums = _normalize_uploaded_checksums(
        parsed_payload.pop("_uploaded_file_checksums", None)
    )

    if not parsed_payload.get("name"):
        raise ValueError("name is required")

    if allow_update:
        return ingest_update(service, parsed_payload)

    parsed_payload = normalize_sample_version_metadata(parsed_payload)

    validated_sample = SamplesDoc.model_validate(parsed_payload)
    validated_payload = validated_sample.model_dump(exclude_none=True)
    if "filters" not in validated_payload:
        default_context = assay_default_filters_from_aspc_collection(
            service._collection("asp_configs"), validated_payload
        )
        if default_context is not None:
            validated_payload["filters"] = sample_filters_from_aspc_filters(
                default_context["filters"], validated_payload.get("omics_layer", "dna")
            )
            aspc = default_context.get("aspc") or {}
            validated_payload["current_aspc_id"] = aspc.get("_id")
            validated_payload["current_aspc_key"] = aspc.get("aspc_id")
            validated_payload["current_aspc_version"] = aspc.get("version")

    preload = service._parse_preload(validated_payload)
    sample_name = next_unique_name(service, str(validated_payload["name"]), bool(increment))
    sample_id = service._new_sample_id()
    counts = data_counts(preload)

    try:
        meta = build_sample_meta_dict(validated_payload)
        meta.update(
            {
                "_id": sample_id,
                "name": sample_name,
                "data_counts": counts,
                "time_added": datetime.now(timezone.utc),
                "ingest_status": "loading",
            }
        )
        if uploaded_checksums:
            meta["uploaded_file_checksums"] = uploaded_checksums

        final_sample = SamplesDoc.model_validate(meta)
        document = final_sample.model_dump(exclude_none=True)
        if "_id" in document:
            document["_id"] = service._provider_sample_id(str(document["_id"]))
        with service._session_scope() as session:
            with service._transaction_scope(session):
                sample_kwargs = {"session": session} if session is not None else {}
                service._sample_collection().insert_one(document, **sample_kwargs)
                written = write_dependents(
                    service,
                    preload=preload,
                    sample_id=sample_id,
                    sample_name=sample_name,
                    session=session,
                )
                service._sample_collection().update_one(
                    {"_id": service._provider_sample_id(str(sample_id))},
                    {"$set": {"ingest_status": "ready", "data_counts": counts}},
                    upsert=False,
                    **sample_kwargs,
                )

        service._invalidate_dashboard_cache_after_ingest()
    except Exception:
        cleanup(service, sample_id)
        raise

    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "sample_name": sample_name,
        "written": written,
        "data_counts": counts,
    }
