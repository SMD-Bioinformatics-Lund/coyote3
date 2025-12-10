#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Main Configuration Module for Coyote3
=====================================

This module defines the configuration classes for the Coyote3 application,
including default, production, development, and testing configurations.

It provides centralized settings for Flask, MongoDB, LDAP, and other
application-specific configurations, ensuring consistency and flexibility
across different environments.
"""


# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import os
from typing import Any, Literal
import toml
from cryptography.fernet import Fernet
from coyote.__version__ import __version__ as app_version
from coyote.util.common_utility import CommonUtility
from dotenv import load_dotenv
from os import path

# Load environment variables from a .env file if present
basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class DefaultConfig:
    """
    Default configuration class for the Coyote3 application.

    This class provides the base configuration settings for the application,
    including application version, logging paths, MongoDB settings, LDAP
    configurations, and other default values. It serves as the foundation
    for other environment-specific configurations such as production,
    development, and testing.
    """

    # GITHUB REPO
    CODEBASE = "https://github.com/SMD-Bioinformatics-Lund/coyote3"

    # Public ASSAY CATALOG
    ASSAY_CATALOG_YAML = "coyote/static/data/assay_catalog.yaml"

    APP_VERSION = app_version
    LOGS = "logs"
    PRODUCTION = False

    # REDIS CACHE TIMEOUTS
    CACHE_DEFAULT_TIMEOUT = 300  # 300 secs, 5 minutes
    CACHE_KEY_PREFIX = "coyote3_cache"
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_HOST = os.getenv("CACHE_REDIS_HOST", "localhost")
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")

    # Fernet key for encrypting sensitive data in the report
    FERNET = Fernet(os.getenv("COYOTE3_FERNET_KEY"))

    WTF_CSRF_ENABLED = True

    MONGO_HOST: str = os.getenv("FLASK_MONGO_HOST") or "localhost"
    MONGO_PORT: str | Literal[27017] = os.getenv("FLASK_MONGO_PORT") or 27017
    MONGO_DB_NAME = os.getenv("COYOTE3_DB_NAME", "coyote3")
    BAM_SERVICE_DB_NAME = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = "config/coyote3_collections.toml"

    LDAP_HOST = "ldap://mtlucmds1.lund.skane.se"
    LDAP_BASE_DN = "dc=skane,dc=se"
    LDAP_USER_LOGIN_ATTR = "mail"
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = "cn=admin,dc=skane,dc=se"
    LDAP_SECRET = "secret"
    LDAP_USER_DN = "ou=people"

    # For the public assay map
    # This is used in the public assay matrix
    PUBLIC_ASSAY_MAP: dict[str, list[str]] = {
        "ST-DNA": ["solid_GMSv3"],
        "Hematology": ["hema_GMSv1"],
        "Myeloid": ["myeloid_GMSv1"],
        "Lymphoid": ["lymph_GMSv3"],
        "PGx": ["PGxv1"],
        "PARP": ["PARP_inhib"],
        "ST-RNA": ["solidRNA_GMSv5"],
        "WTS-Fusion": ["fusion"],
        "RNA-Fusion": ["RNA-fusion"],
        "WGS": ["tumwgs-solid", "tumwgs-hema"],
    }

    # Gens URI
    GENS_URI = os.getenv("GENS_URI", "http://mtcmdpgm01.lund.skane.se/gens/")

    # Report Config
    REPORTS_BASE_PATH = os.getenv("REPORTS_BASE_PATH", "/data/coyote3/reports")

    CONSEQ_TERMS_MAPPER: dict[str, list[str]] = {
        "splicing": [
            "splice_acceptor_variant",
            "splice_donor_variant",
            "splice_region_variant",
        ],
        "stop_gained": ["stop_gained"],
        "frameshift": ["frameshift_variant"],
        "stop_lost": ["stop_lost"],
        "start_lost": ["start_lost"],
        "inframe_indel": [
            "inframe_insertion",
            "inframe_deletion",
        ],
        "missense": [
            "missense_variant",
            "protein_altering_variant",
        ],
        "other_coding": [
            "coding_sequence_variant",
        ],
        "synonymous": [
            "stop_retained_variant",
            "synonymous_variant",
            "start_retained_variant",
            "incomplete_terminal_codon_variant",
        ],
        "transcript_structure": [
            "transcript_ablation",
            "transcript_amplification",
        ],
        "UTR": [
            "5_prime_UTR_variant",
            "3_prime_UTR_variant",
        ],
        "miRNA": [
            "mature_miRNA_variant",
        ],
        "NMD": [
            "NMD_transcript_variant",
        ],
        "non_coding": [
            "non_coding_transcript_exon_variant",
            "non_coding_transcript_variant",
        ],
        "intronic": [
            "intron_variant",
        ],
        "intergenic": [
            "intergenic_variant",
            "downstream_gene_variant",
            "upstream_gene_variant",
        ],
        "regulatory": [
            "regulatory_region_variant",
            "regulatory_region_ablation",
            "regulatory_region_amplification",
            "TFBS_ablation",
            "TFBS_amplification",
            "TF_binding_site_variant",
        ],
        "feature_elon_trunc": [
            "feature_elongation",
            "feature_truncation",
        ],
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

    CONTACT: dict[str, str] = {
        "clinical_email": "ram.nanduri@skane.se",
        "research_email": "ram.nanduri@skane.se",
        "samples_email": "ram.nanduri@skane.se",
        "phone_main": "+46 ",
        "phone_urgent": "+46 ",
        "address": "Section for Molecular Diagnostics, Region Skåne\nSölvegatan 23 B, Byggnad 71 Lund, Sweden",
        "hours": ["Mon–Fri: 08:00–16:30", "Closed on public holidays"],
        # "sample_form_url": "https://…",
        # "guidelines_url": "https://…",
        # "urgent_notes": "For critical cases within lab hours only.",
    }

    @property
    def MONGO_URI(self) -> str:
        """
        Construct a MongoDB URI for connecting to the database.

        This property dynamically generates the MongoDB connection URI
        using the configured host, port, and database name.

        Returns:
            str: The MongoDB connection URI.
        """
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"

    @property
    def DB_COLLECTIONS_CONFIG(self) -> dict[str, Any]:
        """
        Load and validate the database collections configuration.

        This method reads the database collections configuration from a TOML file,
        validates that the required databases are present, and filters the configuration
        to include only the relevant databases.

        Returns:
            dict[str, Any]: A dictionary containing the filtered database collections configuration.

        Raises:
            ValueError: If any required database is missing from the configuration file.
        """
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

    This class defines the configuration settings for the production
    environment of the Coyote3 application. It inherits from the
    `DefaultConfig` class and overrides specific attributes to suit
    the production setup.
    """

    LOGS = "logs/prod"
    PRODUCTION = True
    APP_VERSION: str = f"{app_version}"
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "coyote3_prod")
    DEBUG: bool = False


