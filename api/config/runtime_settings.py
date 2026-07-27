"""Runtime configuration classes for the Coyote3 API.

This module owns environment-derived process settings only. Deployer-editable
center content is loaded by ``api.config.center``; repository metadata lives in
``api.config.application_metadata``.
"""

import os
from os import path
from typing import Any
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

from api.config.application_metadata import CODEBASE_LINKS
from api.config.loaders.collections import load_collection_mapping
from api.config.loaders.contact import load_contact_config, normalize_url_prefix
from api.config.paths import (
    COLLECTIONS_CONFIG_PATH,
    REPO_ROOT,
)
from api.config.paths import (
    CONTACT_CONFIG_PATH as DEFAULT_CONTACT_CONFIG_PATH,
)
from api.version import __version__ as app_version

# Load environment variables from the repo root .env file if present.
load_dotenv(path.join(REPO_ROOT, ".env"))


def _require_env(key: str, context: str = "production") -> str:
    """Raise RuntimeError if the environment variable is not set or empty."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"{key} must be set in {context} environments. Add it to your env file and re-deploy."
        )
    return value


def _active_git_branch_name() -> str:
    """Return current git branch name for debug/test version labels."""
    head_file = path.join(REPO_ROOT, ".git", "HEAD")
    if not path.exists(head_file):
        return "unknown branch"
    with open(head_file, "r", encoding="utf-8") as f:
        for line in f.read().splitlines():
            if line.startswith("ref:"):
                return line.partition("refs/heads/")[2] or "unknown branch"
    return "unknown branch"


DEFAULT_ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "Coyote3").strip() or "Coyote3"


def _environment_bool(key: str, default: bool = False) -> bool:
    """Read a boolean deployment setting once and normalize it consistently."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class RepositoryMetadataSettings:
    """Repository-owned links and files exposed by the application."""

    CODEBASE = CODEBASE_LINKS["repository_url"]
    README_URL = f"{CODEBASE}/blob/master/README.md"
    LICENSE_FILE = "LICENSE.txt"
    LICENSE_URL = CODEBASE_LINKS["license_url"]
    CODE_OF_CONDUCT_URL = f"{CODEBASE}/blob/master/CODE_OF_CONDUCT.md"
    SECURITY_URL = f"{CODEBASE}/blob/master/SECURITY.md"
    CONTRIBUTING_URL = f"{CODEBASE}/blob/master/CONTRIBUTING.md"


class CacheSettings:
    """Redis-backed cache and dashboard snapshot settings."""

    CACHE_DEFAULT_TIMEOUT = 300  # 300 secs, 5 minutes
    CACHE_KEY_PREFIX = "coyote3_cache"
    CACHE_TYPE = "RedisCache"
    CACHE_ENABLED = _environment_bool("CACHE_ENABLED", True)
    CACHE_REQUIRED = _environment_bool("CACHE_REQUIRED", False)
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "")
    CACHE_REDIS_CONNECT_TIMEOUT = float(os.getenv("CACHE_REDIS_CONNECT_TIMEOUT", "1.0"))
    CACHE_REDIS_SOCKET_TIMEOUT = float(os.getenv("CACHE_REDIS_SOCKET_TIMEOUT", "1.0"))
    DASHBOARD_SUMMARY_CACHE_TTL_SECONDS = int(
        os.getenv("DASHBOARD_SUMMARY_CACHE_TTL_SECONDS", "60")
    )
    DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS = int(
        os.getenv("DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS", "300")
    )
    DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS = int(
        os.getenv("DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS", "604800")
    )


