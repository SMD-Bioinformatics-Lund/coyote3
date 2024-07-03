from bson.objectid import ObjectId
from flask_login import current_user
from datetime import datetime


class BaseHandler:
    """
    Base Handler for all the handlers
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.current_user = current_user

        # default collection for a given handler, must be set from inside the handler class
        self.handler_collection = None
        print(f"Inside Base: {self.adapter}")
        print(f"Inside Base: {self.adapter.client}")

    def hide_comment(self, var_id: str, comment_id: str) -> None:
        self.handler_collection.update_one(
            {"_id": ObjectId(var_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 1,
                    "comments.$.hidden_by": current_user.get_id(),
                    "comments.$.time_hidden": datetime.now(),
                }
            },
        )

    def unhide_comment(self, var_id: str, comment_id: str) -> None:
        """
        Unhide variant comment
        """
        self.handler_collection.update_one(
            {"_id": ObjectId(var_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 0,
                }
            },
        )

    def mark_false_positive(self, var_id: str, fp: bool) -> None:
        """
        Mark / Unmark variant as false
        """
        self.handler_collection.update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"fp": fp}},
        )

    def mark_interesting(self, var_id: str, interesting: bool) -> None:
        """
        Mark variant as interesting
        """
        self.handler_collection.update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"interesting": interesting}},
        )

    def mark_irrelevant(self, var_id: str, irrelevant: bool) -> None:
        """
        Mark / Unmark variant as irrelevant
        """
        self.handler_collection.update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"irrelevant": irrelevant}},
        )
