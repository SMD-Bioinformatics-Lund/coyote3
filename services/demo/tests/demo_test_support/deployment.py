"""Explicit synthetic deployment inputs for demo isolation tests."""

from coyote_demo.deployment import DEMO_DATABASES, DEMO_MONGO_URI_KEYS


def demo_settings():
    """Return an enabled Docker demo mapping without any operational credentials."""
    mongo = (
        "mongodb://coyote_demo:synthetic-password@demo-mongo:27017/"
        "?authSource=admin&replicaSet=coyote-demo-rs&directConnection=true"
    )
    return {
        **DEMO_DATABASES,
        **dict.fromkeys(DEMO_MONGO_URI_KEYS, mongo),
        "COYOTE_DEMO_ENABLED": "1",
        "COYOTE_DEMO_MODE": "docker",
        "ENV_NAME": "testing",
        "COYOTE4_RUNTIME_ROOT": "/app",
        "COYOTE4_DATA_ROOT": "/data",
        "COYOTE4_RUNTIME_MODE": "production",
        "TESTING": "0",
        "DEVELOPMENT": "0",
        "CACHE_REDIS_URL": "redis://default:synthetic-password@demo-redis:6379/0",
        "CELERY_BROKER_URL": "redis://default:synthetic-password@demo-redis:6379/1",
        "CELERY_RESULT_BACKEND": "redis://default:synthetic-password@demo-redis:6379/2",
        "AUTHENTICATION_PROVIDERS": "local",
        "LDAP_HOST": "",
        "SMTP_HOST": "",
        "GENS_URI": "",
        "IGV_URI": "",
        "ONCOKB_PUBLIC_LOOKUPS_ENABLED": "0",
        "CLINPGX_PUBLIC_LOOKUPS_ENABLED": "0",
        "PUBLIC_BASE_URL": "http://127.0.0.1:8089",
    }


def demo_privileges():
    """Return MongoDB-expanded grants limited to the four demonstration databases."""
    return [
        {"resource": {"db": name, "collection": ""}, "actions": ["find", "insert", "update"]}
        for name in DEMO_DATABASES.values()
    ]
