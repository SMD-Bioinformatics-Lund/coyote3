"""Repository operations for transactional ingest workflows."""

from __future__ import annotations

from typing import Any

from api.domain.core.internal.results import ReplaceDocumentResult
from api.infra.mongo.persistence import insert_many_transaction
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.transactions import run_transaction


class IngestCollectionGateway:
    """Provide named Mongo collections and session helpers for ingest services."""

    @classmethod
    def from_store(cls, store: Any) -> "IngestCollectionGateway":
        """Build the gateway from the runtime repository store."""
        return cls(
            collections={
                "samples": store.sample_repository.get_collection(),
                "variants": store.variant_repository.get_collection(),
                "anno_vep": store.anno_vep_repository.get_collection(),
                "cnvs": store.copy_number_variant_repository.get_collection(),
                "biomarkers": store.biomarker_repository.get_collection(),
                "translocations": store.translocation_repository.get_collection(),
                "d4_coverage": store.d4_coverage_repository.get_collection(),
                "fusions": store.fusion_repository.get_collection(),
                "rna_expression": store.rna_expression_repository.get_collection(),
                "rna_classification": store.rna_classification_repository.get_collection(),
                "rna_qc": store.rna_quality_repository.get_collection(),
                "users": store.user_repository.get_collection(),
                "roles": store.roles_repository.get_collection(),
                "permissions": store.permissions_repository.get_collection(),
                "annotation": store.coyote_db["annotation"],
                "reported_variants": store.reported_variant_repository.get_collection(),
                "asp_configs": store.assay_configuration_repository.get_collection(),
                "assay_specific_panels": store.assay_panel_repository.get_collection(),
                "assay_groups": store.assay_group_repository.get_collection(),
                "insilico_genelists": store.gene_list_repository.get_collection(),
                "blacklist": store.blacklist_repository.get_collection(),
                "brcaexchange": store.brca_repository.get_collection(),
                "civic_genes": store.civic_gene_collection,
                "civic_variants": store.civic_repository.get_collection(),
                "cosmic": store.cosmic_repository.get_collection(),
                "d4_coverage_blacklist": store.d4_coverage_blacklist_repository.get_collection(),
                "hgnc_genes": store.hgnc_repository.get_collection(),
                "hpaexpr": store.expression_repository.get_collection(),
                "iarc_tp53": store.iarc_tp53_repository.get_collection(),
                "mane_select": store.coyote_db["mane_select"],
                "oncokb_actionable": store.oncokb_actionable_collection,
                "oncokb_genes": store.oncokb_genes_collection,
                "oncokb_public": store.oncokb_public_cache_repository.get_collection(),
                "oncokb_genes_public": (store.oncokb_public_cache_repository.gene_collection),
                "oncokb_cancer_genes_public": (
                    store.oncokb_public_cache_repository.cancer_gene_collection
                ),
                "clinpgx_genes_public": store.clinpgx_public_repository.get_collection(),
                "vep_metadata": store.vep_metadata_repository.get_collection(),
                "asp_to_groups": store.coyote_db["asp_to_groups"],
            }
        )

    def __init__(self, *, collections: dict[str, Any]) -> None:
        """Copy the mapping of collection names permitted for ingestion.

        Args:
            collections: Ingest names mapped to MongoDB collection handles.
        """
        self._collections = dict(collections)

    def collection(self, name: str) -> Any:
        """Return a named ingest collection."""
        if name not in self._collections:
            raise ValueError(f"Unsupported ingest collection: {name}")
        return self._collections[name]

    def collection_names(self) -> set[str]:
        """Return the collections actually configured for this ingest gateway."""
        return set(self._collections)

    def find_document(
        self, name: str, selector: dict[str, Any], *, session: Any = None
    ) -> dict[str, Any] | None:
        """Read a configured ingest document on its owning client's transaction.

        Args:
            name: Registered logical ingest collection name.
            selector: Exact MongoDB predicate prepared by the workflow.
            session: Session from the destination client; None reads outside a transaction.

        Returns:
            The matching document, or None when it does not exist.

        Raises:
            ValueError: The logical collection is not configured for ingestion.
        """
        return self.collection(name).find_one(selector, session=session)

    def hgnc_documents(self, projection: dict[str, int]) -> list[dict[str, Any]]:
        """Read reference gene metadata used to normalize transcript annotations.

        Args:
            projection: HGNC fields required for symbol/transcript resolution.

        Returns:
            Projected reference documents from the configured knowledgebase collection.
        """
        return list(self.collection("hgnc_genes").find({}, projection))

    def sample_names(self, selector: dict[str, Any]) -> list[dict[str, Any]]:
        """Read existing sample names for collision detection before ingest.

        Args:
            selector: Exact-name or escaped-name-pattern predicate.

        Returns:
            Matching sample identifiers and names without other clinical metadata.
        """
        return list(self.sample_collection().find(selector, {"name": 1}))

    def insert_dependent(self, name: str, document: dict[str, Any], *, session: Any) -> None:
        """Insert one validated measurement in the active bundle transaction.

        Args:
            name: Registered destination for the measurement.
            document: Validated measurement with canonical sample ownership.
            session: Owning bundle session; None is reserved for direct test/import callers.
        """
        kwargs = {"session": session} if session is not None else {}
        self.collection(name).insert_one(dict(document), **kwargs)

    def insert_dependents(
        self, name: str, documents: list[dict[str, Any]], *, session: Any
    ) -> None:
        """Insert validated finding rows without starting another transaction.

        Args:
            name: Registered destination for the finding type.
            documents: Validated rows containing canonical sample ownership.
            session: Active bundle session passed through to the bulk writer.
        """
        from api.infra.mongo.persistence import insert_many_documents

        insert_many_documents(self.collection(name), documents, session=session)

    def delete_dependents(self, name: str, sample_id: str, *, session: Any) -> None:
        """Remove evidence owned by one sample before transactional replacement.

        Args:
            name: Registered destination for the evidence type.
            sample_id: Canonical serialized sample identifier matched against SAMPLE_ID.
            session: Active bundle session containing replacement writes.
        """
        self.collection(name).delete_many({"SAMPLE_ID": sample_id}, session=session)

    def document_count(self, name: str) -> int:
        """Return estimated occupancy without scanning all ingest records.

        Args:
            name: Registered logical ingest collection name.

        Returns:
            Estimated document count; zero for an empty collection.
        """
        return int(self.collection(name).estimated_document_count() or 0)

    def create_sample(self, document: dict[str, Any], *, session: Any) -> None:
        """Insert validated sample metadata inside the bundle transaction.

        Args:
            document: Current-schema sample anchor with its preallocated provider ID.
            session: Application-database transaction shared with dependent writes.
        """
        self.sample_collection().insert_one(dict(document), session=session)

    def set_sample_fields(
        self, selector: dict[str, Any], fields: dict[str, Any], *, session: Any
    ) -> None:
        """Set prepared sample state fields inside the owning bundle transaction.

        Args:
            selector: Sample identity predicate already checked by the workflow.
            fields: Validated metadata/state values to set; no upsert is performed.
            session: Owning application-database transaction.
        """
        self.sample_collection().update_one(selector, {"$set": fields}, session=session)

    def replace_document(
        self,
        name: str,
        selector: dict[str, Any],
        document: dict[str, Any],
        *,
        upsert: bool,
        session: Any,
    ) -> ReplaceDocumentResult:
        """Replace a validated ingest document and return portable write counts.

        Args:
            name: Registered logical ingest collection name.
            selector: Nonempty identity predicate validated by the application.
            document: Complete validated replacement, including preserved provenance.
            upsert: Permit insertion when the selector has no match.
            session: Destination-client transaction, never a different database client's session.

        Returns:
            Matched/modified counts and the serialized inserted ID when upserted.
        """
        result = self.collection(name).replace_one(
            filter=selector, replacement=document, upsert=upsert, session=session
        )
        return ReplaceDocumentResult(
            matched_count=int(result.matched_count or 0),
            modified_count=int(result.modified_count or 0),
            upserted_id=str(result.upserted_id) if result.upserted_id else None,
        )

    def sample_collection(self) -> Any:
        """Return the samples collection."""
        return self.collection("samples")

    def sample_biomarkers(self, sample_id: str, *, session: Any) -> list[dict[str, Any]]:
        """Read measurements in the same transaction that will replace supplied analyses.

        Args:
            sample_id: Parent sample's string identifier.
            session: Active ingest transaction from this gateway's application client.

        Returns:
            Existing measurement documents, including their source identity.
        """
        return list(self.collection("biomarkers").find({"SAMPLE_ID": sample_id}, session=session))

    def mongo_client(self) -> Any | None:
        """Return the underlying Mongo client when available."""
        database = getattr(self.sample_collection(), "database", None)
        return getattr(database, "client", None)

    def run_transaction(self, operation):
        """Commit all bundle writes together or propagate the transaction failure."""

        def audited(session):
            """Include a bundle receipt before committing the sample transaction."""
            result = operation(session)
            enqueue_audit(
                self.sample_collection().database,
                session,
                event_type="ingest.bundle_committed",
                resource_type="sample_bundle",
                resource_id=(result or {}).get("sample_id", "batch"),
            )
            return result

        return run_transaction(self.mongo_client(), audited)

    def validate_completion_target(self, name):
        """Reject remote writes that cannot share the app's ingest receipt transaction."""
        if self.collection(name).database.client is not self.mongo_client():
            raise ValueError(
                "Async collection ingestion requires the target and job ledger to share "
                "a MongoDB client. Use synchronous ingestion or a maintenance importer "
                "for separately configured services."
            )

    def run_collection_transaction(self, name, operation):
        """Run a transaction on the client owning a named ingest collection.

        Args:
            name: Configured ingest collection name.
            operation: Callback receiving the transaction's session.

        Returns:
            The callback's result after successful transaction completion.

        Raises:
            ValueError: If the collection name is not configured.

        Notes:
            Transaction failures propagate from the shared transaction runner.
        """

        def audited(session):
            """Include a collection-ingest receipt on the owning database's connection."""
            result = operation(session)
            enqueue_audit(
                self.collection(name).database,
                session,
                event_type="ingest.collection_committed",
                resource_type=name,
                resource_id="batch",
            )
            return result

        return run_transaction(self.collection(name).database.client, audited)

    def insert_documents(self, name, documents, *, ignore_duplicates=False, record_completion=None):
        """Insert a batch atomically, retrying without explicitly ignored duplicates.

        Duplicate errors abort a MongoDB transaction. Filter only the reported duplicate
        rows after abort, then retry the entire remaining batch, never a partial commit.
        """

        if record_completion is not None:
            self.validate_completion_target(name)

        def payload(ids):
            """Build an ingest receipt from the successfully inserted identifiers.

            Args:
                ids: Serialized identifiers from the insertion batch.

            Returns:
                Status, collection, and inserted count, plus an inserted ID only
                when the original batch contained one document and it was inserted.
            """
            result = {
                "status": "ok",
                "collection": name,
                "inserted_count": len(ids),
            }
            if len(documents) == 1 and ids:
                result["inserted_id"] = ids[0]
            return result

        ids = insert_many_transaction(
            self.collection(name),
            documents,
            ignore_duplicates=ignore_duplicates,
            on_insert=(lambda ids, session: record_completion(payload(ids), session))
            if record_completion is not None
            else None,
        )
        return payload(ids)
