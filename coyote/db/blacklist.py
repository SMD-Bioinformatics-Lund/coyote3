from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app
from coyote.util.common_utility import CommonUtility


class BlacklistHandler(BaseHandler):
    """
    Blacklist handler from coyote["blacklist"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.blacklist_collection)

    def add_blacklist_data(self, variants: list, assay: str) -> dict:
        """
        Add blacklist data to variants
        """

        short_pos = [var.get("simple_id") for var in variants]

        blacklisted = self.get_collection().find(
            {"assay": assay, "pos": {"$in": short_pos}}, {"pos": 1, "in_normal_perc": 1, "_id": 0}
        )
        blacklisted_dict = {elem["pos"]: elem["in_normal_perc"] for elem in list(blacklisted)}

        for var in variants:
            if var["simple_id"] in blacklisted_dict:
                var["blacklist"] = blacklisted_dict[var["simple_id"]]

        return variants

    def blacklist_variant(self, var: dict, assay: str) -> str:
        """
        Add a variant to the blacklist collection
        """
        short_pos = var.get("simple_id", CommonUtility.get_simple_id(var))

        if self.get_collection().insert_one(
            {"assay": assay, "in_normal_perc": 1, "pos": short_pos}
        ):
            flash(f"Variant {short_pos} added to blacklist", "green")
            return True
        else:
            flash(f"Failed to add variant {short_pos} to blacklist", "red")
            return False

    def get_unique_blacklist_count(self) -> int:
        """
        Get unique Blacklist
        """
        query = [
            {"$group": {"_id": {"pos": "$pos"}}},
            {"$group": {"_id": None, "uniqueBlacklistCount": {"$sum": 1}}},
        ]

        try:
            result = list(self.get_collection().aggregate(query))
            if result:
                return result[0].get("uniqueBlacklistCount", 0)
            else:
                return 0
        except Exception as e:
            app.logger.error(f"An error occurred: {e}")
            return 0
