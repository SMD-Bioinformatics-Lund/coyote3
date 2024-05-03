import pymongo


class UsersHandler:
    """
    Users handler from coyote["users"]
    """

    coyote_users_collection: pymongo.collection.Collection

    def get_user_cccp_groups(self, user: str) -> list:
        result = self.coyote_users_collection.find_one( {"_id": user} )       
        if not result:
            return []
        cccp_groups = result.get("cccp_groups", [])
        return cccp_groups
    
    def update_cccp_groups(self, user: str, groups: list) -> None:
        self.coyote_users_collection.update( {"_id": user}, { '$set': { 'cccp_groups': groups }} )


