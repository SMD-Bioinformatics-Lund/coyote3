import pymongo
from flask import current_app as app

class GroupsHandler:

    def get_sample_groups(self, group: str):
        group = self.groups_collection.find_one( { '_id':group } )
        return group