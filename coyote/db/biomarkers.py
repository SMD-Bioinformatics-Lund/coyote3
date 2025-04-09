from coyote.db.base import BaseHandler


class BiomarkerHandler(BaseHandler):
    """
    Biomarker handler from coyote["biomarkers"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.biomarkers_collection)

    def get_sample_biomarkers_doc(self, sample_id: str, normal: bool = False):
        """
        Get biomarkers data as a full document for a sample
        """
        return self.get_collection().find({"SAMPLE_ID": sample_id})

    def get_sample_biomarkers(self, sample_id: str, normal: bool = False):
        """
        Get biomarkers data for a sample without _id, name  and SAMPLE_ID
        """
        return self.get_collection().find(
            {"SAMPLE_ID": sample_id}, {"_id": 0, "name": 0, "SAMPLE_ID": 0}
        )

    def delete_sample_biomarkers(self, sample_id: str):
        """
        Delete biomarkers data for a sample
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_id})
