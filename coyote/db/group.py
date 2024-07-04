from coyote.db.base import BaseHandler


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
