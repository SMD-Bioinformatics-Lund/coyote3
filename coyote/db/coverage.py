from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app


class CoverageHandler(BaseHandler):
    """
    Coverage handler from coyote["coverage"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.coverage_collection)

    def get_sample_coverage(self, sample_name: str) -> list[dict]:
        """
        Get coverage for a gene and assay
        """
        coverage = self.get_collection().find({"sample": sample_name})
        return list(coverage)

    def delete_sample_coverage(self, sample_oid: str):
        """
        Delete coverage for a sample
        """
        return self.get_collection().delete_many({"sample": sample_oid})
