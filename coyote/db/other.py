from coyote.db.base import BaseHandler


class OtherHandler(BaseHandler):

    def __init__(self, adapter):
        super().__init__(adapter)

    def get_sample_other(self, sample_id: str, normal: bool = False):
        """
        Get other data for a sample
        """
        return self.adapter.biomarkers_collection.find({"SAMPLE_ID": sample_id})
