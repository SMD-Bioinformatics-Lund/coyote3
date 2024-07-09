from bson.objectid import ObjectId
from coyote.db.base import BaseHandler


class FusionHandler(BaseHandler):
    """
    Fusions  handler from coyote["fusions"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.fusion_collection)

    def add_fusion_comment(self, fusion_id: str, comment_doc: dict) -> None:
        """
        Add comment to a Fusion
        """
        self.update_comment(fusion_id, comment_doc)
