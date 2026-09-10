"""Internal sample-ingestion service for API-first ingest flows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from api.application.ingest import collection_writes, dependent_writes, helpers, sample_updates
from api.application.ingest.file_policy import (
    assay_file_policy,
    readable_file_payload,
    validate_declared_file_resources,
    validate_payload_file_keys,
)
from api.application.ingest.helpers import (
    assay_default_filters_from_aspc_collection,
    build_sample_meta_dict,
    normalize_sample_version_metadata,
)
from api.application.ingest.parsers import (
    DnaIngestParser,
    RnaIngestParser,
    infer_omics_layer,
)
from api.config.constants import (
    manifest_file_preload_keys,
    non_database_manifest_file_keys,
)
from api.contracts.schemas.registry import normalize_collection_document
from api.contracts.schemas.samples import (
    SAMPLE_SOURCE_PATH_KEYS,
    SamplesDoc,
)
from api.domain.common.sample_filters import sample_filters_from_aspc_filters
from api.infra.mongo.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.persistence import (
    new_object_id_str,
    to_provider_id,
)

logger = logging.getLogger(__name__)


def _provider_sample_id(sample_id: str) -> Any:
    """Convert app-layer sample ids into provider-native ids when needed."""
    return to_provider_id(sample_id)


def _new_sample_id() -> str:
    """Return a new provider-native sample id serialized for the app layer."""
    return new_object_id_str()


class InternalIngestService:
    """Validate and persist sample bundles with readiness and recovery handling."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        dashboard_metrics_invalidator,
        audit_service: Any | None = None,
        notification_service: Any | None = None,
        monitoring_group: str = "monitoring_group",
    ) -> "InternalIngestService":
        """Bind ingestion and optional warning delivery to runtime repositories.

        Args:
            store: Runtime repositories and databases used for ingestion.
            dashboard_metrics_invalidator: Callback accepting the store after commit.
            audit_service: Warning audit recorder, or None to disable audit delivery.
            notification_service: Inbox service, or None to disable inbox delivery.
            monitoring_group: Role whose active members receive inbox warnings.

        Returns:
            Ingestion service with transaction and warning dependencies attached.
        """
        return cls(
            collection_gateway=IngestCollectionGateway.from_store(store),
            anno_vep_repository=store.anno_vep_repository,
            invalidate_dashboard_metrics=lambda: dashboard_metrics_invalidator(store),
            audit_service=audit_service,
            notification_service=notification_service,
            monitoring_group=monitoring_group,
        )

    def __init__(
        self,
        *,
        collection_gateway: IngestCollectionGateway,
        anno_vep_repository: Any,
        invalidate_dashboard_metrics,
        audit_service: Any | None = None,
        notification_service: Any | None = None,
        monitoring_group: str = "monitoring_group",
    ) -> None:
        """Create ingestion with transaction and post-commit warning dependencies.

        Args:
            collection_gateway: Owns sample collections and transaction execution.
            anno_vep_repository: Stores parsed variant annotations.
            invalidate_dashboard_metrics: Callback invoked after committed ingestion.
            audit_service: Optional recorder for missing-file warning events.
            notification_service: Optional service resolving and notifying group members.
            monitoring_group: Recipient role; blank disables inbox warnings.
        """
        self.collection_gateway = collection_gateway
        self.anno_vep_repository = anno_vep_repository
        self.invalidate_dashboard_metrics = invalidate_dashboard_metrics
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.monitoring_group = monitoring_group

    def _missing_expected_files(self, payload: dict[str, Any], available: set[str]) -> list[str]:
        """Return configured expected resources absent from this ingest's readable inputs.

        Args:
            payload: Sample carrying its ASP identifier and omics layer.
            available: File keys validated as readable for this ingest attempt.

        Returns:
            Sorted missing expected file keys from the active ASP contract.
        """
        expected, _required = self._assay_file_policy(
            assay_name=payload.get("asp_id"), omics_layer=payload.get("omics_layer")
        )
        return sorted(expected - available)

    def _report_missing_expected_files(self, result: dict[str, Any]) -> None:
        """Log and notify about committed incomplete samples without undoing ingestion.

        Args:
            result: Committed sample identity and missing expected file keys.

        Notes:
            A structured warning is picked up by the disk monitor for retryable
            email delivery. Audit and inbox failures are logged independently.
        """
        missing = result.get("missing_expected_files") or []
        if not missing:
            return
        message = (
            f"Sample {result['sample_name']} ingested with unavailable expected files: "
            + ", ".join(missing)
            + ". Required files passed validation; ingestion proceeded."
        )
        metadata = {"sample_id": result["sample_id"], "missing_expected_files": missing}
        logger.warning(message, extra={"event_type": "ingest.expected_files_missing", **metadata})
        if self.audit_service is not None:
            try:
                self.audit_service.record(
                    "ingest.expected_files_missing",
                    message,
                    category="data",
                    severity="warning",
                    outcome="warning",
                    resource_type="sample",
                    resource_id=result["sample_id"],
                    resource_name=result["sample_name"],
                    metadata=metadata,
                    tags=["ingest"],
                )
            except Exception:
                logger.exception("Could not audit missing expected ingest files")
        if self.notification_service is not None and self.monitoring_group.strip():
            try:
                users = (
                    self.notification_service.user_repository.list_active_users_for_notifications(
                        role_ids=[self.monitoring_group]
                    )
                )
                recipients = [str(user["username"]) for user in users if user.get("username")]
                if recipients:
                    self.notification_service.create_notification(
                        audience="users",
                        recipients=recipients,
                        tone="warning",
                        category="application",
                        title="Sample ingested with unavailable data",
                        message=message,
                        source="Sample ingestion",
                        created_by="system",
                        severity="warning",
                        resource={"type": "sample", "id": result["sample_id"]},
                    )
            except Exception:
                logger.exception("Could not notify missing expected ingest files")

    def _sample_collection(self):
        """Return the sample collection used by internal ingest workflows."""
        return self.collection_gateway.sample_collection()

    def _mongo_client(self) -> Any | None:
        """Return the underlying Mongo client when available."""
        return self.collection_gateway.mongo_client()

    def _collection(self, name: str):
        """Return the collection backing an ingest-dependent document type."""
        return self.collection_gateway.collection(name)

    def _invalidate_dashboard_metrics_after_ingest(self) -> None:
        """Invalidate dashboard metrics after a completed ingest write."""
        try:
            self.invalidate_dashboard_metrics()
        except Exception as exc:
            logger.warning("ingest_dashboard_metrics_invalidate_failed error=%s", exc)

    def list_supported_collections(self) -> list[str]:
        """List collection names that can be validated/inserted via ingest APIs."""
        return sorted(
            set(collection_writes.list_supported_collections())
            & self.collection_gateway.collection_names()
        )

    def preflight_sample_name(
        self, payload: dict[str, Any], *, allow_update: bool = False, increment: bool = False
    ) -> None:
        """Reject duplicate creation before reading declared analysis files.

        Args:
            payload: Parsed manifest containing the sample name.
            allow_update: Permit the existing sample update workflow.
            increment: Permit automatic naming of a new sample copy.

        Raises:
            ValueError: The name is missing or already exists without either option.
        """
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("name is required")
        if not allow_update and not increment:
            self._next_unique_name(name, False)

    def parse_yaml_payload(self, yaml_content: str) -> dict[str, Any]:
        """Parse and validate a YAML ingest payload string.

        Args:
            yaml_content: Raw YAML string from the request body.

        Returns:
            A dict decoded from the YAML string.

        Raises:
            ValueError: If the YAML does not decode to a dict or is missing mandatory fields.
        """
        return collection_writes.parse_yaml_payload(yaml_content)

    def _hgnc_metadata_maps(self) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        """Build HGNC metadata lookup maps by HGNC ID and symbol aliases."""
        by_id: dict[str, dict[str, Any]] = {}
        by_symbol: dict[str, dict[str, Any]] = {}
        projection = {
            "_id": 1,
            "hgnc_id": 1,
            "hgnc_symbol": 1,
            "prev_symbol": 1,
            "alias_symbol": 1,
            "refseq_mane_select": 1,
            "ensembl_mane_select": 1,
            "refseq_mane_plus_clinical": 1,
            "ensembl_mane_plus_clinical": 1,
        }
        try:
            hgnc_collection = self._collection("hgnc_genes")
        except KeyError:
            return by_id, by_symbol
        for doc in hgnc_collection.find({}, projection):
            hgnc_id = str(doc.get("hgnc_id") or doc.get("_id") or "").strip()
            if hgnc_id and not hgnc_id.startswith("HGNC:"):
                hgnc_id = f"HGNC:{hgnc_id}"
            if hgnc_id:
                by_id[hgnc_id] = doc
            symbols: list[str] = []
            if doc.get("hgnc_symbol"):
                symbols.append(str(doc["hgnc_symbol"]))
            for key in ("prev_symbol", "alias_symbol"):
                value = doc.get(key)
                if isinstance(value, list):
                    symbols.extend(str(item) for item in value if str(item).strip())
                elif value:
                    symbols.append(str(value))
            for symbol in symbols:
                normalized_symbol = str(symbol).strip()
                if normalized_symbol:
                    by_symbol.setdefault(normalized_symbol, doc)
                    by_symbol.setdefault(normalized_symbol.upper(), doc)
        return by_id, by_symbol

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
            hgnc_by_id, hgnc_by_symbol = self._hgnc_metadata_maps()
            return DnaIngestParser(
                hgnc_by_id=hgnc_by_id,
                hgnc_by_symbol=hgnc_by_symbol,
            ).parse(args)
        if omics_layer == "rna":
            return RnaIngestParser.parse(args)
        raise ValueError("Could not determine data type (DNA/RNA) from payload")

    def _assay_file_policy(
        self,
        *,
        assay_name: str | None,
        omics_layer: str | None,
    ) -> tuple[set[str], set[str]]:
        """Return ASP-controlled expected and required file keys for an assay."""
        return assay_file_policy(self._collection, assay_name=assay_name, omics_layer=omics_layer)

    def _validate_payload_file_keys(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Reject declared file resources outside the active ASP contract."""
        return validate_payload_file_keys(self._collection, payload)

    def _validate_declared_file_resources(self, payload: dict[str, Any]) -> set[str]:
        """Validate assay file policy and declared file paths before parsing.

        Required ASP files must be present and readable. Missing or unreadable
        optional expected files are recorded as unavailable, whether or not a
        path was declared. Readable inputs must parse and write successfully.
        """
        return validate_declared_file_resources(self._collection, payload)

    def _apply_resolved_aspc_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach the exact active ASPC policy snapshot required for a new sample.

        Ingested samples never accept a filter profile authored in the manifest.
        Their initial intent profiles and ASPC lineage come from the resolved
        ASPC for the exact ASP, subpanel, and environment scope.
        """
        resolved = assay_default_filters_from_aspc_collection(
            self._collection("asp_configs"), payload
        )
        if resolved is None:
            raise ValueError(
                f"No active ASPC is configured for assay='{payload.get('asp_id')}', "
                f"subpanel='{payload.get('subpanel_id') or 'base'}', "
                f"environment='{payload.get('environment') or 'production'}'. "
                "Create or activate the matching analysis configuration."
            )
        aspc = dict(resolved.get("aspc") or {})
        normalized = dict(payload)
        normalized["filters"] = sample_filters_from_aspc_filters(
            resolved.get("filters"),
            normalized.get("omics_layer", "dna"),
            analysis_intents=aspc.get("analysis_intents"),
        )
        normalized["analysis_intents"] = aspc.get("analysis_intents") or ["somatic"]
        normalized["current_aspc_id"] = aspc.get("_id")
        normalized["current_aspc_key"] = aspc.get("aspc_id")
        normalized["current_aspc_version"] = aspc.get("version")
        normalized["aspc_resolution"] = resolved.get("aspc_resolution")
        return normalized

    @staticmethod
    def _validate_preload_matches_declared_files(
        *, declared_file_keys: set[str], preload: dict[str, Any], omics_layer: str | None
    ) -> None:
        """Ensure each declared database-backed file produced a parsed preload section."""
        if not declared_file_keys:
            return
        if not omics_layer:
            raise ValueError("omics_layer is required to validate declared ingest files")
        missing_sections: list[str] = []
        preload_keys = manifest_file_preload_keys(omics_layer)
        non_database_keys = non_database_manifest_file_keys(omics_layer)
        for file_key in sorted(declared_file_keys - non_database_keys):
            preload_key = preload_keys.get(file_key)
            if preload_key and preload_key not in preload:
                missing_sections.append(f"{file_key}->{preload_key}")
        if missing_sections:
            raise ValueError(
                "Declared ingest file(s) did not produce database payloads: "
                + ", ".join(missing_sections)
            )

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
        normalized = []
        for index, doc in enumerate(docs, start=1):
            try:
                normalized.append(normalize_collection_document(collection, doc))
            except ValidationError as exc:
                errors = exc.errors(include_input=False, include_context=False, include_url=False)
                detail = "; ".join(
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in errors[:5]
                )
                raise ValueError(
                    f"{collection} record {index} failed validation: {detail}"
                ) from exc
        return normalized

    def _write_dependents(
        self,
        *,
        preload: dict[str, Any],
        sample_id: str,
        sample_name: str,
        session: Any | None = None,
    ) -> dict[str, int]:
        """Write parsed analysis data through the shared dependent-write workflow."""
        return dependent_writes.write_dependents(
            self,
            preload=preload,
            sample_id=sample_id,
            sample_name=sample_name,
            session=session,
        )

    def _data_counts(self, preload: dict[str, Any]) -> dict[str, int | bool]:
        """Count documents in each preload data type.

        Args:
            preload: Parsed analysis data keyed by type.

        Returns:
            A dict mapping each key to its document count (list length) or
            a boolean presence flag (for single-document types).
        """
        return dependent_writes.data_counts(preload)

    def _replace_dependents(
        self, *, preload: dict[str, Any], sample_id: str, sample_name: str, session: Any
    ) -> dict[str, int]:
        """Replace declared evidence within the owning sample transaction."""
        return dependent_writes.replace_dependents(
            self,
            preload=preload,
            sample_id=sample_id,
            sample_name=sample_name,
            session=session,
        )

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
        return sample_updates.prepare_update_payload(self, sample_doc=sample_doc, payload=payload)

    def _update_meta_fields(
        self,
        *,
        sample_id: str,
        payload_meta: dict[str, Any],
        block_fields: set[str],
        session: Any | None = None,
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
        sample_updates.update_meta_fields(
            self,
            sample_id=sample_id,
            payload_meta=payload_meta,
            block_fields=block_fields,
            session=session,
        )

    def _ingest_update(self, payload: dict[str, Any], *, record_completion=None) -> dict[str, Any]:
        """Handle the sample update flow: validate payload, update metadata and dependents.

        Locates the existing sample by name, validates the update payload against
        the current document's omics layer, updates metadata fields, and replaces
        dependent analysis data and metadata in one required MongoDB transaction.

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

        for key in ("asp_id", "environment"):
            if payload.get(key) != current_doc.get(key):
                raise ValueError(f"Sample ingest cannot change {key}; use sample administration.")

        sample_id = str(current_doc["_id"])
        parsed_payload = self._prepare_update_payload(
            sample_doc=current_doc,
            payload=dict(payload),
        )
        parsed_payload = self._validate_payload_file_keys(parsed_payload)
        parsed_payload = normalize_sample_version_metadata(parsed_payload)
        declared_file_keys = self._validate_declared_file_resources(parsed_payload)
        parsed_payload["missing_expected_files"] = self._missing_expected_files(
            parsed_payload, declared_file_keys
        )
        parsed_payload.pop("_id", None)
        parsed_payload.pop("data_counts", None)
        parsed_payload.pop("time_added", None)
        parsed_payload.pop("ingest_status", None)
        parsed_payload.pop("report_num", None)
        parsed_payload.pop("increment", None)
        parsed_payload.pop("update_existing", None)
        uploaded_checksums = helpers.normalize_uploaded_checksums(
            parsed_payload.pop("_uploaded_file_checksums", None)
        )

        merged_doc = dict(current_doc)
        merged_doc.update(parsed_payload)
        if uploaded_checksums:
            existing_checksums = helpers.normalize_uploaded_checksums(
                current_doc.get("uploaded_file_checksums", {})
            )
            existing_checksums.update(uploaded_checksums)
            merged_doc["uploaded_file_checksums"] = existing_checksums
        validated_merged = SamplesDoc.model_validate(merged_doc)
        validated_payload = validated_merged.model_dump(exclude_none=True)

        preload_payload: dict[str, Any] = {"omics_layer": validated_payload["omics_layer"]}
        if validated_payload.get("files"):
            preload_payload["files"] = validated_payload["files"]
        runtime_files = parsed_payload.get("_runtime_files")
        if isinstance(runtime_files, dict) and runtime_files:
            preload_payload["_runtime_files"] = dict(runtime_files)
        for key in SAMPLE_SOURCE_PATH_KEYS:
            if key in parsed_payload and parsed_payload.get(key):
                preload_payload[key] = parsed_payload[key]

        preload = self._parse_preload(readable_file_payload(preload_payload, declared_file_keys))
        self._validate_preload_matches_declared_files(
            declared_file_keys=declared_file_keys,
            preload=preload,
            omics_layer=validated_payload.get("omics_layer"),
        )
        counts = dict(current_doc.get("data_counts") or {})
        counts.update(self._data_counts(preload))

        def update(session):
            """Apply the prepared sample update and dependent replacements in one session.

            Args:
                session: Transaction session supplied by the collection gateway.

            Returns:
                Success status, sample identity, dependent write results, and data counts.

            Raises:
                ValueError: The stored sample differs from the document used for preparation.

            Notes:
                Sets loading before writes and ready afterward. The optional completion
                callback runs in the same session before returning to the transaction runner.
            """
            selector = {"_id": self._provider_sample_id(sample_id)}
            current = self._sample_collection().find_one(selector, session=session)
            if current != current_doc:
                raise ValueError("Sample changed while the update was prepared; retry the update")
            self._sample_collection().update_one(
                selector, {"$set": {"ingest_status": "loading"}}, session=session
            )
            self._update_meta_fields(
                sample_id=sample_id,
                payload_meta=build_sample_meta_dict(validated_merged.to_persistence_document()),
                block_fields={"asp_id", "environment"},
                session=session,
            )
            written = self._replace_dependents(
                preload=preload,
                sample_id=sample_id,
                sample_name=str(current_doc["name"]),
                session=session,
            )
            self._sample_collection().update_one(
                selector,
                {"$set": {"ingest_status": "ready", "data_counts": counts}},
                session=session,
            )
            result = {
                "status": "ok",
                "sample_id": str(sample_id),
                "sample_name": str(current_doc["name"]),
                "written": written,
                "data_counts": counts,
                "missing_expected_files": parsed_payload["missing_expected_files"],
            }
            if record_completion is not None:
                record_completion(result, session)
            return result

        result = self.collection_gateway.run_transaction(update)
        self._invalidate_dashboard_metrics_after_ingest()
        self._report_missing_expected_files(result)
        return result

    def ingest_sample_bundle(
        self,
        payload: dict[str, Any],
        *,
        allow_update: bool = False,
        increment: bool = False,
        record_completion=None,
    ) -> dict[str, Any]:
        """Create a fresh sample with all dependent analysis data, or update an existing one.

        When ``allow_update=True`` and a sample with the same name already exists,
        delegates to ``_ingest_update`` instead of creating a new sample.
        MongoDB aborts every write when creation or update fails.

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
        uploaded_checksums = helpers.normalize_uploaded_checksums(
            parsed_payload.pop("_uploaded_file_checksums", None)
        )
        if not parsed_payload.get("name"):
            raise ValueError("name is required")
        if allow_update:
            return self._ingest_update(parsed_payload, record_completion=record_completion)

        self.preflight_sample_name(parsed_payload, increment=increment)
        parsed_payload = self._validate_payload_file_keys(parsed_payload)
        parsed_payload = normalize_sample_version_metadata(parsed_payload)
        declared_file_keys = self._validate_declared_file_resources(parsed_payload)
        parsed_payload["missing_expected_files"] = self._missing_expected_files(
            parsed_payload, declared_file_keys
        )
        parsed_payload = self._apply_resolved_aspc_snapshot(parsed_payload)

        validated_sample = SamplesDoc.model_validate(parsed_payload)
        validated_payload = validated_sample.model_dump(exclude_none=True)
        preload = self._parse_preload(readable_file_payload(validated_payload, declared_file_keys))
        self._validate_preload_matches_declared_files(
            declared_file_keys=declared_file_keys,
            preload=preload,
            omics_layer=validated_payload.get("omics_layer"),
        )
        sample_name = self._next_unique_name(str(validated_payload["name"]), bool(increment))
        sample_id = self._new_sample_id()
        counts = self._data_counts(preload)

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
        document = SamplesDoc.model_validate(meta).to_persistence_document()
        document["_id"] = self._provider_sample_id(sample_id)

        def create(session):
            """Insert the prepared sample and dependent analyses in the supplied transaction.

            Args:
                session: Transaction session supplied by the collection gateway.

            Returns:
                Success status, sample identity, dependent write results, and data counts.

            Notes:
                Marks the sample ready after dependent writes, then invokes the optional
                completion callback in the same session. Write/callback failures propagate.
            """
            self._sample_collection().insert_one(dict(document), session=session)
            written = self._write_dependents(
                preload=preload, sample_id=sample_id, sample_name=sample_name, session=session
            )
            self._sample_collection().update_one(
                {"_id": document["_id"]},
                {"$set": {"ingest_status": "ready", "data_counts": counts}},
                session=session,
            )
            result = {
                "status": "ok",
                "sample_id": str(sample_id),
                "sample_name": sample_name,
                "written": written,
                "data_counts": counts,
                "missing_expected_files": parsed_payload["missing_expected_files"],
            }
            if record_completion is not None:
                record_completion(result, session)
            return result

        result = self.collection_gateway.run_transaction(create)
        self._invalidate_dashboard_metrics_after_ingest()
        self._report_missing_expected_files(result)
        return result

    def insert_collection_document(
        self,
        *,
        collection: str,
        document: dict[str, Any],
        ignore_duplicate: bool = False,
        record_completion=None,
    ) -> dict[str, Any]:
        """Validate and insert one document into a supported collection."""
        normalized_doc = normalize_collection_document(collection, document)
        return self.collection_gateway.insert_documents(
            collection,
            [normalized_doc],
            ignore_duplicates=ignore_duplicate,
            record_completion=record_completion,
        )

    def collection_document_count(self, collection: str) -> int:
        """Return the current document count for a supported collection."""
        if collection not in self.list_supported_collections():
            raise ValueError(f"Unsupported collection: {collection}")
        return int(self._collection(collection).estimated_document_count() or 0)

    def insert_collection_documents(
        self,
        *,
        collection: str,
        documents: list[dict[str, Any]],
        ignore_duplicates: bool = False,
        record_completion=None,
    ) -> dict[str, Any]:
        """Validate and insert many documents into a supported collection."""
        normalized_docs = self._normalize_collection_docs(collection, documents)
        return self.collection_gateway.insert_documents(
            collection,
            normalized_docs,
            ignore_duplicates=ignore_duplicates,
            record_completion=record_completion,
        )

    def upsert_collection_document(
        self,
        *,
        collection: str,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = False,
        record_completion=None,
    ) -> dict[str, Any]:
        """Validate and replace one document in a supported collection."""
        if record_completion is not None:
            self.validate_async_collection(collection)

        def replace(session):
            """Validate and replace the enclosing collection document within one session.

            Args:
                session: Target collection's session supplied by the transaction gateway.

            Returns:
                Status, collection name, matched/modified counts, and optional upserted ID.

            Raises:
                ValueError: The match is empty/invalid or document normalization fails.

            Notes:
                Runs the optional completion callback with the replacement result and
                the same session before returning to the transaction runner.
            """
            result = collection_writes.upsert_collection_document(
                self,
                collection=collection,
                match=match,
                document=document,
                upsert=upsert,
                session=session,
            )
            if record_completion is not None:
                record_completion(result, session)
            return result

        return self.collection_gateway.run_collection_transaction(collection, replace)

    def validate_async_collection(self, collection: str) -> None:
        """Check whether target data and the job receipt can share one transaction."""
        self.collection_gateway.validate_completion_target(collection)

    def _next_unique_name(self, case_id: str, increment: bool) -> str:
        """Return a unique sample name, optionally auto-suffixing if name already exists."""
        return sample_updates.next_unique_name(self, case_id, increment)

    @staticmethod
    def _provider_sample_id(sample_id: str) -> Any:
        """Convert app-layer sample ids into provider-native ids when needed."""
        return _provider_sample_id(sample_id)

    @staticmethod
    def _new_sample_id() -> str:
        """Return a new provider-native sample id serialized for the app layer."""
        return _new_sample_id()
