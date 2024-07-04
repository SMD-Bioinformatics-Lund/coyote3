from coyote.db.base import BaseHandler


class OnkoKBHandler(BaseHandler):
    """
    OncoKB handler from OncoKB["oncokb"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.oncokb_collection)

    def get_oncokb_anno(self, variant: dict, oncokb_hgvsp: str) -> dict:
        """
        Get OncoKB annotation for a variant
        """
        return self.get_collection().find_one(
            {"Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"], "Alteration": {"$in": oncokb_hgvsp}}
        )

    def get_oncokb_action(self, variant: dict, oncokb_hgvsp: str) -> dict:
        """
        Get OncoKB actionable for a variant
        """
        return self.adapter.oncokb_actionable_collection.find(
            {
                "Gene": variant["INFO"]["selected_CSQ"]["SYMBOL"],
                "Alteration": {"$in": [oncokb_hgvsp, "Oncogenic Mutations"]},
            }
        )

    def get_oncokb_gene(self, gene: str) -> dict:
        """
        Get OncoKB gene for a gene
        """
        return self.adapter.oncokb_genes_collection.find_one({"name": gene})
