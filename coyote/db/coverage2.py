from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app


class CoverageHandler2(BaseHandler):
    """
    Coverage handler from coyote["coverage"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.coverage2_collection)

    def get_sample_coverage(self, sample_name: str) -> dict:
        """
        Get coverage for a gene and assay
        """
        app.logger.debug(sample_name)
        coverage = self.get_collection().find_one({"SAMPLE_ID": sample_name})
        return coverage

    def delete_sample_coverage(self, sample_oid: str):
        """
        Delete coverage data for a sample
        """
        return self.get_collection().delete_many({"SAMPLE_ID": sample_oid})
