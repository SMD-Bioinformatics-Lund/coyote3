import pymongo
from coyote.db.base import BaseHandler


class UsersHandler(BaseHandler):
    """
    Users handler from coyote["users"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.users_collection)

    coyote_users_collection: pymongo.collection.Collection

    def user(self, user_mail: str) -> dict:
        """
        for an authorized user return user dict, requires autorized user to have email in db
        """
        return dict(self.get_collection().find_one({"email": user_mail}))
