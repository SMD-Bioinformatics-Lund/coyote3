from coyote.db.base import BaseHandler


class BiomarkerHandler(BaseHandler):
    """
    Biomarker handler from coyote["biomarkers"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.biomarkers_collection)

    def get_sample_other(self, sample_id: str, normal: bool = False):
        """
        Get biomarkers data for a sample
        """
        return self.get_collection().find({"SAMPLE_ID": sample_id})
