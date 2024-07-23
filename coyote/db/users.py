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

    def user_with_id(self, user_id: str) -> dict:
        """
        for an authorized user return user dict, requires autorized user to have email in db
        """
        return dict(self.get_collection().find_one({"_id": user_id}))

    def update_user_fullname(self, user_id, fullname) -> None:
        """
        Update the user fullname
        """
        self.get_collection().update_one({"_id": user_id}, {"$set": {"fullname": fullname}})

    def update_user_groups(self, user_id, groups) -> None:
        """
        Update the user groups
        """
        self.get_collection().update_one({"_id": user_id}, {"$set": {"groups": groups}})

    def update_password(self, username, password_hash) -> None:
        """
        Update the password for a user
        """

        self.get_collection().update_one({"_id": username}, {"$set": {"password": password_hash}})

    def user_exists(self, user_id=None, email=None) -> bool:
        """
        Check if a user exists
        """
        if not user_id and not email:
            return False

        if email:
            return self.get_collection().find_one({"email": email}) is not None

        if user_id:
            return self.get_collection().find_one({"_id": user_id}) is not None

    def create_user(self, user_data: dict) -> None:
        """
        Create a new user
        """
        self.get_collection().insert_one(user_data)

    def get_all_users(self) -> list:
        """
        Get all users
        """
        return list(self.get_collection().find().sort([("fullname", pymongo.ASCENDING)]))

    def delete_user(self, user_id) -> None:
        """
        Delete a user
        """
        self.get_collection().delete_one({"_id": user_id})

    def update_user(self, user_data) -> None:
        """
        Update a user
        """
        id = user_data.pop("_id")
        user_data.pop("password")
        self.get_collection().update_one({"_id": id}, {"$set": user_data})
