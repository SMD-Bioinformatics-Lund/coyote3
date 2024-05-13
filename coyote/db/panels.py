"""
Coyote gene panels db actions
"""

class PanelsHandler:

    def get_assay_panels(self, assay: str)->list:
        panels = list(self.panels_collection.find( { 'assays': { '$in': [assay] } }  ))
        return panels