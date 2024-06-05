import pymongo
from bson.objectid import ObjectId
from flask import current_app as app


class ExpressionHandler:
    """
    Expression Data handler from coyote["hpaexpr"]
    """

    def get_expression_data(self, transcripts):
        expression = self.expression_collection.find({"tid": {"$in": transcripts}})

        expression_dict = {}
        for transcript_expression in expression:
            expression_dict[transcript_expression["tid"]] = transcript_expression["expr"]

        return expression_dict
