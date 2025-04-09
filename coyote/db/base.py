from bson.objectid import ObjectId
from flask_login import current_user
from flask import current_app as app
from flask import flash
from datetime import datetime
import pymongo


class BaseHandler:
    """
    Base Handler for all the handlers
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.current_user = current_user
        self.app = app

        # default collection for a given handler, must be set from inside the handler class
        self.handler_collection = None

    def set_collection(self, collection: pymongo.collection.Collection) -> None:
        self.handler_collection = collection

    def get_collection(self) -> pymongo.collection.Collection:
        if self.handler_collection is not None:
            return self.handler_collection
        else:
            raise NotImplementedError("get_collection or set_collection must be implemented")

    def hide_comment(self, var_id: str, comment_id: str) -> None:
        """
        Hide comment for a variant or a translocation or a cnv etc
        """

        if self.handler_collection.update_one(
            {"_id": ObjectId(var_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 1,
                    "comments.$.hidden_by": current_user.username,
                    "comments.$.time_hidden": datetime.now(),
                }
            },
        ):
            flash("Comment hidden", "green")
        else:
            flash("Comment failed to remove", "red")

    def unhide_comment(self, var_id: str, comment_id: str) -> None:
        """
        Unhide comment for a variant or a translocation or a cnv etc
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id), "comments._id": ObjectId(comment_id)},
            {
                "$set": {
                    "comments.$.hidden": 0,
                }
            },
        ):
            flash("Comment unhidden", "green")
        else:
            flash("Failed to unhide comment", "red")

    def mark_false_positive(self, var_id: str, fp: bool) -> None:
        """
        Mark / Unmark variant as false
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"fp": fp}},
        ):
            flash("Variant marked as False Positive", "green")
        else:
            flash("Failed to mark variant as False Positive", "red")

    def mark_interesting(self, var_id: str, interesting: bool) -> None:
        """
        Mark variant as interesting
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"interesting": interesting}},
        ):
            flash("Variant marked as Interesting", "green")
        else:
            flash("Failed to mark variant as Interesting", "red")

    def mark_irrelevant(self, var_id: str, irrelevant: bool) -> None:
        """
        Mark / Unmark variant as irrelevant
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"irrelevant": irrelevant}},
        ):
            flash("Variant marked as Irrelevant", "green")
        else:
            flash("Failed to mark variant as Irrelevant", "red")

    def mark_noteworthy(self, var_id: str, noteworthy: bool) -> None:
        """
        Mark / Unmark variant as noteworthy (it is intresting but may not be used to report, but can be used for future references)
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"noteworthy": noteworthy}},
        ):
            flash("Variant marked as Note Worthy", "green")
        else:
            flash("Failed to mark variant as Note Worthy", "red")

    def add_comment(self, comment_doc: dict) -> None:
        """
        Add comment to a variant
        """
        if self.get_collection().insert_one(comment_doc):
            flash("Comment added", "green")
        else:
            flash("Failed to add comment", "red")

    def update_comment(self, id: str, comment_doc: dict) -> None:
        """
        Update comment for a variant
        """
        if self.get_collection().update({"_id": ObjectId(id)}, comment_doc):
            flash("Comment added", "green")
        else:
            flash("Failed to add comment", "red")

    def hidden_comments(self, id: str) -> bool:
        """
        Get hidden comments for a document, example sample comments, variant comments etc
        """
        data = self.get_collection().find_one({"_id": ObjectId(id)}).get("comments")
        if data:
            return any(comment.get("hidden") for comment in data)
        return False
