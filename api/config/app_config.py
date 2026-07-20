"""Runtime configuration classes for the Coyote3 API."""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import os
from os import path
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import toml
from dotenv import load_dotenv

from api.version import __version__ as app_version

API_CONFIG_DIR = Path(__file__).resolve().parent

# Load environment variables from the repo root .env file if present.
REPO_ROOT = path.abspath(path.join(path.dirname(__file__), "..", ".."))
load_dotenv(path.join(REPO_ROOT, ".env"))


def _normalize_url_prefix(value: str | None) -> str:
    """Normalize an externally mounted URL prefix such as SCRIPT_NAME."""
    raw = (value or "").strip()
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")


def _join_public_url(base_url: str, script_name: str, suffix: str = "") -> str:
    """Join public origin, mounted SCRIPT_NAME, and a browser-facing suffix."""
    base = base_url.strip().rstrip("/")
    if not base:
        return ""
    prefix = _normalize_url_prefix(script_name)
    normalized_suffix = "/" + suffix.strip("/") if suffix.strip("/") else ""
    trailing = "/" if suffix.endswith("/") else ""
    return f"{base}{prefix}{normalized_suffix}{trailing}"


def _require_env(key: str, context: str = "production") -> str:
    """Raise RuntimeError if the environment variable is not set or empty."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"{key} must be set in {context} environments. Add it to your env file and re-deploy."
        )
    return value


def _load_contact_config(
    config_path: str | Path,
    *,
    organization_name: str,
    public_base_url: str,
    script_name: str,
) -> dict[str, Any]:
    """Load center-owned public contact metadata from TOML."""
    path_obj = Path(config_path)
    if not path_obj.is_absolute():
        path_obj = (REPO_ROOT / path_obj).resolve()
    if not path_obj.exists():
        raise RuntimeError(f"CONTACT_CONFIG_PATH does not exist: {path_obj}")

    raw = toml.load(str(path_obj))
    organization = dict(raw.get("organization") or {})
    organization["name"] = organization_name

    support = dict(raw.get("support") or {})
    web_app_base_url = _join_public_url(public_base_url, script_name, "/")
    help_center_url = _join_public_url(public_base_url, script_name, "/docs-site/")
    if web_app_base_url:
        support.setdefault("web_app_base_url", web_app_base_url)
    if help_center_url:
        support.setdefault("help_center_url", help_center_url)
    return {
        "organization": organization,
        "support": support,
        "codebase": dict(raw.get("codebase") or {}),
        "contacts": list(raw.get("contacts") or []),
        "links": list(raw.get("links") or []),
        "hours": list(raw.get("hours") or []),
        "meta": {
            "source": str(path_obj),
            "format": "toml",
        },
    }


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

    # Readme
    README_URL = f"{CODEBASE}/blob/master/README.md"

    # LICENSE
    LICENSE_FILE = "LICENSE.txt"
    LICENSE_URL = f"{CODEBASE}/blob/master/LICENSE.txt"

    # CODE OF CONDUCT
    CODE_OF_CONDUCT_URL = f"{CODEBASE}/blob/master/CODE_OF_CONDUCT.md"

    # SECURITY
    SECURITY_URL = f"{CODEBASE}/blob/master/SECURITY.md"

    # CONTRIBUTING
    CONTRIBUTING_URL = f"{CODEBASE}/blob/master/CONTRIBUTING.md"

    APP_VERSION = app_version
    ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "Coyote3").strip() or "Coyote3"
    LOGS = "logs"
    PRODUCTION = False

    # REDIS CACHE TIMEOUTS
    CACHE_DEFAULT_TIMEOUT = 300  # 300 secs, 5 minutes
    CACHE_KEY_PREFIX = "coyote3_cache"
    CACHE_TYPE = "RedisCache"
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "1") == "1"
    CACHE_REQUIRED = os.getenv("CACHE_REQUIRED", "0") == "1"
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
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

    WTF_CSRF_ENABLED = True
    SCRIPT_NAME = _normalize_url_prefix(os.getenv("SCRIPT_NAME", ""))
    INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")
    # CORS configuration.
    # Set CORS_ORIGINS as a comma-separated list of allowed origins, e.g.:
    #   CORS_ORIGINS=https://coyote3.example.com,https://staging.example.com
    # If unset or empty, ALL origins are permitted by the API CORS middleware.
    # See the README Security section for production recommendations.
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    ]
    API_SESSION_COOKIE_NAME = os.getenv("API_SESSION_COOKIE_NAME", "coyote3_api_session")
    API_SESSION_TTL_SECONDS = int(os.getenv("API_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
    API_SESSION_SALT = os.getenv("API_SESSION_SALT", "coyote3-api-session-v1")
    API_SESSION_COOKIE_SAMESITE = os.getenv("API_SESSION_COOKIE_SAMESITE", "lax")
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
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
    CONTACT_CONFIG_PATH = os.getenv("CONTACT_CONFIG_PATH", str(API_CONFIG_DIR / "contact.toml"))
    ONCOKB_BASE_URL = os.getenv("ONCOKB_BASE_URL", "https://public.api.oncokb.org/api/v1")
    ONCOKB_PUBLIC_LOOKUPS_ENABLED = os.getenv("ONCOKB_PUBLIC_LOOKUPS_ENABLED", "1") == "1"
    ONCOKB_REQUEST_TIMEOUT_SECONDS = float(os.getenv("ONCOKB_REQUEST_TIMEOUT_SECONDS", "3.0"))
    ONCOKB_PUBLIC_BATCH_SIZE = int(os.getenv("ONCOKB_PUBLIC_BATCH_SIZE", "200"))
    CLINPGX_BASE_URL = os.getenv("CLINPGX_BASE_URL", "https://api.clinpgx.org/v1")
    CLINPGX_PUBLIC_LOOKUPS_ENABLED = os.getenv("CLINPGX_PUBLIC_LOOKUPS_ENABLED", "1") == "1"
    CLINPGX_REQUEST_TIMEOUT_SECONDS = float(os.getenv("CLINPGX_REQUEST_TIMEOUT_SECONDS", "3.0"))
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0") == "1"
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@coyote3.local")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", ORGANIZATION_NAME)

    _MONGO_URI_ENV: str = os.getenv("MONGO_URI", "").strip()
    COYOTE3_DB = os.getenv("COYOTE3_DB", "coyote3")
    BAM_DB = os.getenv("BAM_DB", "BAM_Service")
    _PATH_DB_COLLECTIONS_CONFIG = API_CONFIG_DIR / "coyote3_collections.toml"

    # LDAP — all values must be set via environment variables per center.
    # No SMD-specific defaults are provided here.
    LDAP_HOST = os.getenv("LDAP_HOST", "")
    LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")
    LDAP_USER_LOGIN_ATTR = os.getenv("LDAP_USER_LOGIN_ATTR", "mail")
    LDAP_USE_SSL = False
    LDAP_USE_TLS = True
    LDAP_BINDDN = os.getenv("LDAP_BINDDN", "")
    LDAP_SECRET = os.getenv("LDAP_SECRET", "")
    LDAP_USER_DN = os.getenv("LDAP_USER_DN", "ou=people")

    # Gens URI — optional integration; set per center or leave empty.
    GENS_URI = os.getenv("GENS_URI", "")

    # IGV URI — optional integration; set per center or leave empty.
    IGV_URI = os.getenv("IGV_URI", "")

    # Report Config
    REPORTS_BASE_PATH = os.getenv("REPORTS_BASE_PATH", "/data/coyote3/reports")

    # Center public contact metadata. Runtime endpoints and secrets remain in env;
    # presentation content belongs in the center-owned TOML file.
    CONTACT: dict[str, Any] = _load_contact_config(
        CONTACT_CONFIG_PATH,
        organization_name=ORGANIZATION_NAME,
        public_base_url=PUBLIC_BASE_URL,
        script_name=SCRIPT_NAME,
    )

    # SEARCH LIMITS
    TIERED_VARIANT_SEARCH_LIMIT = 1000
    SAMPLE_SEARCH_LIMIT = 1000
    REPORTED_SAMPLES_SEARCH_LIMIT = 50

    @property
    def MONGO_URI(self) -> str:
        """
        Construct a MongoDB URI for connecting to the database.

        This property requires MONGO_URI.
        If MONGO_URI is provided without a database path, the current
        configured COYOTE3_DB is appended.

        Returns:
            str: The MongoDB connection URI.
        """
        if not self._MONGO_URI_ENV:
            raise ValueError("MONGO_URI must be set.")

        parsed = urlparse(self._MONGO_URI_ENV)
        has_db_path = bool((parsed.path or "").strip("/"))
        if has_db_path:
            return self._MONGO_URI_ENV
        return urlunparse(parsed._replace(path=f"/{self.COYOTE3_DB}"))

    @classmethod
    def validate_required_env(cls) -> None:
        """Hook for environment-specific required-variable validation."""
        return None

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
        db_config: dict[str, Any] = toml.load(str(self._PATH_DB_COLLECTIONS_CONFIG))

        if not all(db in db_config for db in [self.COYOTE3_DB, self.BAM_DB]):
            missing_dbs = [db for db in [self.COYOTE3_DB, self.BAM_DB] if db not in db_config]
            raise ValueError(
                f"Database(s) {', '.join(missing_dbs)} not found in the database configuration. Check the config file. ({self._PATH_DB_COLLECTIONS_CONFIG})"
            )

        # Filter the config to include only the relevant databases
        custom_db_config: dict[str, Any] = {
            db_name: collections
            for db_name, collections in db_config.items()
            if db_name in [self.COYOTE3_DB, self.BAM_DB]
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
