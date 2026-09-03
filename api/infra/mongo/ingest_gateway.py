"""Mongo collection gateway for internal ingest workflows."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


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
                "users": store.coyote_db["users"],
                "roles": store.coyote_db["roles"],
                "permissions": store.coyote_db["permissions"],
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
        return self._collections[name]

    def sample_collection(self) -> Any:
        """Return the samples collection."""
        return self.collection("samples")

    def mongo_client(self) -> Any | None:
        """Return the underlying Mongo client when available."""
        database = getattr(self.sample_collection(), "database", None)
        return getattr(database, "client", None)

    def session_scope(self):
        """Return a best-effort Mongo session context when supported."""
        client = self.mongo_client()
        if client is None or not hasattr(client, "start_session"):
            return nullcontext(None)
        try:
            hello = client.admin.command("hello")
            if not (hello.get("setName") or hello.get("msg") == "isdbgrid"):
                return nullcontext(None)
        except Exception:
            return nullcontext(None)
        try:
            return client.start_session()
        except Exception:
            return nullcontext(None)