class HttpSecuritySettings:
    """HTTP routing, browser-session, CORS, and security settings."""

    SCRIPT_NAME = normalize_url_prefix(os.getenv("SCRIPT_NAME", ""))
    INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    ]
    API_SESSION_COOKIE_NAME = os.getenv("API_SESSION_COOKIE_NAME", "coyote3_api_session")
    API_SESSION_TTL_SECONDS = int(os.getenv("API_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
    API_SESSION_SALT = os.getenv("API_SESSION_SALT", "coyote3-api-session-v1")
    API_SESSION_COOKIE_SAMESITE = os.getenv("API_SESSION_COOKIE_SAMESITE", "lax")


class OperationsSettings:
    """Audit, logging, notification, and request-rate settings."""

    AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "730"))
    LOG_SERVICE_NAME = os.getenv("LOG_SERVICE_NAME", "api")
    LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", "1") == "1"
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    LOG_GZIP_AFTER_DAYS = int(os.getenv("LOG_GZIP_AFTER_DAYS", "1"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    NOTIFICATION_RETENTION_DAYS = int(os.getenv("NOTIFICATION_RETENTION_DAYS", "180"))
    API_RATE_LIMIT_ENABLED = os.getenv("API_RATE_LIMIT_ENABLED", "1") == "1"
    API_RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_REQUESTS_PER_MINUTE", "600"))
    API_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))
    PASSWORD_TOKEN_SALT = os.getenv("PASSWORD_TOKEN_SALT", "")
    PASSWORD_TOKEN_TTL_SECONDS = int(os.getenv("PASSWORD_TOKEN_TTL_SECONDS", str(60 * 60)))
    WEB_RATE_LIMIT_ENABLED = os.getenv("WEB_RATE_LIMIT_ENABLED", "1") == "1"
    WEB_RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("WEB_RATE_LIMIT_REQUESTS_PER_MINUTE", "300"))
    WEB_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("WEB_RATE_LIMIT_WINDOW_SECONDS", "60"))


class KnowledgebaseSettings:
    """Public knowledgebase integration settings."""

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
    ONCOKB_BASE_URL = os.getenv("ONCOKB_BASE_URL", "https://public.api.oncokb.org/api/v1")
    ONCOKB_PUBLIC_LOOKUPS_ENABLED = os.getenv("ONCOKB_PUBLIC_LOOKUPS_ENABLED", "1") == "1"
    ONCOKB_REQUEST_TIMEOUT_SECONDS = float(os.getenv("ONCOKB_REQUEST_TIMEOUT_SECONDS", "3.0"))
    ONCOKB_PUBLIC_BATCH_SIZE = int(os.getenv("ONCOKB_PUBLIC_BATCH_SIZE", "200"))
    CLINPGX_BASE_URL = os.getenv("CLINPGX_BASE_URL", "https://api.clinpgx.org/v1")
    CLINPGX_PUBLIC_LOOKUPS_ENABLED = os.getenv("CLINPGX_PUBLIC_LOOKUPS_ENABLED", "1") == "1"
    CLINPGX_REQUEST_TIMEOUT_SECONDS = float(os.getenv("CLINPGX_REQUEST_TIMEOUT_SECONDS", "3.0"))


class MailSettings:
    """SMTP delivery settings for account and password workflows."""

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0") == "1"
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@coyote3.local")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", DEFAULT_ORGANIZATION_NAME)


class PersistenceSettings:
    """MongoDB connection and configured collection-mapping settings."""

    _MONGO_URI_ENV: str = os.getenv("MONGO_URI", "").strip()
    COYOTE3_DB = os.getenv("COYOTE3_DB", "coyote3")
    BAM_DB = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = COLLECTIONS_CONFIG_PATH

    @property
    def MONGO_URI(self) -> str:
        """Return the configured Mongo URI, appending the primary DB when absent."""
        if not self._MONGO_URI_ENV:
            raise ValueError("MONGO_URI must be set.")
        parsed = urlparse(self._MONGO_URI_ENV)
        if (parsed.path or "").strip("/"):
            return self._MONGO_URI_ENV
        return urlunparse(parsed._replace(path=f"/{self.COYOTE3_DB}"))

    @property
    def DB_COLLECTIONS_CONFIG(self) -> dict[str, Any]:
        """Return mappings for the configured application and BAM databases."""
        return load_collection_mapping(
            primary_database=self.COYOTE3_DB,
            bam_database=self.BAM_DB,
            config_path=self._PATH_DB_COLLECTIONS_CONFIG,
        )


