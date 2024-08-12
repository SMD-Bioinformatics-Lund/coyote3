from coyote.db.base import BaseHandler
from functools import lru_cache


class GroupsHandler(BaseHandler):
    """
    Groups handler from Groups["groups"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.groups_collection)

    def get_sample_groups(self, group: str):
        """
        Get groups for a sample
        """
        group = self.get_collection().find_one({"_id": group})
        return group

    @lru_cache(maxsize=2)
    def get_total_group_count(self):
        """
        Get total group count
        """
        return self.get_collection().count_documents({})
