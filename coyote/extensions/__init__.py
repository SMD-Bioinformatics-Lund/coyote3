"""
This module stores variables/objects that need to be accessed all over
the app. e.g. mongo : MongoClient.
"""

from flask_login import LoginManager
from flask_pymongo import PyMongo
from coyote.db.mongo import MongoAdapter
from .ldap_extension import LdapManager
from coyote.util import Utility
from coyote.models.roles import RolesModel

login_manager = LoginManager()
mongo = PyMongo()
store = MongoAdapter()
ldap_manager = LdapManager()
util = Utility()
roles_model = RolesModel()
