# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime configuration classes for the Coyote4 API.

This module owns environment-derived process settings only. Deployer-editable
center content is loaded from the host-selected profile; product metadata lives in
``coyote_api.config.factory_defaults``. Domain policy defaults are imported from the core package.
"""

import os
from typing import Any

from coyote.config.factory_defaults import factory_value
from coyote.config.knowledgebase_sources import PUBLIC_KNOWLEDGEBASE_API_URLS
from coyote.config.loaders.filter_flags import load_filter_flag_metadata
from coyote_mongo.config.collections import COLLECTIONS_CONFIG_PATH, load_collection_mapping

from coyote_api.config.application_metadata import CODEBASE_LINKS
from coyote_api.config.contact import load_contact_config, normalize_url_prefix
from coyote_api.config.factory_defaults import api_default
from coyote_api.config.paths import (
    CONTACT_CONFIG_PATH as DEFAULT_CONTACT_CONFIG_PATH,
)
from coyote_api.config.paths import REPORTS_BASE_PATH
from coyote_api.version import environment_version

# The host bootstrap selects environment inputs and center configuration first.
load_filter_flag_metadata()


def _require_env(key: str, context: str = "production") -> str:
    """Raise RuntimeError if the environment variable is not set or empty."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"{key} must be set in {context} environments. Add it to your env file and re-deploy."
        )
    return value


DEFAULT_ORGANIZATION_NAME = os.getenv(
    "ORGANIZATION_NAME", api_default("product.name")
).strip() or api_default("product.name")


def _environment_bool(key: str, default: bool | None = None) -> bool:
    """Read a boolean deployment setting once and normalize it consistently."""
    value = os.getenv(key)
    if value is None:
        return bool(api_default(f"runtime.{key}")) if default is None else default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class RepositoryMetadataSettings:
    """Repository-owned links and files exposed by the application."""

    CODEBASE = CODEBASE_LINKS["repository_url"]
    README_URL = f"{CODEBASE}/blob/master/README.md"
    LICENSE_FILE = api_default("runtime.LICENSE_FILE")
    LICENSE_URL = CODEBASE_LINKS["license_url"]
    CODE_OF_CONDUCT_URL = f"{CODEBASE}/blob/master/CODE_OF_CONDUCT.md"
    SECURITY_URL = f"{CODEBASE}/blob/master/SECURITY.md"
    CONTRIBUTING_URL = f"{CODEBASE}/blob/master/CONTRIBUTING.md"


class CacheSettings:
    """Redis runtime settings."""

    CACHE_DEFAULT_TIMEOUT = api_default("runtime.CACHE_DEFAULT_TIMEOUT")
    CACHE_KEY_PREFIX = api_default("runtime.CACHE_KEY_PREFIX")
    CACHE_TYPE = api_default("runtime.CACHE_TYPE")
    CACHE_REQUIRED = _environment_bool("CACHE_REQUIRED", api_default("runtime.CACHE_REQUIRED"))
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "")
    CACHE_REDIS_CONNECT_TIMEOUT = float(
        os.getenv(
            "CACHE_REDIS_CONNECT_TIMEOUT",
            api_default("runtime.CACHE_REDIS_CONNECT_TIMEOUT"),
        )
    )
    CACHE_REDIS_SOCKET_TIMEOUT = float(
        os.getenv(
            "CACHE_REDIS_SOCKET_TIMEOUT",
            api_default("runtime.CACHE_REDIS_SOCKET_TIMEOUT"),
        )
    )


class DashboardMetricSettings:
    """Independent dashboard metric cache settings."""

    DASHBOARD_METRIC_CACHE_TTL_SECONDS = int(
        os.getenv(
            "DASHBOARD_METRIC_CACHE_TTL_SECONDS",
            api_default("runtime.DASHBOARD_METRIC_CACHE_TTL_SECONDS"),
        )
    )
    DASHBOARD_METRIC_CACHE_RETENTION_SECONDS = int(
        os.getenv(
            "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS",
            api_default("runtime.DASHBOARD_METRIC_CACHE_RETENTION_SECONDS"),
        )
    )


