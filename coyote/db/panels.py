"""
Coyote gene panels db actions
"""

class PanelsHandler:

    def get_assay_panels(self, assay: str)->list:
        panels = list(self.panels_collection.find( { 'assays': { '$in': [assay] } }  ))
        gene_lists = {}
        for panel in panels:
            if panel['type'] == 'genelist':
                gene_lists[panel['name']] = panel['genes']
        return gene_lists, panels
    def get_panel(self, type: str, subpanel: str):
        panel = self.panels_collection.find_one( { 'name':subpanel, 'type': type } )
        return panel