from bson.objectid import ObjectId

from coyote.db.base import BaseHandler


class ReportHandler(BaseHandler):
    """
    Report handlers from coyote["reports"]

    Args:
        BaseException (_type_): _description_
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.samples_collection)

    def get_report_id(self, id: str) -> int:
        """
        get sample id

        Args:
            id (str): _description_

        Returns:
            int: _description_
        """
        return self.get_collection().find_one({"_id": ObjectId(id)})

    @staticmethod
    def report_class_description() -> list:
        """
        Static method that provides a description of different types of clinical variant significances.

        Returns:
            list: A list of strings, where each string represents the clinical significance of a variant.
        """
        description = [
            "None",
            "Variant av stark klinisk signifikans",
            "Variant av potentiell klinisk signifikans",
            "Variant av oklar klinisk signifikans",
            "Variant bedömd som benign eller sannolikt benign",
        ]

        return description
