import pymongo


class UsersHandler:
    """
    Users handler from coyote["users"]
    """

    coyote_users_collection: pymongo.collection.Collection
    
    def user(self, user_mail: str) -> dict:
        """
        for an authorized user return user dict, requires autorized user to have email in db
        """
        return dict(self.users_collection.find_one( { "email": user_mail } ))


