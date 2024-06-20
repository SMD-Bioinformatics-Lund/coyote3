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

    LDAP_HOST = "ldap://mtlucmds1.lund.skane.se"
    LDAP_BASE_DN = "dc=skane,dc=se"
    LDAP_USER_LOGIN_ATTR = "mail"
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = "cn=admin,dc=skane,dc=se"
    LDAP_SECRET = "secret"
    LDAP_USER_DN = "ou=people"

    _PATH_GROUPS_CONFIG = "config/groups.toml"
    GROUP_FILTERS = {
        "warn_cov": 500,
        "error_cov": 100,
        "default_popfreq": 1.0,
        "default_mindepth": 100,
        "default_spanreads": 0,
        "default_spanpairs": 0,
        "default_min_freq": 0.05,
        "default_min_reads": 10,
        "default_max_freq": 0.05,
        "default_min_cnv_size": 100,
        "default_max_cnv_size": 100000000,
        "default_checked_conseq": {
            "splicing": 1,
            "stop_gained": 1,
            "frameshift": 1,
            "stop_lost": 1,
            "start_lost": 1,
            "inframe_indel": 1,
            "missense": 1,
            "other_coding": 1,
        },
        "default_checked_genelists": {},
        "default_checked_fusionlists": {},
        "default_checked_fusioneffects": [],
        "default_checked_fusioncallers": [],
        "default_checked_cnveffects": [],
    }
    TRANS = {
        "nonsynonymous_SNV": "missense SNV",
        "stopgain": "stop gain",
        "frameshift_insertion": "frameshift ins",
        "frameshift_deletion": "frameshift del",
        "nonframeshift_insertion": "frameshift ins",
        "nonframeshift_deletion": "frameshift del",
        "missense_variant": "missense variant",
        "feature_truncation": "feature truncation",
        "frameshift_variant": "frameshift variant",
    }

    @property
    def MONGO_URI(self):
        """
        Construct a mongo uri config property
        """
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"

    @property
    def GROUP_CONFIGS(self):
        return toml.load(self._PATH_GROUPS_CONFIG)


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