class DirectoryAndReportSettings:
    """Directory authentication, optional local integrations, and report paths."""

    LDAP_HOST = os.getenv("LDAP_HOST", "")
    LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")
    LDAP_USER_LOGIN_ATTR = os.getenv("LDAP_USER_LOGIN_ATTR", "mail")
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = os.getenv("LDAP_BINDDN", "")
    LDAP_SECRET = os.getenv("LDAP_SECRET", "")
    LDAP_USER_DN = os.getenv("LDAP_USER_DN", "ou=people")

    GENS_URI = os.getenv("GENS_URI", "")
    IGV_URI = os.getenv("IGV_URI", "")
    REPORTS_BASE_PATH = os.getenv("REPORTS_BASE_PATH", "/data/coyote3/reports")


class CelerySettings:
    """Celery process settings shared by API, worker, and beat processes."""

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")
    CELERY_DEFAULT_QUEUE = os.getenv("CELERY_DEFAULT_QUEUE", "default")
    CELERY_INGEST_QUEUE = os.getenv("CELERY_INGEST_QUEUE", "ingest")
    CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "7200"))
    CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "6900"))
    CELERY_RESULT_EXPIRES = int(os.getenv("CELERY_RESULT_EXPIRES", "86400"))
    CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
    COYOTE3_MAINTENANCE_HOUR = int(os.getenv("COYOTE3_MAINTENANCE_HOUR", "2"))


class IngestSettings:
    """Ingest workspace and watched-manifest settings shared by API and workers."""

    CELERY_INGEST_STAGING_DIR = os.getenv("CELERY_INGEST_STAGING_DIR", "/tmp/coyote3_ingest_jobs")
    COYOTE3_DATA_HOST_ROOT = os.getenv("COYOTE3_DATA_HOST_ROOT", "")
    COYOTE3_INGEST_WATCH_ENABLED = _environment_bool("COYOTE3_INGEST_WATCH_ENABLED")
    COYOTE3_INGEST_WATCH_DIR = os.getenv("COYOTE3_INGEST_WATCH_DIR", "")
    COYOTE3_INGEST_WATCH_FILENAME = os.getenv("COYOTE3_INGEST_WATCH_FILENAME", "coyote3.yaml")
    COYOTE3_INGEST_DONE_SUFFIX = os.getenv("COYOTE3_INGEST_DONE_SUFFIX", ".done")
    COYOTE3_INGEST_FAILED_SUFFIX = os.getenv("COYOTE3_INGEST_FAILED_SUFFIX", ".failed")
    COYOTE3_INGEST_WATCH_INTERVAL_SECONDS = int(
        os.getenv("COYOTE3_INGEST_WATCH_INTERVAL_SECONDS", "30")
    )
    COYOTE3_INGEST_WATCH_UPDATE_EXISTING = _environment_bool("COYOTE3_INGEST_WATCH_UPDATE_EXISTING")
    COYOTE3_INGEST_WATCH_INCREMENT = _environment_bool("COYOTE3_INGEST_WATCH_INCREMENT")
    COYOTE3_INGEST_WATCH_LOCK_PATH = os.getenv(
        "COYOTE3_INGEST_WATCH_LOCK_PATH", "/tmp/coyote3_ingest_watch.lock"
    )


class SearchLimitSettings:
    """Bounded result limits for interactive search workflows."""

    TIERED_VARIANT_SEARCH_LIMIT = 1000
    SAMPLE_SEARCH_LIMIT = 1000
    REPORTED_SAMPLES_SEARCH_LIMIT = 50


