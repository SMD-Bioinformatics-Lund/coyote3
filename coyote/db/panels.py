from coyote.db.base import BaseHandler


class PanelsHandler(BaseHandler):
    """
    Coyote gene panels db actions
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.panels_collection)

    def get_assay_panels(self, assay: str) -> list:
        panels = list(self.get_collection().find({"assays": {"$in": [assay]}}))
        gene_lists = {}
        for panel in panels:
            if panel["type"] == "genelist":
                gene_lists[panel["name"]] = panel["genes"]
        return gene_lists, panels

    def get_panel(self, type: str, subpanel: str):
        panel = self.get_collection().find_one({"name": subpanel, "type": type})
        return panel
