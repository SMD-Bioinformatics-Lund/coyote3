import pymongo
from flask import current_app as app

class FusionsHandler:
    """
    Handles the fusions collections from the database
    """

    def get_sample_fusions(self, query: dict):
        """
        Return fusions with according to a constructed varquery
        """
        return self.fusions_collection.find(query)
    
    def get_selected_fusioncall(self, fusion):
        """
        Return the selected fusion call from the fusion data
        """
        for call in fusion.get("calls", []):
            if call.get("selected") == 1:
                return call
        return None
    
    def get_fusion_annotations(self, fusion):
        """
        Return annotations and latest classification for a given fusion
        """
        call = self.get_selected_fusioncall(fusion)
        if call and "breakpoint1" in call and "breakpoint2" in call:
            annotations = (
                self.annotations_collection
                .find({"variant": f"{call['breakpoint1']}^{call['breakpoint2']}"})
                .sort("time_created", 1)
            )
        else:
            annotations = None

        latest_classification = {"class": 999}
        annotations_arr = []
        if annotations:
            for anno in annotations:
                if "class" in anno:
                    latest_classification = anno
                elif "text" in anno:
                    annotations_arr.append(anno)

        return annotations_arr, latest_classification