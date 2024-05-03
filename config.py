"""Class-based Flask app configuration."""

import os
import ssl
import toml

from coyote.__version__ import __version__ as app_version
from coyote.util import get_active_branch_name

# # Implement in the future?
# from dotenv import load_dotenv
# basedir = path.abspath(path.dirname(__file__))
# load_dotenv(path.join(basedir, ".env"))

"""
CONFIG UTIL FUNCTIONS:
"""


class DefaultConfig:
    APP_VERSION = app_version

    WTF_CSRF_ENABLED = True
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

    SESSION_COOKIE_NAME = "coyote"

    MONGO_HOST = os.getenv("FLASK_MONGO_HOST") or "localhost"
    MONGO_PORT = os.getenv("FLASK_MONGO_PORT") or 27017
    MONGO_DB_NAME = "coyote"

    LDAP_HOST = 'ldap://mtlucmds1.lund.skane.se'
    LDAP_BASE_DN = 'dc=skane,dc=se'
    LDAP_USER_LOGIN_ATTR = 'mail'
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = 'cn=admin,dc=skane,dc=se'
    LDAP_SECRET = 'secret'
    LDAP_USER_DN = 'ou=people'
    
    @property
    def MONGO_URI(self):
        """
        Construct a mongo uri config property
        """
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"

class DevelopmentConfig(DefaultConfig):
    SECRET_KEY = "traskbatfluga"
    APP_VERSION = f"{app_version}-DEV (git: {get_active_branch_name()})"


class TestConfig(DefaultConfig):
    """
    For future test code.
    """

    # Paths to config files for testing:
    _PATH_ASSAY_CONFIG = "tests/config/assays.conf.toml"
    _PATH_CUTOFF_CONFIG = "tests/config/cutoffs.conf.toml"
    _PATH_TABLE_CONFIG = "tests/config/tables.conf.toml"

    MONGO_HOST = "localhost"
    MONGO_PORT = 27017

    SECRET_KEY = "traskbatfluga"
    TESTING = True
    LOGIN_DISABLED = True


