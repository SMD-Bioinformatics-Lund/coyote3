"""API deployment defaults reuse core policy while retaining their own ownership."""

from coyote.config.factory_defaults import factory_value
from coyote_api.config.factory_defaults import api_default
from coyote_api.config.runtime_settings import OperationsSettings


def test_api_environment_fallback_conversion_preserves_types():
    """False strings must remain false and numeric fallbacks remain usable."""
    assert api_default("runtime.SMTP_USE_SSL", bool) is False
    assert api_default("runtime.API_RATE_LIMIT_ENABLED", bool) is True
    assert api_default("runtime.API_SESSION_TTL_SECONDS", int) == 43200


def test_api_and_core_share_the_same_retention_policy_defaults():
    """Deployment fallbacks derive from domain policy rather than declaring it again."""
    retention = factory_value("controls.RetentionControlDoc")
    assert OperationsSettings.AUDIT_RETENTION_DAYS == retention["audit_events_days"]
    assert OperationsSettings.NOTIFICATION_RETENTION_DAYS == retention["notification_days"]
    assert OperationsSettings.LOG_RETENTION_DAYS == retention["disk_log_days"]
    assert OperationsSettings.LOG_GZIP_AFTER_DAYS == retention["gzip_disk_logs_after_days"]


def test_api_catalog_has_no_ui_default_sections():
    """The API owns deployment settings, not display defaults."""
    import tomllib

    from coyote_api.config.factory_defaults import API_DEFAULTS_PATH

    with API_DEFAULTS_PATH.open("rb") as handle:
        catalog = tomllib.load(handle)
    assert set(catalog) == {"runtime", "profiles", "product", "http_clients", "modes"}
