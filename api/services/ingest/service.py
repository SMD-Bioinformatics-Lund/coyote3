"""Internal sample-ingestion service for API-first ingest flows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from api.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    INGEST_SINGLE_DOCUMENT_KEYS,
    normalize_collection_document,
)
from api.contracts.schemas.samples import (
    SamplesDoc,  # noqa: F401 - re-exported for existing tests/importers
)
from api.core.dna.variant_identity import ensure_variant_identity_fields
from api.infra.mongo.persistence import (
    insert_many_documents,
    insert_one_document,
    new_object_id_str,
    to_provider_id,
)
from api.services.ingest.collection_writes import (
    list_supported_collections as _list_supported_collections,
)
from api.services.ingest.collection_writes import parse_yaml_payload as _parse_yaml_payload
from api.services.ingest.collection_writes import (
    upsert_collection_document as _upsert_collection_document,
)
from api.services.ingest.dependent_writes import cleanup as _cleanup
from api.services.ingest.dependent_writes import data_counts as _data_counts
from api.services.ingest.dependent_writes import ingest_dependents as _ingest_dependents
from api.services.ingest.helpers import (
    _normalize_case_control,  # noqa: F401 — re-exported for test namespace access
    _normalize_uploaded_checksums,
    build_sample_meta_dict,
)
from api.services.ingest.parsers import DnaIngestParser, RnaIngestParser, infer_omics_layer
from api.services.ingest.sample_updates import catch_left_right
from api.services.ingest.sample_updates import next_unique_name as _next_unique_name
from api.services.ingest.sample_updates import (
    prepare_update_payload as _prepare_update_payload,
)
from api.services.ingest.sample_updates import update_meta_fields as _update_meta_fields

logger = logging.getLogger(__name__)

_catch_left_right = catch_left_right


def _provider_sample_id(sample_id: str) -> Any:
    """Convert app-layer sample ids into provider-native ids when needed."""
    return to_provider_id(sample_id)


def _new_sample_id() -> str:
    """Return a new provider-native sample id serialized for the app layer."""
    return new_object_id_str()


class InternalIngestService:
    """API-side service that ingests a fresh sample plus analysis data atomically."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        dashboard_summary_cache_invalidator,
    ) -> "InternalIngestService":
        """Build the service from the shared store."""
        collections = {
            "samples": store.sample_handler.get_collection(),
            "variants": store.variant_handler.get_collection(),
            "cnvs": store.copy_number_variant_handler.get_collection(),
            "biomarkers": store.biomarker_handler.get_collection(),
            "translocations": store.translocation_handler.get_collection(),
            "panel_coverage": store.coverage_handler.get_collection(),
            "fusions": store.fusion_handler.get_collection(),
            "rna_expression": store.rna_expression_handler.get_collection(),
            "rna_classification": store.rna_classification_handler.get_collection(),
            "rna_qc": store.rna_quality_handler.get_collection(),
            "users": store.coyote_db["users"],
            "roles": store.coyote_db["roles"],
            "permissions": store.coyote_db["permissions"],
            "annotation": store.coyote_db["annotation"],
            "reported_variants": store.reported_variant_handler.get_collection(),
            "asp_configs": store.assay_configuration_handler.get_collection(),
            "assay_specific_panels": store.assay_panel_handler.get_collection(),
            "insilico_genelists": store.gene_list_handler.get_collection(),
            "blacklist": store.blacklist_handler.get_collection(),
            "brcaexchange": store.coyote_db["brcaexchange"],
            "civic_genes": store.civic_handler.get_collection(),
            "civic_variants": store.coyote_db["civic_variants"],
            "cosmic": store.coyote_db["cosmic"],
            "dashboard_metrics": store.coyote_db["dashboard_metrics"],
            "group_coverage": store.grouped_coverage_handler.get_collection(),
            "hgnc_genes": store.hgnc_handler.get_collection(),
            "hpaexpr": store.coyote_db["hpaexpr"],
            "iarc_tp53": store.iarc_tp53_handler.get_collection(),
            "mane_select": store.coyote_db["mane_select"],
            "oncokb_actionable": store.oncokb_handler.get_collection(),
            "oncokb_genes": store.coyote_db["oncokb_genes"],
            "refseq_canonical": store.coyote_db["refseq_canonical"],
            "vep_metadata": store.vep_metadata_handler.get_collection(),
            "asp_to_groups": store.coyote_db["asp_to_groups"],
        }
        return cls(
            sample_collection=collections["samples"],
            refseq_canonical_collection=collections["refseq_canonical"],
            collections=collections,
            invalidate_variant_cache=store.variant_handler.invalidate_dashboard_metrics_cache,
            invalidate_summary_cache=lambda: dashboard_summary_cache_invalidator(store),
        )

    def __init__(
        self,
        *,
        sample_collection: Any,
        refseq_canonical_collection: Any,
        collections: dict[str, Any],
        invalidate_variant_cache,
        invalidate_summary_cache,
    ) -> None:
        """Create the service with explicit handlers and datastore."""
        self.sample_collection = sample_collection
        self.refseq_canonical_collection = refseq_canonical_collection
        self.collections = collections
        self.invalidate_variant_cache = invalidate_variant_cache
        self.invalidate_summary_cache = invalidate_summary_cache

    def _sample_collection(self):
        """Return the sample collection used by internal ingest workflows."""
        return self.sample_collection

    def _collection(self, name: str):
        """Return the collection backing an ingest-dependent document type."""
        return self.collections[name]

    def _invalidate_dashboard_cache_after_ingest(self) -> None:
        """Refresh dashboard caches after ingest writes into sample/variant collections."""
        try:
            self.invalidate_variant_cache()
        except Exception as exc:
            logger.warning("ingest_dashboard_variant_cache_invalidate_failed error=%s", exc)
        try:
            self.invalidate_summary_cache()
        except Exception as exc:
            logger.warning("ingest_dashboard_summary_cache_invalidate_failed error=%s", exc)

    def list_supported_collections(self) -> list[str]:
        """List collection names that can be validated/inserted via ingest APIs."""
        return _list_supported_collections()

    def parse_yaml_payload(self, yaml_content: str) -> dict[str, Any]:
        """Parse and validate a YAML ingest payload string.

        Args:
            yaml_content: Raw YAML string from the request body.

        Returns:
            A dict decoded from the YAML string.

        Raises:
            ValueError: If the YAML does not decode to a dict or is missing mandatory fields.
        """
        return _parse_yaml_payload(yaml_content)

    def _canonical_map(self) -> dict[str, str]:
        """Build a gene-to-canonical-RefSeq mapping from reference data.

        Returns:
            A dict mapping gene symbol to canonical RefSeq accession (no version).
        """
        mapping: dict[str, str] = {}
        for doc in self.refseq_canonical_collection.find({}):
            gene = doc.get("gene")
            canonical = doc.get("canonical")
            if gene and canonical:
                mapping[gene] = canonical
        return mapping

    def _parse_preload(self, args: dict[str, Any]) -> dict[str, Any]:
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
            return DnaIngestParser(self._canonical_map()).parse(args)
        if omics_layer == "rna":
            return RnaIngestParser.parse(args)
        raise ValueError("Could not determine data type (DNA/RNA) from payload")

    def _normalize_collection_docs(
        self, collection: str, docs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalise a list of documents through the collection schema contract.

        Args:
            collection: Ingest alias of the target collection.
            docs: Raw document dicts to normalise.

        Returns:
            A list of normalised dicts validated against the collection contract.
        """
        return [normalize_collection_document(collection, doc) for doc in docs]

    def _write_dependents(
        self,
        *,
        preload: dict[str, Any],
        sample_id: str,
        sample_name: str,
    ) -> dict[str, int]:
        """Write all dependent analysis documents for a newly created sample.

        Iterates over each data type in preload and inserts the corresponding
        documents into the appropriate collection, tagging each with SAMPLE_ID.

        Args:
            preload: Parsed analysis data keyed by type (snvs, cnvs, cov, etc.).
            sample_id: Sample id of the newly inserted sample document.
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
            if key in INGEST_SINGLE_DOCUMENT_KEYS:
                if not isinstance(payload, dict):
                    raise TypeError(f"{key} expected dict, got {type(payload).__name__}")
                doc = dict(payload)
                doc["SAMPLE_ID"] = sid
                if key == "cov":
                    doc["sample"] = sample_name
                normalized_doc = self._normalize_collection_docs(col_name, [doc])[0]
                self._collection(col_name).insert_one(dict(normalized_doc))
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
            normalized_docs = self._normalize_collection_docs(col_name, docs)
            if normalized_docs:
                insert_many_documents(self._collection(col_name), normalized_docs)
            written[key] = len(normalized_docs)
        return written

    def ingest_dependents(
        self,
        *,
        sample_id: str,
        sample_name: str,
        delete_existing: bool,
        preload: dict[str, Any],
    ) -> dict[str, int]:
        """Insert dependent analysis payload for an existing sample id."""
        return _ingest_dependents(
            self,
            sample_id=sample_id,
            sample_name=sample_name,
            delete_existing=delete_existing,
            preload=preload,
        )

    def _cleanup(self, sample_id: str) -> None:
        """Roll back a failed ingest by deleting the sample and all its dependents.

        All deletions are attempted unconditionally; individual failures are
        silently swallowed so cleanup proceeds as far as possible.

        Args:
            sample_id: Sample id of the sample document to remove.
        """
        _cleanup(self, sample_id)

    def _data_counts(self, preload: dict[str, Any]) -> dict[str, int | bool]:
        """Count documents in each preload data type.

        Args:
            preload: Parsed analysis data keyed by type.

        Returns:
            A dict mapping each key to its document count (list length) or
            a boolean presence flag (for single-document types).
        """
        return _data_counts(preload)

    def _snapshot_dependents(
        self, *, sample_id: str, keys: set[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Back up existing dependent documents before a replacement operation.

        Args:
            sample_id: Sample id of the sample whose dependents to snapshot.
            keys: Set of data type keys to include in the snapshot.

        Returns:
            A dict mapping each key to the list of current documents for that type.
        """
        from api.services.ingest.dependent_writes import snapshot_dependents as _snapshot_dependents

        return _snapshot_dependents(self, sample_id=sample_id, keys=keys)

    def _restore_dependents(
        self, *, sample_id: str, sample_name: str, backup: dict[str, list[dict[str, Any]]]
    ) -> None:
        """Restore dependent documents from a prior snapshot after a failed replacement.

        Clears the current documents for each backed-up type and re-inserts
        the snapshot, stripping ``_id`` fields to avoid duplicate-key errors.

        Args:
            sample_id: Sample id of the sample whose dependents to restore.
            sample_name: Human-readable name (re-applied to coverage docs).
            backup: Snapshot produced by ``_snapshot_dependents``.
        """
        from api.services.ingest.dependent_writes import restore_dependents as _restore_dependents

        _restore_dependents(
            self,
            sample_id=sample_id,
            sample_name=sample_name,
            backup=backup,
        )

    def _replace_dependents(
        self, *, preload: dict[str, Any], sample_id: str, sample_name: str
    ) -> dict[str, int]:
        """Atomically replace dependent data with transactional rollback on failure.

        Snapshots the current dependents, deletes them, writes the new preload,
        and restores the snapshot if any step raises.

        Args:
            preload: New analysis data to write.
            sample_id: Sample id of the owning sample.
            sample_name: Human-readable name (used for coverage docs).

        Returns:
            A dict mapping data type keys to the count of documents written.

        Raises:
            Exception: Re-raises any exception after restoring from snapshot.
        """
        sid = str(sample_id)
        keys_to_replace = set(preload.keys())
        backup = self._snapshot_dependents(sample_id=sample_id, keys=keys_to_replace)
        try:
            for key, col_name in INGEST_DEPENDENT_COLLECTIONS.items():
                if key in keys_to_replace:
                    self._collection(col_name).delete_many({"SAMPLE_ID": sid})
            return self._write_dependents(
                preload=preload,
                sample_id=sample_id,
                sample_name=sample_name,
            )
        except Exception:
            self._restore_dependents(
                sample_id=sample_id,
                sample_name=sample_name,
                backup=backup,
            )
            raise

    def _prepare_update_payload(
        self, *, sample_doc: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate that the update payload preserves the existing omics layer.

        Ensures the requested omics_layer matches the existing sample and that
        no cross-layer file keys (RNA keys on a DNA sample, or vice versa) are present.

        Args:
            sample_doc: Current persisted sample document.
            payload: Proposed update payload (will be copied, not mutated).

        Returns:
            A normalised copy of payload with omics_layer set to the existing layer.

        Raises:
            ValueError: If the omics layer cannot be determined, or if the
                payload attempts a DNA↔RNA swap, or adds cross-layer file keys.
        """
        return _prepare_update_payload(self, sample_doc=sample_doc, payload=payload)

    def _update_meta_fields(
        self,
        *,
        sample_id: str,
        payload_meta: dict[str, Any],
        block_fields: set[str],
    ) -> None:
        """Update sample metadata fields, blocking changes to protected keys.

        Only fields whose values differ from the current document (or are absent)
        are written. ``_id`` and ``name`` are always skipped.

        Args:
            sample_id: Sample id of the sample to update.
            payload_meta: Dict of candidate field updates.
            block_fields: Set of field names that may not be changed.

        Raises:
            ValueError: If payload_meta contains a changed value for a blocked field.
        """
        _update_meta_fields(
            self,
            sample_id=sample_id,
            payload_meta=payload_meta,
            block_fields=block_fields,
        )

    def _ingest_update(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        if not payload:
            raise ValueError("sample payload is required")
        if not payload.get("name"):
            raise ValueError("name is required for update")

        current_doc = self._sample_collection().find_one({"name": payload["name"]})
        if not current_doc:
            raise ValueError("Sample not found for update")

        sample_id = str(current_doc["_id"])
        parsed_payload = self._prepare_update_payload(
            sample_doc=current_doc,
            payload=dict(payload),
        )
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
        from api.contracts.schemas.samples import SAMPLE_SOURCE_PATH_KEYS

        for key in SAMPLE_SOURCE_PATH_KEYS:
            if key in parsed_payload and parsed_payload.get(key):
                preload_payload[key] = parsed_payload[key]

        preload = self._parse_preload(preload_payload)
        counts = dict(current_doc.get("data_counts") or {})
        counts.update(self._data_counts(preload))

        self._update_meta_fields(
            sample_id=sample_id,
            payload_meta=build_sample_meta_dict(validated_merged.model_dump(exclude_none=True)),
            block_fields={"assay"},
        )
        self._sample_collection().update_one(
            {"_id": self._provider_sample_id(sample_id)},
            {"$set": {"ingest_status": "ready", "data_counts": counts}},
            upsert=False,
        )

        written = self._replace_dependents(
            preload=preload,
            sample_id=sample_id,
            sample_name=str(current_doc["name"]),
        )
        self._invalidate_dashboard_cache_after_ingest()
        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": str(current_doc["name"]),
            "written": written,
            "data_counts": counts,
        }

    def ingest_sample_bundle(
        self,
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
            return self._ingest_update(parsed_payload)

        validated_sample = SamplesDoc.model_validate(parsed_payload)
        validated_payload = validated_sample.model_dump(exclude_none=True)
        preload = self._parse_preload(validated_payload)
        sample_name = self._next_unique_name(str(validated_payload["name"]), bool(increment))
        sample_id = self._new_sample_id()
        counts = self._data_counts(preload)

        try:
            written = self._write_dependents(
                preload=preload,
                sample_id=sample_id,
                sample_name=sample_name,
            )
            meta = build_sample_meta_dict(validated_payload)
            meta.update(
                {
                    "_id": sample_id,
                    "name": sample_name,
                    "data_counts": counts,
                    "time_added": datetime.now(timezone.utc),
                    "ingest_status": "ready",
                }
            )
            if uploaded_checksums:
                meta["uploaded_file_checksums"] = uploaded_checksums

            final_sample = SamplesDoc.model_validate(meta)
            document = final_sample.model_dump(exclude_none=True)
            if "_id" in document:
                document["_id"] = self._provider_sample_id(str(document["_id"]))
            self._sample_collection().insert_one(document)
            self._invalidate_dashboard_cache_after_ingest()
        except Exception:
            self._cleanup(sample_id)
            raise

        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "sample_name": sample_name,
            "written": written,
            "data_counts": counts,
        }

    def insert_collection_document(
        self, *, collection: str, document: dict[str, Any], ignore_duplicate: bool = False
    ) -> dict[str, Any]:
        """Validate and insert one document into a supported collection."""
        normalized_doc = normalize_collection_document(collection, document)
        inserted_id = insert_one_document(
            self._collection(collection),
            dict(normalized_doc),
            ignore_duplicate=ignore_duplicate,
        )
        if inserted_id is None:
            return {"status": "ok", "collection": collection, "inserted_count": 0}
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": inserted_id,
        }

    def insert_collection_documents(
        self, *, collection: str, documents: list[dict[str, Any]], ignore_duplicates: bool = False
    ) -> dict[str, Any]:
        """Validate and insert many documents into a supported collection."""
        if not documents:
            return {"status": "ok", "collection": collection, "inserted_count": 0}
        normalized_docs = self._normalize_collection_docs(collection, documents)
        inserted_count = insert_many_documents(
            self._collection(collection),
            [dict(doc) for doc in normalized_docs],
            ignore_duplicates=ignore_duplicates,
        )
        return {
            "status": "ok",
            "collection": collection,
            "inserted_count": inserted_count,
        }

    def upsert_collection_document(
        self,
        *,
        collection: str,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
    ) -> dict[str, Any]:
        """Validate and replace one document in a supported collection."""
        return _upsert_collection_document(
            self,
            collection=collection,
            match=match,
            document=document,
            upsert=upsert,
        )

    def _next_unique_name(self, case_id: str, increment: bool) -> str:
        """Return a unique sample name, optionally auto-suffixing if name already exists."""
        return _next_unique_name(self, case_id, increment)

    @staticmethod
    def _provider_sample_id(sample_id: str) -> Any:
        """Convert app-layer sample ids into provider-native ids when needed."""
        return _provider_sample_id(sample_id)

    @staticmethod
    def _new_sample_id() -> str:
        """Return a new provider-native sample id serialized for the app layer."""
        return _new_sample_id()