class HttpSecuritySettings:
    """HTTP routing, browser-session, and security settings."""

    SCRIPT_NAME = normalize_url_prefix(os.getenv("SCRIPT_NAME", ""))
    INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
    API_SESSION_COOKIE_NAME = os.getenv(
        "API_SESSION_COOKIE_NAME", api_default("runtime.API_SESSION_COOKIE_NAME")
    )
    API_SESSION_TTL_SECONDS = int(
        os.getenv("API_SESSION_TTL_SECONDS", api_default("runtime.API_SESSION_TTL_SECONDS"))
    )
    API_SESSION_COOKIE_SAMESITE = os.getenv(
        "API_SESSION_COOKIE_SAMESITE", api_default("runtime.API_SESSION_COOKIE_SAMESITE")
    )


class OperationsSettings:
    """Audit, logging, notification, and request-rate settings."""

    AUDIT_RETENTION_DAYS = int(
        os.getenv(
            "AUDIT_RETENTION_DAYS",
            str(factory_value("controls.RetentionControlDoc.audit_events_days")),
        )
    )
    AUDIT_CHECKPOINT_DIRECTORY = os.getenv("AUDIT_CHECKPOINT_DIRECTORY", "")
    LOG_SERVICE_NAME = os.getenv("LOG_SERVICE_NAME", api_default("runtime.LOG_SERVICE_NAME"))
    LOG_ROOT = os.getenv("LOG_ROOT", api_default("runtime.LOG_ROOT"))
    LOG_TIMEZONE = os.getenv("LOCAL_TIME_ZONE", api_default("runtime.LOCAL_TIME_ZONE"))
    ERROR_EMAIL_GROUP = os.getenv("ERROR_EMAIL_GROUP", api_default("runtime.ERROR_EMAIL_GROUP"))
    LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", api_default("runtime.LOG_FILE_ENABLED")) == "1"
    LOG_RETENTION_DAYS = int(
        os.getenv(
            "LOG_RETENTION_DAYS", str(factory_value("controls.RetentionControlDoc.disk_log_days"))
        )
    )
    LOG_GZIP_AFTER_DAYS = int(
        os.getenv(
            "LOG_GZIP_AFTER_DAYS",
            str(factory_value("controls.RetentionControlDoc.gzip_disk_logs_after_days")),
        )
    )
    LOG_LEVEL = os.getenv("LOG_LEVEL") or (
        api_default("runtime.LOG_LEVEL")
        if (os.getenv("ENV_NAME") or factory_value("capabilities.environment.default"))
        .strip()
        .lower()
        in {"prod", "production"}
        else api_default("runtime.LOG_LEVEL_NON_PRODUCTION")
    )
    CELERY_LOG_LEVEL = os.getenv("CELERY_LOG_LEVEL") or LOG_LEVEL
    NOTIFICATION_RETENTION_DAYS = int(
        os.getenv(
            "NOTIFICATION_RETENTION_DAYS",
            str(factory_value("controls.RetentionControlDoc.notification_days")),
        )
    )
    API_RATE_LIMIT_ENABLED = (
        os.getenv("API_RATE_LIMIT_ENABLED", api_default("runtime.API_RATE_LIMIT_ENABLED")) == "1"
    )
    API_CSRF_ENABLED = _environment_bool(
        "API_CSRF_ENABLED", api_default("runtime.API_CSRF_ENABLED")
    )
    API_RATE_LIMIT_REQUESTS_PER_MINUTE = int(
        os.getenv(
            "API_RATE_LIMIT_REQUESTS_PER_MINUTE",
            api_default("runtime.API_RATE_LIMIT_REQUESTS_PER_MINUTE"),
        )
    )
    API_RATE_LIMIT_WINDOW_SECONDS = int(
        os.getenv(
            "API_RATE_LIMIT_WINDOW_SECONDS",
            api_default("runtime.API_RATE_LIMIT_WINDOW_SECONDS"),
        )
    )
    PASSWORD_TOKEN_SALT = os.getenv("PASSWORD_TOKEN_SALT", "")
    PASSWORD_TOKEN_TTL_SECONDS = int(
        os.getenv(
            "PASSWORD_TOKEN_TTL_SECONDS",
            api_default("runtime.PASSWORD_TOKEN_TTL_SECONDS"),
        )
    )