class DevelopmentConfig(DefaultConfig):
    """
    Development configuration.

    This class defines the configuration settings for the development
    environment of the Coyote3 application. It inherits from the
    `DefaultConfig` class and overrides specific attributes to suit
    the development setup.
    """

    MONGO_DB_NAME = os.getenv("COYOTE3_DB_NAME", "coyote_dev_3")
    BAM_SERVICE_DB_NAME = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = "config/db_collections_beta2.toml"

    CACHE_DEFAULT_TIMEOUT = 1  # 300 secs, 5 minutes

    LOGS = "logs/dev"
    PRODUCTION = False
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "coyote3_dev")
    SECRET_KEY = os.getenv("SECRET_KEY")
    APP_VERSION: str = f"{app_version}-DEV (git: {CommonUtility.get_active_branch_name()})"
    DEBUG: bool = True


class TestConfig(DefaultConfig):
    """
    Placeholder for future test code.

    This docstring indicates that this section or class is reserved
    for implementing test-related configurations or functionality
    in the future.
    """

    MONGO_DB_NAME = os.getenv("COYOTE3_DB_NAME", "coyote3_test")
    BAM_SERVICE_DB_NAME = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = "config/db_collections_beta2.toml"

    LOGS = "logs/test"
    PRODUCTION = False
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "coyote3_test")
    SECRET_KEY = os.getenv("SECRET_KEY")

    APP_VERSION: str = f"{app_version}-Test (git: {CommonUtility.get_active_branch_name()})"

    TESTING = True
    LOGIN_DISABLED = True
    DEBUG: bool = True
