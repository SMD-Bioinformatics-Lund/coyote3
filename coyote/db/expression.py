from coyote.db.base import BaseHandler


class ExpressionHandler(BaseHandler):
    """
    Expression Data handler from coyote["hpaexpr"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.expression_collection)

    def get_expression_data(self, transcripts: list) -> dict:
        """
        Get expression data for a list of transcripts
        """

        expression = self.get_collection().find({"tid": {"$in": transcripts}})

        expression_dict = {}
        for transcript_expression in expression:
            expression_dict[transcript_expression["tid"]] = transcript_expression["expr"]

        return expression_dict