class KnowledgebaseSettings:
    """Public knowledgebase integration settings."""

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
    ONCOKB_BASE_URL = PUBLIC_KNOWLEDGEBASE_API_URLS["oncokb"]
    ONCOKB_PUBLIC_LOOKUPS_ENABLED = (
        os.getenv(
            "ONCOKB_PUBLIC_LOOKUPS_ENABLED",
            api_default("runtime.ONCOKB_PUBLIC_LOOKUPS_ENABLED"),
        )
        == "1"
    )
    ONCOKB_REQUEST_TIMEOUT_SECONDS = float(
        os.getenv(
            "ONCOKB_REQUEST_TIMEOUT_SECONDS",
            api_default("http_clients.request_timeout_seconds"),
        )
    )
    CLINPGX_BASE_URL = PUBLIC_KNOWLEDGEBASE_API_URLS["clinpgx"]
    CLINPGX_PUBLIC_LOOKUPS_ENABLED = (
        os.getenv(
            "CLINPGX_PUBLIC_LOOKUPS_ENABLED",
            api_default("runtime.CLINPGX_PUBLIC_LOOKUPS_ENABLED"),
        )
        == "1"
    )
    CLINPGX_REQUEST_TIMEOUT_SECONDS = float(
        os.getenv(
            "CLINPGX_REQUEST_TIMEOUT_SECONDS",
            api_default("http_clients.request_timeout_seconds"),
        )
    )


class MailSettings:
    """SMTP delivery settings for account and password workflows."""

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", api_default("runtime.SMTP_PORT")))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", api_default("runtime.SMTP_USE_TLS")) == "1"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", api_default("runtime.SMTP_USE_SSL")) == "1"
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", api_default("runtime.SMTP_FROM_EMAIL"))
    SMTP_INFO_FROM_EMAIL = os.getenv(
        "SMTP_INFO_FROM_EMAIL", api_default("runtime.SMTP_INFO_FROM_EMAIL")
    )
    SMTP_SECURITY_FROM_EMAIL = os.getenv(
        "SMTP_SECURITY_FROM_EMAIL", api_default("runtime.SMTP_SECURITY_FROM_EMAIL")
    )
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", DEFAULT_ORGANIZATION_NAME)


class PersistenceSettings:
    """MongoDB connection and configured collection-mapping settings."""

    COYOTE4_MONGO_URI = os.getenv("COYOTE4_MONGO_URI", "").strip()
    IDENTITY_MONGO_URI = os.getenv("IDENTITY_MONGO_URI", "").strip()
    KNOWLEDGEBASE_MONGO_URI = os.getenv("KNOWLEDGEBASE_MONGO_URI", "").strip()
    BAM_MONGO_URI = os.getenv("BAM_MONGO_URI", "").strip()
    COYOTE4_DB = os.getenv("COYOTE4_DB", "").strip()
    IDENTITY_DB = os.getenv("IDENTITY_DB", "").strip()
    KNOWLEDGEBASE_DB = os.getenv(
        "KNOWLEDGEBASE_DB", api_default("runtime.KNOWLEDGEBASE_DB")
    ).strip()
    BAM_DB = os.getenv("BAM_DB", "").strip()
    MONGO_MAX_POOL_SIZE = int(
        os.getenv("MONGO_MAX_POOL_SIZE", api_default("runtime.MONGO_MAX_POOL_SIZE"))
    )
    MONGO_MIN_POOL_SIZE = int(
        os.getenv("MONGO_MIN_POOL_SIZE", api_default("runtime.MONGO_MIN_POOL_SIZE"))
    )
    MONGO_CONNECT_TIMEOUT_MS = int(
        os.getenv("MONGO_CONNECT_TIMEOUT_MS", api_default("runtime.MONGO_CONNECT_TIMEOUT_MS"))
    )
    MONGO_SERVER_SELECTION_TIMEOUT_MS = int(
        os.getenv(
            "MONGO_SERVER_SELECTION_TIMEOUT_MS",
            api_default("runtime.MONGO_SERVER_SELECTION_TIMEOUT_MS"),
        )
    )
    MONGO_WAIT_QUEUE_TIMEOUT_MS = int(
        os.getenv(
            "MONGO_WAIT_QUEUE_TIMEOUT_MS",
            api_default("runtime.MONGO_WAIT_QUEUE_TIMEOUT_MS"),
        )
    )
    MONGO_READ_CONCERN_LEVEL = os.getenv(
        "MONGO_READ_CONCERN_LEVEL", api_default("runtime.MONGO_READ_CONCERN_LEVEL")
    )
    MONGO_WRITE_CONCERN_W = os.getenv(
        "MONGO_WRITE_CONCERN_W", api_default("runtime.MONGO_WRITE_CONCERN_W")
    )
    MONGO_WRITE_CONCERN_JOURNAL = _environment_bool(
        "MONGO_WRITE_CONCERN_JOURNAL", api_default("runtime.MONGO_WRITE_CONCERN_JOURNAL")
    )
    _PATH_DB_COLLECTIONS_CONFIG = COLLECTIONS_CONFIG_PATH

    @property
    def DB_COLLECTIONS_CONFIG(self) -> dict[str, Any]:
        """Return mappings for the application, identity, knowledgebase, and BAM databases."""
        return load_collection_mapping(config_path=self._PATH_DB_COLLECTIONS_CONFIG)


