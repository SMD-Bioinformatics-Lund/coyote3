"""Internal sample-ingestion service for API-first ingest flows."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import yaml
from bson.objectid import ObjectId
from pymongo.errors import BulkWriteError, DuplicateKeyError

from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
    normalize_collection_document,
    supported_collections,
)
from api.contracts.schemas.samples import (
    DNA_SAMPLE_FILE_KEYS,
    RNA_SAMPLE_FILE_KEYS,
    SAMPLE_SOURCE_PATH_KEYS,
    SamplesDoc,
)
from api.core.dna.variant_identity import ensure_variant_identity_fields
from api.extensions import store
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.services.ingest.helpers import (
    _normalize_case_control,  # noqa: F401 — re-exported for test namespace access
    _normalize_uploaded_checksums,
    _validate_yaml_payload_like_import_script,
    build_sample_meta_dict,
)
from api.services.ingest.parsers import DnaIngestParser, RnaIngestParser, infer_omics_layer

logger = logging.getLogger(__name__)


def _catch_left_right(case_id: str, name: str) -> tuple[str, str, str]:
    """Extract left-hand and right-hand suffixes relative to a case_id in a name string.

    Args:
        case_id: The base sample name to locate within name.
        name: Full sample name potentially containing a suffix after case_id.

    Returns:
        A tuple (left, right, matched_case_id). All empty strings if no match.
    """
    pattern = rf"(.*)({re.escape(case_id)})(.*)"
    match = re.match(pattern, name)
    if not match:
        return "", "", ""
    return match.group(1), match.group(3), match.group(2)


def _next_unique_name(case_id: str, increment: bool) -> str:
    """Return a unique sample name, optionally auto-suffixing if name already exists.

    Args:
        case_id: The requested sample name.
        increment: If True, append -N suffix to make the name unique.

    Returns:
        The original name if no conflict, or a suffixed variant like ``NAME-2``.

    Raises:
        ValueError: If the name already exists and increment is False, or if
            suffix resolution fails.
    """
    existing_exact = list(store.sample_handler.get_collection().find({"name": case_id}))
    if not existing_exact:
        return case_id
    if not increment:
        raise ValueError("Sample already exists; set increment=true to auto-suffix")

    suffixes: list[str] = []
    true_matches = 0
    for doc in store.sample_handler.get_collection().find({"name": {"$regex": case_id}}):
        left, right, true = _catch_left_right(case_id, doc["name"])
        if right and not left and true:
            suffixes.append(right)
            true_matches += 1

    max_suffix = 1
    if true_matches:
        if not suffixes:
            raise ValueError("Multiple exact matches found for sample name")
        for suffix in suffixes:
            match = re.match(r"-\d+", suffix)
            if match:
                number = int(suffix.replace("-", ""))
                if number > max_suffix:
                    max_suffix = number

    return f"{case_id}-{max_suffix + 1}"


class InternalIngestService:
    """API-side service that ingests a fresh sample plus analysis data atomically."""

    @staticmethod
    def _invalidate_dashboard_cache_after_ingest() -> None:
        """Refresh dashboard caches after ingest writes into sample/variant collections."""
        try:
            store.variant_handler.invalidate_dashboard_metrics_cache()
        except Exception as exc:
            logger.warning("ingest_dashboard_variant_cache_invalidate_failed error=%s", exc)
        try:
            invalidate_dashboard_summary_cache(store)
        except Exception as exc:
            logger.warning("ingest_dashboard_summary_cache_invalidate_failed error=%s", exc)

    @staticmethod
    def list_supported_collections() -> list[str]:
        """List collection names that can be validated/inserted via ingest APIs."""
        return supported_collections()

    @staticmethod
    def _resolve_collection(name: str):
        """Resolve collection by ingest alias from store handlers or raw DB."""
        handler_map = {
            "variants": "variant_handler",
            "cnvs": "cnv_handler",
            "biomarkers": "biomarker_handler",
            "transloc": "transloc_handler",
            "panel_coverage": "coverage_handler",
            "fusions": "fusion_handler",
            "rna_expression": "rna_expression_handler",
            "rna_classification": "rna_classification_handler",
            "rna_qc": "rna_qc_handler",
        }
        handler_name = handler_map.get(name)
        if handler_name and hasattr(store, handler_name):
            return getattr(store, handler_name).get_collection()
        return store.coyote_db[name]

    @staticmethod
    def parse_yaml_payload(yaml_content: str) -> dict[str, Any]:
        """Parse and validate a YAML ingest payload string.

        Args:
            yaml_content: Raw YAML string from the request body.

        Returns:
            A dict decoded from the YAML string.

        Raises:
            ValueError: If the YAML does not decode to a dict or is missing mandatory fields.
        """
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            raise ValueError("YAML body must decode to an object")
        _validate_yaml_payload_like_import_script(parsed)
        return parsed

    @staticmethod
    def _canonical_map() -> dict[str, str]:
        """Build a gene-to-canonical-RefSeq mapping from the refseq_canonical collection.

        Returns:
            A dict mapping gene symbol to canonical RefSeq accession (no version).
        """
        mapping: dict[str, str] = {}
        for doc in store.coyote_db["refseq_canonical"].find({}):
            gene = doc.get("gene")
            canonical = doc.get("canonical")
            if gene and canonical:
                mapping[gene] = canonical
        return mapping

    @classmethod
    def _parse_preload(cls, args: dict[str, Any]) -> dict[str, Any]:
        """Detect omics layer and delegate payload parsing to the appropriate parser.

        Args:
            args: Validated sample payload dict with file path keys and omics_layer.

        Returns:
            A preload dict keyed by data type (snvs, cnvs, fusions, etc.).

        Raises:
            ValueError: If the omics layer cannot be determined from the payload.
        """
        omics_layer = str(args.get("omics_layer") or "").strip().lower()
        if not omics_layer:
            omics_layer = infer_omics_layer(args) or ""
        if omics_layer == "dna":
            return DnaIngestParser(cls._canonical_map()).parse(args)
        if omics_layer == "rna":
            return RnaIngestParser.parse(args)
        raise ValueError("Could not determine data type (DNA/RNA) from payload")

    @classmethod
    def _normalize_collection_docs(
        cls, collection: str, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalise a list of documents through the collection schema contract.

        Args:
            collection: Ingest alias of the target collection.
            docs: Raw document dicts to normalise.

        Returns:
            A list of normalised dicts validated against the collection contract.
        """
        normalized: list[dict[str, Any]] = []
        for doc in docs:
            normalized.append(normalize_collection_document(collection, doc))
        return normalized

    @classmethod
    def _write_dependents(
        cls,
        *,
        preload: dict[str, Any],
        sample_id: ObjectId,
        sample_name: str,
    ) -> dict[str, int]:
        """Write all dependent analysis documents for a newly created sample.

        Iterates over each data type in preload and inserts the corresponding
        documents into the appropriate collection, tagging each with SAMPLE_ID.

        Args:
            preload: Parsed analysis data keyed by type (snvs, cnvs, cov, etc.).
            sample_id: ObjectId of the newly inserted samples document.
            sample_name: Human-readable sample name (used for coverage docs).

        Returns:
            A dict mapping data type keys to the count of documents written.

        Raises:
            TypeError: If a payload value has an unexpected type for its key.
        """
        sid = str(sample_id)
        written: dict[str, int] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in preload:
                continue
            payload = preload[key]
            col = cls._resolve_collection(col_name)

            if key in INGEST_SINGLE_DOCUMENT_KEYS:
                if not isinstance(payload, dict):
                    raise TypeError(f"{key} expected dict, got {type(payload).__name__}")
                doc = dict(payload)
                doc["SAMPLE_ID"] = sid
                if key == "cov":
                    doc["sample"] = sample_name
                normalized_doc = cls._normalize_collection_docs(col_name, [doc])[0]
                col.insert_one(normalized_doc)
                written[key] = 1
                continue

            if not isinstance(payload, (list, tuple)):
                raise TypeError(f"{key} expected list, got {type(payload).__name__}")
            docs: list[dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    raise TypeError(f"{key} contains non-dict item")
                doc = dict(item)
                doc["SAMPLE_ID"] = sid
                if key == "snvs":
                    doc = ensure_variant_identity_fields(doc)
                docs.append(doc)
            normalized_docs = cls._normalize_collection_docs(col_name, docs)
            if normalized_docs:
                col.insert_many(normalized_docs)
            written[key] = len(normalized_docs)
        return written

    @classmethod
    def ingest_dependents(
        cls,
        *,
        sample_id: str,
        sample_name: str,
        delete_existing: bool,
        preload: dict[str, Any],
    ) -> dict[str, int]:
        """Insert dependent analysis payload for an existing sample id."""
        sid = str(sample_id)
        written: dict[str, int] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in preload:
                continue
            col = cls._resolve_collection(col_name)
            if delete_existing:
                col.delete_many({"SAMPLE_ID": sid})

            raw_payload: Any = preload[key]
            if key in INGEST_SINGLE_DOCUMENT_KEYS:
                if not isinstance(raw_payload, dict):
                    raise ValueError(f"{key} expected dict payload")
                doc = dict(raw_payload)
                doc["SAMPLE_ID"] = sid
                if key == "cov":
                    doc["sample"] = sample_name
                normalized_doc = cls._normalize_collection_docs(col_name, [doc])[0]
                col.insert_one(normalized_doc)
                written[key] = 1
                continue

            if not isinstance(raw_payload, (list, tuple)):
                raise ValueError(f"{key} expected list payload")
            docs: list[dict[str, Any]] = []
            for item in raw_payload:
                if not isinstance(item, dict):
                    raise ValueError(f"{key} contains non-dict item")
                doc = dict(item)
                doc["SAMPLE_ID"] = sid
                if key == "snvs":
                    doc = ensure_variant_identity_fields(doc)
                docs.append(doc)
            normalized_docs = cls._normalize_collection_docs(col_name, docs)
            if normalized_docs:
                col.insert_many(normalized_docs)
            written[key] = len(normalized_docs)
        return written

    @classmethod
    def _cleanup(cls, sample_id: ObjectId) -> None:
        """Roll back a failed ingest by deleting the sample and all its dependents.

        All deletions are attempted unconditionally; individual failures are
        silently swallowed so cleanup proceeds as far as possible.

        Args:
            sample_id: ObjectId of the sample document to remove.
        """
        sid = str(sample_id)
        for collection in INGEST_DEPENDENT_COLLECTIONS.values():
            try:
                store.coyote_db[collection].delete_many({"SAMPLE_ID": sid})
            except Exception:
                pass
        try:
            store.sample_handler.get_collection().delete_one({"_id": sample_id})
        except Exception:
            pass

    @staticmethod
    def _data_counts(preload: dict[str, Any]) -> dict[str, int | bool]:
        """Count documents in each preload data type.

        Args:
            preload: Parsed analysis data keyed by type.

        Returns:
            A dict mapping each key to its document count (list length) or
            a boolean presence flag (for single-document types).
        """
        return {
            key: (len(preload[key]) if isinstance(preload[key], list) else bool(preload[key]))
            for key in preload
        }

    @classmethod
    def _snapshot_dependents(
        cls, *, sample_id: ObjectId, keys: set[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Back up existing dependent documents before a replacement operation.

        Args:
            sample_id: ObjectId of the sample whose dependents to snapshot.
            keys: Set of data type keys to include in the snapshot.

        Returns:
            A dict mapping each key to the list of current documents for that type.
        """
        sid = str(sample_id)
        backup: dict[str, list[dict[str, Any]]] = {}
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key in keys:
                backup[key] = list(store.coyote_db[col_name].find({"SAMPLE_ID": sid}))
        return backup

    @classmethod
    def _restore_dependents(
        cls, *, sample_id: ObjectId, sample_name: str, backup: dict[str, list[dict[str, Any]]]
    ) -> None:
        """Restore dependent documents from a prior snapshot after a failed replacement.

        Clears the current documents for each backed-up type and re-inserts
        the snapshot, stripping ``_id`` fields to avoid duplicate-key errors.

        Args:
            sample_id: ObjectId of the sample whose dependents to restore.
            sample_name: Human-readable name (re-applied to coverage docs).
            backup: Snapshot produced by ``_snapshot_dependents``.
        """
        sid = str(sample_id)
        for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
            if key not in backup:
                continue
            col = store.coyote_db[col_name]
            col.delete_many({"SAMPLE_ID": sid})
            docs = backup[key]
            if docs:
                restored: list[dict[str, Any]] = []
                for doc in docs:
                    d = dict(doc)
                    d.pop("_id", None)
                    if key == "cov":
                        d["sample"] = sample_name
                    restored.append(d)
                col.insert_many(restored)

    @classmethod
    def _replace_dependents(
        cls, *, preload: dict[str, Any], sample_id: ObjectId, sample_name: str
    ) -> dict[str, int]:
        """Atomically replace dependent data with transactional rollback on failure.

        Snapshots the current dependents, deletes them, writes the new preload,
        and restores the snapshot if any step raises.

        Args:
            preload: New analysis data to write.
            sample_id: ObjectId of the owning sample.
            sample_name: Human-readable name (used for coverage docs).

        Returns:
            A dict mapping data type keys to the count of documents written.

        Raises:
            Exception: Re-raises any exception after restoring from snapshot.
        """
        sid = str(sample_id)
        keys_to_replace = set(preload.keys())
        backup = cls._snapshot_dependents(sample_id=sample_id, keys=keys_to_replace)
        try:
            for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
                if key in keys_to_replace:
                    store.coyote_db[col_name].delete_many({"SAMPLE_ID": sid})
            return cls._write_dependents(
                preload=preload, sample_id=sample_id, sample_name=sample_name
            )
        except Exception:
            cls._restore_dependents(sample_id=sample_id, sample_name=sample_name, backup=backup)
            raise

    @classmethod
    def _prepare_update_payload(
        cls, *, sample_doc: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate that the update payload preserves the existing omics layer.

        Ensures the requested omics_layer matches the existing sample and that
        no cross-layer file keys (RNA keys on a DNA sample, or vice versa) are present.

        Args:
            sample_doc: Current sample document from MongoDB.
            payload: Proposed update payload (will be copied, not mutated).

        Returns:
            A normalised copy of payload with omics_layer set to the existing layer.

        Raises:
            ValueError: If the omics layer cannot be determined, or if the
                payload attempts a DNA↔RNA swap, or adds cross-layer file keys.
        """
        normalized = dict(payload)
        existing_layer = str(sample_doc.get("omics_layer") or "").strip().lower()
        if existing_layer not in {"dna", "rna"}:
            existing_layer = infer_omics_layer(sample_doc) or ""
        if existing_layer not in {"dna", "rna"}:
            raise ValueError("Cannot determine existing sample data type for update")

        requested_layer = str(normalized.get("omics_layer") or existing_layer).strip().lower()
        if requested_layer != existing_layer:
            raise ValueError(
                f"Sample omics_layer is '{existing_layer}' and cannot be changed to '{requested_layer}'"
            )

        forbidden_keys = RNA_SAMPLE_FILE_KEYS if existing_layer == "dna" else DNA_SAMPLE_FILE_KEYS
        bad_keys = [key for key in forbidden_keys if normalized.get(key)]
        if bad_keys:
            raise ValueError(
                f"Cannot add {'RNA' if existing_layer == 'dna' else 'DNA'} data to an existing {existing_layer.upper()} sample"
            )

        normalized["omics_layer"] = existing_layer
        return normalized

    @classmethod
    def _update_meta_fields(
        cls,
        *,
        sample_id: ObjectId,
        payload_meta: dict[str, Any],
        block_fields: set[str],
    ) -> None:
        """Update sample metadata fields, blocking changes to protected keys.

        Only fields whose values differ from the current document (or are absent)
        are written. ``_id`` and ``name`` are always skipped.

        Args:
            sample_id: ObjectId of the sample to update.
            payload_meta: Dict of candidate field updates.
            block_fields: Set of field names that may not be changed.

        Raises:
            ValueError: If payload_meta contains a changed value for a blocked field.
        """
        sample_col = store.sample_handler.get_collection()
        current = sample_col.find_one({"_id": sample_id}) or {}
        update_fields: dict[str, Any] = {}
        for key, value in payload_meta.items():
            if key in {"_id", "name"}:
                continue
            if key in current and current[key] != value:
                if key in block_fields:
                    raise ValueError(f"No support to update {key} as of yet")
                update_fields[key] = value
            elif key not in current:
                update_fields[key] = value
        if update_fields:
            sample_col.update_one({"_id": sample_id}, {"$set": update_fields}, upsert=False)

    @classmethod
    def _ingest_update(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle the sample update flow: validate payload, update metadata and dependents.

        Locates the existing sample by name, validates the update payload against
        the current document's omics layer, updates metadata fields, and replaces
        dependent analysis data with transactional rollback.

        Args:
            payload: Update payload dict containing at minimum a ``name`` key.

        Returns:
            A result dict with keys ``status``, ``sample_id``, ``sample_name``,
            ``written``, and ``data_counts``.

        Raises:
            ValueError: If payload is empty, missing name, or sample is not found.
        """
        sample_col = store.sample_handler.get_collection()

        if not payload:
            raise ValueError("sample payload is required")
        if not payload.get("name"):
            raise ValueError("name is required for update")

        current_doc = sample_col.find_one({"name": payload["name"]})
        if not current_doc:
            raise ValueError("Sample not found for update")

        sample_id = current_doc["_id"]

        # Prepare update payload using existing sample context
        parsed_payload = cls._prepare_update_payload(
            sample_doc=current_doc,
            payload=dict(payload),
        )

        # Strip DB-managed / operation-only fields before validation
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

        # Validate merged document shape through the strict contract.
        merged_doc = dict(current_doc)
        merged_doc.update(parsed_payload)
        if uploaded_checksums:
            existing_checksums = _normalize_uploaded_checksums(
                current_doc.get("uploaded_file_checksums", {})
            )
            existing_checksums.update(uploaded_checksums)
            merged_doc["uploaded_file_checksums"] = existing_checksums
        validated_merged = SamplesDoc.model_validate(merged_doc)
        validated_payload = validated_merged.model_dump(exclude_none=True)

        preload_payload: dict[str, Any] = {"omics_layer": validated_payload["omics_layer"]}
        runtime_files = parsed_payload.get("_runtime_files")
        if isinstance(runtime_files, dict) and runtime_files:
            preload_payload["_runtime_files"] = dict(runtime_files)
        for key in SAMPLE_SOURCE_PATH_KEYS:
            if key in parsed_payload and parsed_payload.get(key):
                preload_payload[key] = parsed_payload[key]

        preload = cls._parse_preload(preload_payload)
        data_counts = dict(current_doc.get("data_counts") or {})
        data_counts.update(cls._data_counts(preload))

        # Keep the same update flow ordering as scripts/import_coyote_sample.py:
        # update sample metadata + counts/status first, then rewrite dependents.
        merged_doc["name"] = current_doc["name"]
        merged_doc["data_counts"] = data_counts
        merged_doc["ingest_status"] = "ready"

        cls._update_meta_fields(
            sample_id=sample_id,
            payload_meta=build_sample_meta_dict(validated_merged.model_dump(exclude_none=True)),
            block_fields={"assay"},
        )

        sample_col.update_one(
            {"_id": sample_id},
            {"$set": {"ingest_status": "ready", "data_counts": data_counts}},
            upsert=False,
        )

        written = cls._replace_dependents(
            preload=preload,
            sample_id=sample_id,
            sample_name=str(current_doc["name"]),
        )

        cls._invalidate_dashboard_cache_after_ingest()

        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": str(current_doc["name"]),
            "written": written,
            "data_counts": data_counts,
        }

    @classmethod
    def ingest_sample_bundle(
        cls,
        payload: dict[str, Any],
        *,
        allow_update: bool = False,
        increment: bool = False,
    ) -> dict[str, Any]:
        """Create a fresh sample with all dependent analysis data, or update an existing one.

        When ``allow_update=True`` and a sample with the same name already exists,
        delegates to ``_ingest_update`` instead of creating a new sample.
        On creation failure, rolls back all written documents via ``_cleanup``.

        Args:
            payload: Sample payload dict. Must contain at minimum a ``name`` key.
            allow_update: If True, update an existing sample instead of raising on conflict.
            increment: If True, auto-append a numeric suffix to make the name unique.

        Returns:
            A result dict with keys ``status``, ``sample_id``, ``sample_name``,
            ``written``, and ``data_counts``.

        Raises:
            ValueError: If payload is empty or missing name.
        """
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
            return cls._ingest_update(parsed_payload)

        validated_sample = SamplesDoc.model_validate(parsed_payload)
        validated_payload = validated_sample.model_dump(exclude_none=True)

        preload = cls._parse_preload(validated_payload)
        sample_name = _next_unique_name(str(validated_payload["name"]), bool(increment))
        sample_id = ObjectId()
        data_counts = cls._data_counts(preload)

        try:
            written = cls._write_dependents(
                preload=preload,
                sample_id=sample_id,
                sample_name=sample_name,
            )

            meta = build_sample_meta_dict(validated_payload)
            meta.update(
                {
                    "_id": sample_id,
                    "name": sample_name,
                    "data_counts": data_counts,
                    "time_added": datetime.now(timezone.utc),
                    "ingest_status": "ready",
                }
            )
            if uploaded_checksums:
                meta["uploaded_file_checksums"] = uploaded_checksums

            final_sample = SamplesDoc.model_validate(meta)
            store.sample_handler.get_collection().insert_one(
                final_sample.model_dump(exclude_none=True)
            )

            cls._invalidate_dashboard_cache_after_ingest()

        except Exception:
            cls._cleanup(sample_id)
            raise

        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": sample_name,
            "written": written,
            "data_counts": data_counts,
        }

    @classmethod
    def insert_collection_document(
        cls, *, collection: str, document: dict[str, Any], ignore_duplicate: bool = False
    ) -> dict[str, Any]:
        """Validate and insert one document into a supported collection."""
        normalized_doc = normalize_collection_document(collection, document)
        try:
            result = cls._resolve_collection(collection).insert_one(dict(normalized_doc))
        except DuplicateKeyError:
            if ignore_duplicate:
                return {
                    "status": "ok",
                    "collection": collection,
                    "inserted_count": 0,
                }
            raise
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": str(result.inserted_id),
        }

    @classmethod
    def insert_collection_documents(
        cls, *, collection: str, documents: list[dict[str, Any]], ignore_duplicates: bool = False
    ) -> dict[str, Any]:
        """Validate and insert many documents into a supported collection."""
        if not documents:
            return {"status": "ok", "collection": collection, "inserted_count": 0}
        normalized_docs = cls._normalize_collection_docs(collection, documents)
        inserted_count = 0
        try:
            result = cls._resolve_collection(collection).insert_many(
                [dict(doc) for doc in normalized_docs], ordered=False
            )
            inserted_count = len(result.inserted_ids)
        except BulkWriteError as exc:
            if not ignore_duplicates:
                raise
            details = exc.details or {}
            inserted_count = int(details.get("nInserted", 0))
            write_errors = details.get("writeErrors", []) or []
            non_duplicate_errors = [w for w in write_errors if w.get("code") != 11000]
            if non_duplicate_errors:
                raise
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": inserted_count,
        }

    @classmethod
    def upsert_collection_document(
        cls,
        *,
        collection: str,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        """Validate and replace one document in a supported collection."""
        if not isinstance(match, dict) or not match:
            raise ValueError("match must be a non-empty object")
        normalized_doc = normalize_collection_document(collection, document)
        result = cls._resolve_collection(collection).replace_one(
            filter=match,
            replacement=normalized_doc,
            upsert=bool(upsert),
        )
        return {
            "status": "ok",
            "collection": collection,
            "matched_count": int(result.matched_count or 0),
            "modified_count": int(result.modified_count or 0),
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }
