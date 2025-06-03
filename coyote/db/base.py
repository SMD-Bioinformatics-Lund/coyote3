# -*- coding: utf-8 -*-
"""
CoverageHandler module for Coyote3
==================================

This module defines the `BaseHandler` class used for accessing and managing
generic data in MongoDB.

It is part of the `coyote.db` package and will be used as a base class for the rest of the handlers in this package.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from bson.objectid import ObjectId
from flask_login import current_user
from typing import Any
from flask import current_app as app
from flask import flash
from datetime import datetime
import pymongo


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BaseHandler:
    """
    Base Handler for all the handlers.

    This class provides a foundational structure for managing and interacting
    with MongoDB collections. It includes methods for performing common
    operations such as adding, updating, hiding, and marking data, which can
    be extended by other handler classes.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        self.adapter = adapter
        self.current_user = current_user
        self.app = app

        # default collection for a given handler, must be set from inside the handler class
        self.handler_collection = None

    def set_collection(
        self, collection: pymongo.collection.Collection
    ) -> None:
        """
        Set the collection for the handler.

        This method assigns a specific MongoDB collection to the handler, which will
        be used for all subsequent database operations.

        Args:
            collection (pymongo.collection.Collection): The MongoDB collection to bind
            to the handler.
        """
        self.handler_collection = collection

    def get_collection(self) -> pymongo.collection.Collection:
        """
        Get the MongoDB collection bound to the handler.

        This method retrieves the MongoDB collection that has been set for the handler.
        If no collection has been set, it raises a `NotImplementedError`.

        Returns:
            pymongo.collection.Collection: The MongoDB collection bound to the handler.

        Raises:
            NotImplementedError: If no collection has been set for the handler.
        """
        if self.handler_collection is not None:
            return self.handler_collection
        else:
            raise NotImplementedError(
                "get_collection or set_collection must be implemented"
            )

    def hide_comment(self, var_id: str, comment_id: str) -> Any:
        """
        Hide a comment for a variant, translocation, or CNV.

        This method updates the `comments` array of a document in the collection
        to mark a specific comment as hidden. It also records the user who hid
        the comment and the timestamp of the action.

        Args:
            var_id (str): The unique identifier of the variant or document.
            comment_id (str): The unique identifier of the comment to hide.

        Returns:
            Any: The result of the update operation.
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

    def unhide_comment(self, var_id: str, comment_id: str) -> Any:
        """
        Unhide a comment for a variant, translocation, or CNV.

        This method updates the `comments` array of a document in the collection
        to mark a specific comment as visible again.

        Args:
            var_id (str): The unique identifier of the variant or document.
            comment_id (str): The unique identifier of the comment to unhide.

        Returns:
            Any: The result of the update operation.
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

    def mark_false_positive(self, var_id: str, fp: bool) -> Any:
        """
        Mark / Unmark a variant as false positive.

        This method updates the `fp` field of a document in the collection to indicate
        whether the variant is a false positive.

        Args:
            var_id (str): The unique identifier of the variant or document.
            fp (bool): A boolean value indicating whether to mark the variant as false positive.

        Returns:
            Any: The result of the update operation.
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"fp": fp}},
        ):
            flash(
                f"Variant {'marked' if fp else 'unmarked'} as False Positive",
                "green",
            )
        else:
            flash(
                f"Failed to {'mark' if fp else 'unmark'} variant as False Positive",
                "red",
            )

    def mark_interesting(self, var_id: str, interesting: bool) -> Any:
        """
        Mark a variant as interesting.

        This method updates the `interesting` field of a document in the collection
        to indicate whether the variant is considered interesting.

        Args:
            var_id (str): The unique identifier of the variant or document.
            interesting (bool): A boolean value indicating whether to mark the variant as interesting.

        Returns:
            Any: The result of the update operation.
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"interesting": interesting}},
        ):
            flash(
                f"Variant {'marked' if interesting else 'unmarked'} as Interesting",
                "green",
            )
        else:
            flash(
                f"Failed to {'mark' if interesting else 'unmark'} variant as Interesting",
                "red",
            )

    def mark_irrelevant(self, var_id: str, irrelevant: bool) -> Any:
        """
        Mark / Unmark a variant as irrelevant.

        This method updates the `irrelevant` field of a document in the collection
        to indicate whether the variant is considered irrelevant.

        Args:
            var_id (str): The unique identifier of the variant or document.
            irrelevant (bool): A boolean value indicating whether to mark the variant as irrelevant.

        Returns:
            Any: The result of the update operation.
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"irrelevant": irrelevant}},
        ):
            flash(
                f"Variant {'marked' if irrelevant else 'unmarked'} as Irrelevant",
                "green",
            )
        else:
            flash(
                f"Failed to {'mark' if irrelevant else 'unmark'} variant as Irrelevant",
                "red",
            )

    def mark_noteworthy(self, var_id: str, noteworthy: bool) -> Any:
        """
        Mark / Unmark a variant as noteworthy.

        This method updates the `noteworthy` field of a document in the collection
        to indicate whether the variant is considered noteworthy. A noteworthy variant
        is interesting but may not be used for reporting; it can be referenced for
        future purposes.

        Args:
            var_id (str): The unique identifier of the variant or document.
            noteworthy (bool): A boolean value indicating whether to mark the variant as noteworthy.

        Returns:
            Any: The result of the update operation.
        """
        if self.get_collection().update_one(
            {"_id": ObjectId(var_id)},
            {"$set": {"noteworthy": noteworthy}},
        ):
            flash(
                f"Variant {'marked' if noteworthy else 'unmarked'} as Note Worthy",
                "green",
            )
        else:
            flash(
                f"Failed to {'mark' if noteworthy else 'unmark'} variant as Note Worthy",
                "red",
            )

    def add_comment(self, comment_doc: dict) -> Any:
        """
        Add a comment to a variant.

        This method inserts a comment document into the collection associated
        with the handler. The comment document should include all necessary
        fields such as the comment text, author, and timestamp.

        Args:
            comment_doc (dict): A dictionary containing the comment details to
                                be added to the collection.

        Returns:
            Any: The result of the insert operation.
        """
        self.get_collection().insert_one(comment_doc)

    def update_comment(self, id: str, comment_doc: dict) -> Any:
        """
        Update a comment for a variant.

        This method updates an existing comment in the collection associated with the handler.
        The comment is identified by its unique `_id`, and the provided `comment_doc` contains
        the updated details.

        Args:
            id (str): The unique identifier of the comment to update.
            comment_doc (dict): A dictionary containing the updated comment details.

        Returns:
            Any: The result of the update operation.
        """
        self.get_collection().update({"_id": ObjectId(id)}, comment_doc)

    def hidden_comments(self, id: str) -> bool:
        """
        Retrieve hidden comments for a document.

        This method checks the `comments` array of a document in the collection to determine
        if any comments are marked as hidden.

        Args:
            id (str): The unique identifier of the document to check.

        Returns:
            bool: `True` if there are hidden comments, `False` otherwise.
        """
        data = (
            self.get_collection()
            .find_one({"_id": ObjectId(id)})
            .get("comments")
        )
        if data:
            return any(comment.get("hidden") for comment in data)
        return False

    def toggle_active(self, doc_id: str, active: bool) -> Any:
        """
        Toggle the active status of a document.

        This method updates the `active` field of a document in the collection
        to indicate whether it is currently active or not.

        Args:
            doc_id (str): The unique identifier of the document to update.
            active (bool): A boolean value indicating whether to set the document as active.

        Returns:
            Any: The result of the update operation.
        """
        return self.get_collection().update_one(
            {"_id": doc_id}, {"$set": {"active": active}}
        )
