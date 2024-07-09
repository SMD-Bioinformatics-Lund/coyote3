"""Class-based Flask app configuration."""

import os
import ssl
import toml

from coyote.__version__ import __version__ as app_version
from coyote.util.common_utility import CommonUtility

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
    # MONGO_DB_NAME = "coyote"
    MONGO_DB_NAME = "coyote_dev"
    BAM_SERVICE_DB_NAME = "BAM_Service"

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
        "default_spanreads": 2,
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

    ASSAY_MAPPER = {
        "exome": ["exome_trio"],
        "myeloid": [
            "myeloid",
            "myeloid_vep",
            "random",
            "gms_myeloid",
            "myeloid_GMSv1",
            "myeloid_GMSv1_hg38",
            "lymphoid_GMSv1",
        ],
        "solid": ["solid_GMSv3"],
        "swea": ["swea_ovarial"],
        "devel": ["devel"],
        "tumwgs": ["tumwgs"],
        "tumor_exome": ["gisselsson", "mertens"],
        "fusion": ["fusion", "fusion_validation_nf"],
        "gmsonco": ["gmsonco", "PARP_inhib"],
        "fusionrna": ["solidRNA_GMSv5"],
    }

    CONSEQ_TERMS_MAPPER = {
        "splicing": ["splice_acceptor_variant", "splice_donor_variant", "splice_region_variant"],
        "stop_gained": ["stop_gained"],
        "frameshift": ["frameshift_variant"],
        "stop_lost": ["stop_lost"],
        "start_lost": ["start_lost"],
        "inframe_indel": ["inframe_insertion", "inframe_deletion"],
        "missense": ["missense_variant", "protein_altering_variant"],
        "synonymous": ["stop_retained_variant", "synonymous_variant"],
        "other_coding": ["coding_sequence_variant"],
        "UTR": ["5_prime_UTR_variant", "3_prime_UTR_variant"],
        "non_coding": ["non_coding_transcript_exon_variant", "non_coding_transcript_variant"],
        "intronic": ["intron_variant"],
        "intergenic": ["intergenic_variant", "downstream_gene_variant", "upstream_gene_variant"],
        "regulatory": ["regulatory_region_variant", "TF_binding_site_variant"],
        "feature_elon_trunc": ["feature_elongation", "feature_truncation"],
    }

    NCBI_CHR = {
        "1": "NC_000001",
        "2": "NC_000002",
        "3": "NC_000003",
        "4": "NC_000004",
        "5": "NC_000005",
        "6": "NC_000006",
        "7": "NC_000007",
        "8": "NC_000008",
        "9": "NC_000009",
        "10": "NC_000010",
        "11": "NC_000011",
        "12": "NC_000012",
        "13": "NC_000013",
        "14": "NC_000014",
        "15": "NC_000015",
        "16": "NC_000016",
        "17": "NC_000017",
        "18": "NC_000018",
        "19": "NC_000019",
        "20": "NC_000020",
        "21": "NC_000021",
        "22": "NC_000022",
        "X": "NC_000023",
        "Y": "NC_000024",
    }

    # UTILITY EXTERNAL SCRIPTS
    HG38_POS_SCRIPT = "/data/bnf/scripts/hg38_pos.pl"
    SANGER_EMAIL_SCRIPT = "/data/bnf/scripts/email_sanger.pl"
    SANGER_EMAIL_RECEPIENTS = "ram.nanduri@skane.se, bjorn.hallstrom@skane.se"
    SANGER_URL = "http://10.0.224.63/coyote/var/"

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
    APP_VERSION = f"{app_version}-DEV (git: {CommonUtility.get_active_branch_name()})"


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