class DefaultConfig(
    RepositoryMetadataSettings,
    CacheSettings,
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

    APP_VERSION = app_version
    ORGANIZATION_NAME = DEFAULT_ORGANIZATION_NAME
    LOGS = "logs"
    PRODUCTION = False
    WTF_CSRF_ENABLED = True
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
    """
    Production configuration.

    This class defines the configuration settings for the production
    environment of the Coyote3 application. It inherits from the
    `DefaultConfig` class and overrides specific attributes to suit
    the production setup.
    """

    LOGS = "logs/prod"
    PRODUCTION = True
    ENV_NAME = os.getenv("ENV_NAME", "Production")
    APP_VERSION: str = f"{app_version}"
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    INTERNAL_API_TOKEN: str = os.getenv("INTERNAL_API_TOKEN", "")
    PASSWORD_TOKEN_SALT: str = os.getenv("PASSWORD_TOKEN_SALT", "")
    CORS_ORIGINS: list[str] = DefaultConfig.CORS_ORIGINS
    DEBUG: bool = False

    @classmethod
    def validate_required_env(cls) -> None:
        """Require critical secrets for production startup."""
        _require_env("SECRET_KEY", "production")
        _require_env("INTERNAL_API_TOKEN", "production")
        _require_env("API_SESSION_SALT", "production")
        _require_env("PASSWORD_TOKEN_SALT", "production")


class DevelopmentConfig(DefaultConfig):
    """
    Development configuration.

    This class defines the configuration settings for the development
    environment of the Coyote3 application. It inherits from the
    `DefaultConfig` class and overrides specific attributes to suit
    the development setup.
    """

    COYOTE3_DB = os.getenv("COYOTE3_DB", "coyote3")
    BAM_DB = os.getenv("BAM_DB", "BAM_Service")

    CACHE_DEFAULT_TIMEOUT = 1  # 300 secs, 5 minutes

    LOGS = "logs/dev"
    PRODUCTION = False
    ENV_NAME = os.getenv("ENV_NAME", "Development")
    SECRET_KEY = os.getenv("SECRET_KEY")
    CORS_ORIGINS: list[str] = DefaultConfig.CORS_ORIGINS
    APP_VERSION: str = f"{app_version}-DEV (git: {_active_git_branch_name()})"
    DEBUG: bool = True


class TestConfig(DefaultConfig):
    """
    Placeholder for future test code.

    This docstring indicates that this section or class is reserved
    for implementing test-related configurations or functionality
    in the future.
    """

    COYOTE3_DB = os.getenv("COYOTE3_DB", "coyote3_test")
    BAM_DB = os.getenv("BAM_DB", "BAM_Service")

    LOGS = "logs/test"
    PRODUCTION = False
    ENV_NAME = os.getenv("ENV_NAME", "Testing")
    SECRET_KEY = os.getenv("SECRET_KEY")
    CORS_ORIGINS: list[str] = DefaultConfig.CORS_ORIGINS

    APP_VERSION: str = f"{app_version}-Test (git: {_active_git_branch_name()})"

    TESTING = True
    LOGIN_DISABLED = True
    DEBUG: bool = True

    # Disable Redis cache in tests — avoids 10s DNS timeout for unreachable hosts.
    CACHE_REDIS_URL = ""


class StageConfig(DefaultConfig):
    """Staging configuration."""

    COYOTE3_DB = os.getenv("COYOTE3_DB", "coyote3")
    BAM_DB = os.getenv("BAM_DB", "BAM_Service")

    LOGS = "logs/stage"
    PRODUCTION = True
    STAGING = True
    ENV_NAME = os.getenv("ENV_NAME", "Staging")
    APP_VERSION: str = f"{app_version}-STAGE"
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    INTERNAL_API_TOKEN: str = os.getenv("INTERNAL_API_TOKEN", "")
    PASSWORD_TOKEN_SALT: str = os.getenv("PASSWORD_TOKEN_SALT", "")
    CORS_ORIGINS: list[str] = DefaultConfig.CORS_ORIGINS
    DEBUG: bool = False

    @classmethod
    def validate_required_env(cls) -> None:
        """Require critical secrets for staging startup."""
        _require_env("SECRET_KEY", "staging")
        _require_env("INTERNAL_API_TOKEN", "staging")
        _require_env("API_SESSION_SALT", "staging")
        _require_env("PASSWORD_TOKEN_SALT", "staging")
