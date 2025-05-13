# -*- coding: utf-8 -*-
"""
Coyote3 Shared Module
=====================================

This module provides shared variables and objects that are used across
the application, such as the `mongo` instance for MongoDB access,
authentication managers, and utility functions.

It serves as a central point for initializing and managing these
shared resources.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from flask_login import LoginManager
from flask_pymongo import PyMongo
from coyote.db.mongo import MongoAdapter
from coyote.services.auth.ldap import LdapManager
from coyote.util import Utility


# -------------------------------------------------------------------------
# Shared Variables and Objects
# -------------------------------------------------------------------------
login_manager = LoginManager()
mongo = PyMongo()
store = MongoAdapter()
ldap_manager = LdapManager()
util = Utility()
