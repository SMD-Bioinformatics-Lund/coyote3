from coyote.db.base import BaseHandler
from flask import current_app as app
from bson.objectid import ObjectId
from datetime import datetime
from flask_login import current_user


class InsilicoGenelistHandler(BaseHandler):
    """
    Coyote gene panels db actions
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.insilico_genelist_collection)

    def insert_genelist(self, config: dict):
        """Insert a new genelist."""
        return self.get_collection().insert_one(config)

    def update_genelist(self, genelist_id: str, updated_data: dict):
        """Update an existing genelist."""
        return self.get_collection().replace_one({"_id": genelist_id}, updated_data)

    def get_genelist(self, genelist_id: str) -> dict | None:
        """Fetch a single genelist."""
        return self.get_collection().find_one({"_id": genelist_id})

    def get_all_genelists(self) -> list:
        """Fetch all genelists."""
        return list(self.get_collection().find({}, {"genes": 0}).sort([("created_on", -1)]))

    def toggle_genelist_active(self, genelist_id: str, active_status: bool) -> bool:
        """Toggle is_active field for a genelist."""
        return self.get_collection().update_one(
            {"_id": genelist_id}, {"$set": {"is_active": active_status}}
        )

    def delete_genelist(self, genelist_id: str):
        """Delete a genelist."""
        return self.get_collection().delete_one({"_id": genelist_id})

    def get_subpanels_for_panel(self, panel_name: str):
        """Filter genelists where this panel is associated, then collect diagnosis terms."""
        docs = self.get_collection().find({"assays": panel_name})
        diagnoses = set()
        for doc in docs:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_subpanels_for_assays(self, assay_ids: list[str]) -> list[str]:
        """Return unique diagnosis names for a list of assay IDs."""
        cursor = self.get_collection().find({"assays": {"$in": assay_ids}})
        diagnoses = set()
        for doc in cursor:
            for diag in doc.get("diagnosis", []):
                diagnoses.add(diag)
        return sorted(diagnoses)

    def get_genes_for_subpanel(self, diagnosis_name: str):
        """Return gene symbols associated with a given subpanel/diagnosis."""
        doc = self.get_collection().find_one({"diagnosis": diagnosis_name})
        return doc.get("genes", []) if doc else []

    def get_all_subpanels(self):
        return sorted(
            {d for doc in self.get_collection().find({}) for d in doc.get("diagnosis", [])}
        )

    def get_all_genes_from_subpanels(self, subpanels):
        """Flatten and deduplicate all genes from all subpanels."""
        genes = set()
        for diag in subpanels:
            doc = self.get_collection().find_one({"diagnosis": diag})
            genes.update(doc.get("genes", []))
        return list(genes)

    def get_gene_details_by_symbols(self, symbols: list[str]) -> list[dict]:
        """Fetch gene metadata for a list of gene symbols."""
        if not symbols:
            return []

        # TODO: Uncomment when gene collection is available
        # return list(self.genes_collection.find({"symbol": {"$in": symbols}}))
        return symbols
