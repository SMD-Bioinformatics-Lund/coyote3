"""Class-based Flask app configuration."""

import os
import ssl
import toml
from typing import Literal, Any

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
    LOGS = "logs"
    PRODUCTION = False

    INTERNAL_USERS = {
        "coyote.admin@skane.se",
        "coyote.developer@skane.se",
        "coyote.tester@skane.se",
        "coyote.manager@skane.se",
        "coyote.user@skane.se",
        "coyote.intern@skane.se",
        "coyote.viewer@skane.se",
        "coyote.external@skane.se",
    }

    WTF_CSRF_ENABLED = True
    SECRET_KEY: str | None = os.getenv("FLASK_SECRET_KEY")

    SESSION_COOKIE_NAME = "coyote3.0"

    MONGO_HOST: str = os.getenv("FLASK_MONGO_HOST") or "localhost"
    MONGO_PORT: str | Literal[27017] = os.getenv("FLASK_MONGO_PORT") or 27017
    # MONGO_DB_NAME = "coyote"
    MONGO_DB_NAME = os.getenv("COYOTE_DB", "coyote_dev_3")
    BAM_SERVICE_DB_NAME = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = "config/db_collections_new.toml"

    # Gens URI
    GENS_URI = os.getenv("GENS_URI", "http://10.231.229.34/gens/")

    LDAP_HOST = "ldap://mtlucmds1.lund.skane.se"
    LDAP_BASE_DN = "dc=skane,dc=se"
    LDAP_USER_LOGIN_ATTR = "mail"
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = "cn=admin,dc=skane,dc=se"
    LDAP_SECRET = "secret"
    LDAP_USER_DN = "ou=people"

    _PATH_GROUPS_CONFIG = "config/groups.toml"
    GROUP_FILTERS: dict[str, Any] = {
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

    # Is it redundant? Have a full set from the report.toml
    TRANS: dict[str, str] = {
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

    # Report Config
    _PATH_REPORT_CONFIG = "config/report.toml"
    REPORTS_BASE_PATH = "/data/bnf/dev/ram/Pipelines/Web_Developement/coyote_blueprinted/reports"

    ASSAY_MAPPER: dict[str, list[str]] = {
        "exome": ["exome_trio"],
        "myeloid": [
            "myeloid",
            "myeloid_vep",
            "random",
            "gms_myeloid",
            "myeloid_GMSv1",
            "myeloid_GMSv1_hg38",
            "GMSHem",
            # "lymphoid_GMSv1",
        ],
        "lymphoid": ["lymphoid", "lymphoid_vep", "lymphoid_GMSv1"],
        "solid": ["solid_GMSv3"],
        "swea": ["swea_ovarial"],
        "devel": ["devel"],
        "tumwgs": ["tumwgs", "tumwgs-solid", "tumwgs-hema"],
        # "tumwgs-solid": ["tumwgs-solid"],
        # "tumwgs-hema": ["tumwgs-hema"],
        "tumor_exome": ["gisselsson", "mertens"],
        "fusion": ["fusion", "fusion_validation_nf"],
        "gmsonco": ["gmsonco", "PARP_inhib"],
        "fusionrna": ["solidRNA_GMSv5"],
    }

    # REPORT_HEADERS: dict[str, str] = {
    #     "myeloid": "Analysrapport, myeloisk genpanel (NGS)",
    #     "swea": "Analysrapport, BRCA-panel (NGS)",
    #     "lymphoid": "Analysrapport, lymfoid genpanel (NGS)",
    #     "solid": "Analysrapport, solid tumörpanel (NGS)",
    #     "gmsonco": "Analysrapport, panel inför PARP-hämmare (NGS)",
    #     "tumwgs": "Analysrapport, somatisk WGS (NGS)",
    #     "unknown": "Analysrapport, myeloisk genpanel (NGS)",
    # }

    # ANALYSIS_METHODS: dict[str, str] = {
    #     "myeloid": "NGS-/MPS-analys med panelen GMS-myeloid v1.0 (191 gener)",
    #     "swea": "SWEA BRCA-panel, endast BRCA1 och BRCA2",
    #     "lymphoid": "",
    #     "solid": "",
    #     "gmsonco": "NGS-/MPS-analys med panelen Ärftlig solid cancer v1.0",
    #     "tumwgs": "Helgenomsekvensering (WGS) med Illumina TruSeq DNA PCR-Free",
    #     "unknown": "",
    # }

    CONSEQ_TERMS_MAPPER: dict[str, list[str]] = {
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

    NCBI_CHR: dict[str, str] = {
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
    def MONGO_URI(self) -> str:
        """
        Construct a mongo uri config property
        """
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"

    @property
    def GROUP_CONFIGS(self) -> dict[str, Any]:
        return toml.load(self._PATH_GROUPS_CONFIG)

    @property
    def REPORT_CONFIG(self) -> dict[str, Any]:
        return toml.load(self._PATH_REPORT_CONFIG)

    @property
    def DB_COLLECTIONS_CONFIG(self) -> dict[str, Any]:

        db_config: dict[str, Any] = toml.load(self._PATH_DB_COLLECTIONS_CONFIG)

        if not all(db in db_config for db in [self.MONGO_DB_NAME, self.BAM_SERVICE_DB_NAME]):
            missing_dbs = [
                db for db in [self.MONGO_DB_NAME, self.BAM_SERVICE_DB_NAME] if db not in db_config
            ]
            raise ValueError(
                f"Database(s) {', '.join(missing_dbs)} not found in the database configuration. Check the config file. ({self._PATH_DB_COLLECTIONS_CONFIG})"
            )

        # Filter the config to include only the relevant databases
        custom_db_config: dict[str, Any] = {
            db_name: collections
            for db_name, collections in db_config.items()
            if db_name in [self.MONGO_DB_NAME, self.BAM_SERVICE_DB_NAME]
        }

        return custom_db_config


class ProductionConfig(DefaultConfig):
    """
    Production configuration.
    """

    LOGS = "logs/prod"
    PRODUCTION = True
    APP_VERSION: str = f"{app_version}"
    SECRET_KEY: str | None = os.getenv("FLASK_SECRET_KEY")


class DevelopmentConfig(DefaultConfig):
    """
    Development configuration.
    """

    LOGS = "logs/dev"
    PRODUCTION = False
    SECRET_KEY = "traskbatfluga"
    APP_VERSION: str = f"{app_version}-DEV (git: {CommonUtility.get_active_branch_name()})"


class TestConfig(DefaultConfig):
    """
    For future test code.
    """

    LOGS = "logs/test"
    PRODUCTION = False
    # Paths to config files for testing:
    _PATH_ASSAY_CONFIG = "tests/config/assays.conf.toml"
    _PATH_CUTOFF_CONFIG = "tests/config/cutoffs.conf.toml"
    _PATH_TABLE_CONFIG = "tests/config/tables.conf.toml"

    APP_VERSION: str = f"{app_version}-Test (git: {CommonUtility.get_active_branch_name()})"

    MONGO_HOST = "localhost"
    MONGO_PORT = 27017

    SECRET_KEY = "traskbatfluga"
    TESTING = True
    LOGIN_DISABLED = True