class DirectoryAndReportSettings:
    """Directory authentication, optional local integrations, and report paths."""

    LDAP_HOST = os.getenv("LDAP_HOST", "")
    LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")
    LDAP_USER_LOGIN_ATTR = os.getenv(
        "LDAP_USER_LOGIN_ATTR", api_default("runtime.LDAP_USER_LOGIN_ATTR")
    )
    LDAP_USE_SSL = _environment_bool("LDAP_USE_SSL", api_default("runtime.LDAP_USE_SSL"))
    LDAP_USE_TLS = _environment_bool("LDAP_USE_TLS", api_default("runtime.LDAP_USE_TLS"))
    LDAP_VERIFY_CERT = _environment_bool(
        "LDAP_VERIFY_CERT", api_default("runtime.LDAP_VERIFY_CERT")
    )
    LDAP_PORT = int(os.getenv("LDAP_PORT") or "0") or None
    LDAP_CONNECT_TIMEOUT = int(
        os.getenv("LDAP_CONNECT_TIMEOUT", api_default("runtime.LDAP_CONNECT_TIMEOUT"))
    )
    LDAP_CA_CERTS_FILE = os.getenv("LDAP_CA_CERTS_FILE", "")
    LDAP_BINDDN = os.getenv("LDAP_BINDDN", "")
    LDAP_SECRET = os.getenv("LDAP_SECRET", "")

    GENS_URI = os.getenv("GENS_URI", "")
    IGV_URI = os.getenv("IGV_URI", "")
    REPORTS_BASE_PATH = str(REPORTS_BASE_PATH)


class CelerySettings:
    """Celery process settings shared by API, worker, and beat processes."""

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")
    CELERY_DEFAULT_QUEUE = api_default("runtime.CELERY_DEFAULT_QUEUE")
    CELERY_INGEST_QUEUE = api_default("runtime.CELERY_INGEST_QUEUE")
    CELERY_TASK_TIME_LIMIT = int(
        os.getenv("CELERY_TASK_TIME_LIMIT", api_default("runtime.CELERY_TASK_TIME_LIMIT"))
    )
    CELERY_TASK_SOFT_TIME_LIMIT = int(
        os.getenv(
            "CELERY_TASK_SOFT_TIME_LIMIT",
            api_default("runtime.CELERY_TASK_SOFT_TIME_LIMIT"),
        )
    )
    CELERY_RESULT_EXPIRES = int(
        os.getenv("CELERY_RESULT_EXPIRES", api_default("runtime.CELERY_RESULT_EXPIRES"))
    )
    CELERY_WORKER_PREFETCH_MULTIPLIER = int(
        os.getenv(
            "CELERY_WORKER_PREFETCH_MULTIPLIER",
            api_default("runtime.CELERY_WORKER_PREFETCH_MULTIPLIER"),
        )
    )
    CELERY_INSPECTION_TIMEOUT_SECONDS = float(
        os.getenv(
            "CELERY_INSPECTION_TIMEOUT_SECONDS",
            api_default("runtime.CELERY_INSPECTION_TIMEOUT_SECONDS"),
        )
    )
    COYOTE4_MAINTENANCE_HOUR = int(
        os.getenv("COYOTE4_MAINTENANCE_HOUR", api_default("runtime.COYOTE4_MAINTENANCE_HOUR"))
    )


