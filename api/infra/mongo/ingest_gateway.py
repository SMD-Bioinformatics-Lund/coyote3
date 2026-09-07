"""Mongo collection gateway for internal ingest workflows."""

from __future__ import annotations

from typing import Any

from api.infra.mongo.persistence import insert_many_transaction
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
                "panel_coverage": store.coverage_repository.get_collection(),
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
                "insilico_genelists": store.gene_list_repository.get_collection(),
                "blacklist": store.blacklist_repository.get_collection(),
                "brcaexchange": store.brca_repository.get_collection(),
                "civic_genes": store.civic_gene_collection,
                "civic_variants": store.civic_repository.get_collection(),
                "cosmic": store.cosmic_repository.get_collection(),
                "group_coverage": store.grouped_coverage_repository.get_collection(),
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
        self._collections = dict(collections)

    def collection(self, name: str) -> Any:
        """Return a named ingest collection."""
        if name not in self._collections:
            raise ValueError(f"Unsupported ingest collection: {name}")
        return self._collections[name]

    def collection_names(self) -> set[str]:
        """Return the collections actually configured for this ingest gateway."""
        return set(self._collections)

    def sample_collection(self) -> Any:
        """Return the samples collection."""
        return self.collection("samples")

    def mongo_client(self) -> Any | None:
        """Return the underlying Mongo client when available."""
        database = getattr(self.sample_collection(), "database", None)
        return getattr(database, "client", None)

    def run_transaction(self, operation):
        """Commit all bundle writes together or propagate the transaction failure."""
        return run_transaction(self.mongo_client(), operation)

    def validate_completion_target(self, name):
        """Reject remote writes that cannot share the app's ingest receipt transaction."""
        if self.collection(name).database.client is not self.mongo_client():
            raise ValueError(
                "Async collection ingestion requires the target and job ledger to share "
                "a MongoDB client. Use synchronous ingestion or a maintenance importer "
                "for separately configured services."
            )

    def run_collection_transaction(self, name, operation):
        return run_transaction(self.collection(name).database.client, operation)

    def insert_documents(self, name, documents, *, ignore_duplicates=False, record_completion=None):
        """Insert a batch atomically, retrying without explicitly ignored duplicates.

        Duplicate errors abort a MongoDB transaction. Filter only the reported duplicate
        rows after abort, then retry the entire remaining batch, never a partial commit.
        """

        if record_completion is not None:
            self.validate_completion_target(name)

        def payload(ids):
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