class IngestSettings:
    """Ingest workspace and watched-manifest settings shared by API and workers."""

    INGEST_COLLECTION_UPLOAD_MAX_BYTES = int(
        os.getenv(
            "INGEST_COLLECTION_UPLOAD_MAX_BYTES",
            api_default("runtime.INGEST_COLLECTION_UPLOAD_MAX_BYTES"),
        )
    )

    COYOTE4_INGEST_WATCH_ENABLED = _environment_bool("COYOTE4_INGEST_WATCH_ENABLED")
    COYOTE4_INGEST_WATCH_FILENAME = os.getenv(
        "COYOTE4_INGEST_WATCH_FILENAME",
        api_default("runtime.COYOTE4_INGEST_WATCH_FILENAME"),
    )
    COYOTE4_INGEST_DONE_SUFFIX = os.getenv(
        "COYOTE4_INGEST_DONE_SUFFIX", api_default("runtime.COYOTE4_INGEST_DONE_SUFFIX")
    )
    COYOTE4_INGEST_FAILED_SUFFIX = os.getenv(
        "COYOTE4_INGEST_FAILED_SUFFIX",
        api_default("runtime.COYOTE4_INGEST_FAILED_SUFFIX"),
    )
    COYOTE4_INGEST_WATCH_INTERVAL_SECONDS = int(
        os.getenv(
            "COYOTE4_INGEST_WATCH_INTERVAL_SECONDS",
            api_default("runtime.COYOTE4_INGEST_WATCH_INTERVAL_SECONDS"),
        )
    )
    COYOTE4_INGEST_WATCH_UPDATE_EXISTING = _environment_bool("COYOTE4_INGEST_WATCH_UPDATE_EXISTING")
    COYOTE4_INGEST_WATCH_INCREMENT = _environment_bool("COYOTE4_INGEST_WATCH_INCREMENT")
    COYOTE4_INGEST_WATCH_LOCK_PATH = os.getenv(
        "COYOTE4_INGEST_WATCH_LOCK_PATH",
        api_default("runtime.COYOTE4_INGEST_WATCH_LOCK_PATH"),
    )


class SearchLimitSettings:
    """Bounded result limits for interactive search workflows."""

    TIERED_VARIANT_SEARCH_LIMIT = api_default("runtime.TIERED_VARIANT_SEARCH_LIMIT")
    SAMPLE_SEARCH_LIMIT = api_default("runtime.SAMPLE_SEARCH_LIMIT")


class DefaultConfig(
    RepositoryMetadataSettings,
    CacheSettings,
    DashboardMetricSettings,
    HttpSecuritySettings,
    OperationsSettings,
    KnowledgebaseSettings,
    MailSettings,
    PersistenceSettings,
    DirectoryAndReportSettings,
    CelerySettings,
    IngestSettings,
    SearchLimitSettings,
):
    """Compose the application defaults from focused settings groups."""

    APP_VERSION = environment_version(
        os.getenv("ENV_NAME", str(factory_value("capabilities.environment.default")))
    )
    ORGANIZATION_NAME = DEFAULT_ORGANIZATION_NAME
    LOGS = api_default("runtime.LOG_ROOT")
    PRODUCTION = api_default("modes.non_production.PRODUCTION")
    WTF_CSRF_ENABLED = api_default("runtime.WTF_CSRF_ENABLED")
    CONTACT_CONFIG_PATH = str(DEFAULT_CONTACT_CONFIG_PATH)

    # Center public contact metadata combines deployment identity with the
    # center-owned TOML file and repository-owned application links.
    CONTACT: dict[str, Any] = load_contact_config(
        CONTACT_CONFIG_PATH,
        organization_name=ORGANIZATION_NAME,
        public_base_url=KnowledgebaseSettings.PUBLIC_BASE_URL,
        script_name=HttpSecuritySettings.SCRIPT_NAME,
    )

    @classmethod
    def validate_required_env(cls) -> None:
        """Hook for environment-specific required-variable validation."""
        return None


class ProductionConfig(DefaultConfig):
    """Production runtime settings with required-secret validation at startup."""

    LOGS = api_default("profiles.ProductionConfig.LOGS")
    PRODUCTION = api_default("modes.production.PRODUCTION")
    ENV_NAME = os.getenv("ENV_NAME", api_default("profiles.ProductionConfig.ENV_NAME"))
    APP_VERSION: str = environment_version("production")
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    INTERNAL_API_TOKEN: str = os.getenv("INTERNAL_API_TOKEN", "")
    PASSWORD_TOKEN_SALT: str = os.getenv("PASSWORD_TOKEN_SALT", "")
    DEBUG: bool = api_default("modes.production.DEBUG")

    @classmethod
    def validate_required_env(cls) -> None:
        """Require critical secrets for production startup."""
        _require_env("SECRET_KEY", "production")
        _require_env("INTERNAL_API_TOKEN", "production")
        _require_env("PASSWORD_TOKEN_SALT", "production")


class DevelopmentConfig(DefaultConfig):
    """Development database defaults, debug mode and branch-aware version label."""

    COYOTE4_DB = os.getenv(
        "COYOTE4_DB", api_default("profiles.DevelopmentConfig.COYOTE4_DB")
    ).strip()
    IDENTITY_DB = os.getenv(
        "IDENTITY_DB", api_default("profiles.DevelopmentConfig.IDENTITY_DB")
    ).strip()
    KNOWLEDGEBASE_DB = os.getenv(
        "KNOWLEDGEBASE_DB", api_default("runtime.KNOWLEDGEBASE_DB")
    ).strip()
    BAM_DB = os.getenv("BAM_DB", api_default("profiles.DevelopmentConfig.BAM_DB")).strip()

    CACHE_DEFAULT_TIMEOUT = api_default("profiles.DevelopmentConfig.CACHE_DEFAULT_TIMEOUT")

    LOGS = api_default("profiles.DevelopmentConfig.LOGS")
    PRODUCTION = api_default("modes.non_production.PRODUCTION")
    ENV_NAME = os.getenv("ENV_NAME", api_default("profiles.DevelopmentConfig.ENV_NAME"))
    SECRET_KEY = os.getenv("SECRET_KEY")
    APP_VERSION: str = environment_version("development")
    DEBUG: bool = api_default("modes.non_production.DEBUG")


class TestConfig(DefaultConfig):
    """Test database defaults and runtime flags for isolated test execution."""

    COYOTE4_DB = os.getenv("COYOTE4_DB", api_default("profiles.TestConfig.COYOTE4_DB")).strip()
    IDENTITY_DB = os.getenv("IDENTITY_DB", api_default("profiles.TestConfig.IDENTITY_DB")).strip()
    KNOWLEDGEBASE_DB = os.getenv(
        "KNOWLEDGEBASE_DB", api_default("runtime.KNOWLEDGEBASE_DB")
    ).strip()
    BAM_DB = os.getenv("BAM_DB", api_default("profiles.TestConfig.BAM_DB")).strip()

    LOGS = api_default("profiles.TestConfig.LOGS")
    PRODUCTION = api_default("modes.non_production.PRODUCTION")
    ENV_NAME = os.getenv("ENV_NAME", api_default("profiles.TestConfig.ENV_NAME"))
    SECRET_KEY = os.getenv("SECRET_KEY")

    APP_VERSION: str = environment_version("testing")

    TESTING = api_default("profiles.TestConfig.TESTING")
    LOGIN_DISABLED = api_default("profiles.TestConfig.LOGIN_DISABLED")
    DEBUG: bool = api_default("modes.non_production.DEBUG")

    # Tests do not need Redis; permit the explicit no-op fallback.
    CACHE_REDIS_URL = ""
    CACHE_REQUIRED = api_default("profiles.TestConfig.CACHE_REQUIRED")
    API_RATE_LIMIT_ENABLED = api_default("profiles.TestConfig.API_RATE_LIMIT_ENABLED")
    API_CSRF_ENABLED = api_default("profiles.TestConfig.API_CSRF_ENABLED")


class StageConfig(DefaultConfig):
    """Staging configuration."""

    COYOTE4_DB = os.getenv("COYOTE4_DB", api_default("profiles.StageConfig.COYOTE4_DB")).strip()
    IDENTITY_DB = os.getenv("IDENTITY_DB", api_default("profiles.StageConfig.IDENTITY_DB")).strip()
    KNOWLEDGEBASE_DB = os.getenv(
        "KNOWLEDGEBASE_DB", api_default("runtime.KNOWLEDGEBASE_DB")
    ).strip()
    BAM_DB = os.getenv("BAM_DB", api_default("profiles.StageConfig.BAM_DB")).strip()

    LOGS = api_default("profiles.StageConfig.LOGS")
    PRODUCTION = api_default("modes.production.PRODUCTION")
    STAGING = api_default("profiles.StageConfig.STAGING")
    ENV_NAME = os.getenv("ENV_NAME", api_default("profiles.StageConfig.ENV_NAME"))
    APP_VERSION: str = environment_version("staging")
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    INTERNAL_API_TOKEN: str = os.getenv("INTERNAL_API_TOKEN", "")
    PASSWORD_TOKEN_SALT: str = os.getenv("PASSWORD_TOKEN_SALT", "")
    DEBUG: bool = api_default("modes.production.DEBUG")

    @classmethod
    def validate_required_env(cls) -> None:
        """Require critical secrets for staging startup."""
        _require_env("SECRET_KEY", "staging")
        _require_env("INTERNAL_API_TOKEN", "staging")
        _require_env("PASSWORD_TOKEN_SALT", "staging")
