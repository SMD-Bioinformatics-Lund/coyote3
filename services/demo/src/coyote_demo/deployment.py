# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Reject demo installation settings that could select ordinary application storage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

DEMO_DATABASES = {
    "COYOTE4_DB": "coyote4_demo",
    "IDENTITY_DB": "coyote4_demo_identity",
    "KNOWLEDGEBASE_DB": "coyote4_demo_knowledgebase",
    "BAM_DB": "coyote4_demo_bam",
}
DEMO_MONGO_URI_KEYS = (
    "COYOTE4_MONGO_URI",
    "IDENTITY_MONGO_URI",
    "KNOWLEDGEBASE_MONGO_URI",
    "BAM_MONGO_URI",
)
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _endpoint(value: Any, *, key: str, scheme: str, hosts: set[str]):
    """Parse one explicitly authenticated endpoint without exposing its credentials.

    Args:
        value: URI supplied by the reviewed demo configuration.
        key: Setting name used in validation errors.
        scheme: Required URI scheme, without SRV discovery.
        hosts: Exact hosts permitted for the selected deployment mode.

    Returns:
        Parsed URI with an explicit port, username and password.

    Raises:
        ValueError: The URI is missing, malformed, unauthenticated or off-target.
    """
    try:
        endpoint = urlsplit(str(value or ""))
        valid = (
            endpoint.scheme == scheme
            and endpoint.hostname in hosts
            and endpoint.port is not None
            and endpoint.username
            and endpoint.password
            and not endpoint.fragment
            and "," not in endpoint.netloc
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError(f"{key} must use an explicitly authenticated local demo endpoint")
    return endpoint


def validate_demo_target(settings: Mapping[str, Any]) -> None:
    """Validate an explicitly enabled Docker or native demonstration deployment.

    Args:
        settings: Resolved host settings plus explicit package-owned
            COYOTE_DEMO_ENABLED and COYOTE_DEMO_MODE values. No environment is read.
            Every database URI must be supplied; ordinary host fallbacks are rejected.

    Raises:
        ValueError: A target, credential, environment or external integration falls
            outside the local demo policy. Errors name settings, never URI secrets.

    Notes:
        This is a configuration check, not a database privilege check. Before any
        demo writes, callers must also validate the authenticated MongoDB privileges.
    """
    if str(settings.get("COYOTE_DEMO_ENABLED", "")).lower() not in {"1", "true"}:
        raise ValueError("COYOTE_DEMO_ENABLED must explicitly enable the demo")
    mode = settings.get("COYOTE_DEMO_MODE")
    if mode not in {"docker", "native"}:
        raise ValueError("COYOTE_DEMO_MODE must be docker or native")
    if settings.get("ENV_NAME") != "testing":
        raise ValueError("Demo deployments require ENV_NAME=testing")
    if settings.get("COYOTE4_RUNTIME_MODE") != "production":
        raise ValueError("Demo deployments require the production security runtime")
    for key in ("TESTING", "DEVELOPMENT"):
        if str(settings.get(key, "")).lower() not in {"0", "false"}:
            raise ValueError(f"{key} must be explicitly disabled for demo deployments")
    runtime_root = Path(str(settings.get("COYOTE4_RUNTIME_ROOT") or ""))
    data_root = Path(str(settings.get("COYOTE4_DATA_ROOT") or ""))
    if mode == "docker":
        valid_storage = runtime_root == Path("/app") and data_root == Path("/data")
    else:
        valid_storage = (
            runtime_root.is_absolute()
            and runtime_root.name == "runtime"
            and data_root == runtime_root.parent / "data"
            and ".." not in runtime_root.parts
        )
    if not valid_storage:
        raise ValueError("Demo runtime and data roots must select isolated demo storage")
    for key, database in DEMO_DATABASES.items():
        if settings.get(key) != database:
            raise ValueError(f"{key} must select the dedicated demo database")
    mongo_hosts = {"demo-mongo"} if mode == "docker" else _LOOPBACK_HOSTS
    for key in DEMO_MONGO_URI_KEYS:
        endpoint = _endpoint(settings.get(key), key=key, scheme="mongodb", hosts=mongo_hosts)
        try:
            options = parse_qs(endpoint.query, strict_parsing=True)
        except ValueError:
            raise ValueError(f"{key} contains invalid MongoDB options") from None
        if (
            endpoint.username != "coyote_demo"
            or endpoint.path not in {"", "/", "/admin"}
            or options.get("authSource") != ["admin"]
            or not options.get("replicaSet")
            or set(options) - {"authSource", "replicaSet", "directConnection"}
            or options.get("directConnection") != ["true"]
            or (mode == "docker" and endpoint.port != 27017)
        ):
            raise ValueError(f"{key} must select the restricted coyote_demo replica-set user")
    redis_hosts = {"demo-redis"} if mode == "docker" else _LOOPBACK_HOSTS
    for key, database in (
        ("CACHE_REDIS_URL", "0"),
        ("CELERY_BROKER_URL", "1"),
        ("CELERY_RESULT_BACKEND", "2"),
    ):
        endpoint = _endpoint(settings.get(key), key=key, scheme="redis", hosts=redis_hosts)
        if (
            endpoint.path != f"/{database}"
            or endpoint.query
            or (mode == "docker" and endpoint.port != 6379)
        ):
            raise ValueError(f"{key} must select its dedicated demo Redis database")
    if settings.get("AUTHENTICATION_PROVIDERS") != "local":
        raise ValueError("Demo authentication must use the local provider only")
    for key in ("LDAP_HOST", "SMTP_HOST", "GENS_URI", "IGV_URI"):
        if settings.get(key):
            raise ValueError(f"{key} must be disabled for demo deployments")
    for key in ("ONCOKB_PUBLIC_LOOKUPS_ENABLED", "CLINPGX_PUBLIC_LOOKUPS_ENABLED"):
        if str(settings.get(key, "")).lower() not in {"0", "false"}:
            raise ValueError(f"{key} must be explicitly disabled for demo deployments")
    public = urlsplit(str(settings.get("PUBLIC_BASE_URL") or ""))
    if (
        public.scheme != "http"
        or public.hostname not in _LOOPBACK_HOSTS
        or public.username
        or public.password
        or public.query
        or public.fragment
    ):
        raise ValueError("PUBLIC_BASE_URL must select the local HTTP demo")


def validate_demo_privileges(privileges: Iterable[Mapping[str, Any]]) -> None:
    """Reject MongoDB credentials with authority outside the four demo databases.

    Args:
        privileges: Expanded authenticatedUserPrivileges returned by the connected
            client's connectionStatus command with showPrivileges enabled.

    Raises:
        ValueError: Privileges are absent, cover other databases, grant cluster-wide
            authority or cannot write the required demonstration databases.
    """
    allowed = set(DEMO_DATABASES.values())
    writable: set[str] = set()
    for privilege in privileges:
        resource = privilege.get("resource") or {}
        database = resource.get("db")
        if (
            database not in allowed
            or set(resource) - {"db", "collection"}
            or not isinstance(resource.get("collection"), str)
        ):
            raise ValueError("MongoDB demo credentials must be restricted to demo databases")
        if resource["collection"] == "" and {"find", "insert", "update"} <= set(
            privilege.get("actions") or ()
        ):
            writable.add(database)
    if writable != allowed:
        raise ValueError("MongoDB demo credentials require write access to all demo databases")


def validate_runtime(settings: Mapping[str, Any]) -> None:
    """Validate enabled demo processes before the host creates persistence services.

    Args:
        settings: Only the deployment keys declared by DemoRuntimeValidator,
            explicitly projected by the host. Disabled demonstrations do nothing.

    Raises:
        ValueError: Enabled settings or authenticated privileges are not demo-only.
        PyMongoError: The selected local MongoDB cannot authenticate the demo user.

    Notes:
        The enabled host integration requires the server extra. It connects only
        after configuration validation and issues connectionStatus read commands;
        no application collections or credentials are changed.
    """
    if str(settings.get("COYOTE_DEMO_ENABLED", "")).lower() not in {"1", "true"}:
        return
    validate_demo_target(settings)
    from coyote_demo.host import validate_runtime_credentials

    validate_runtime_credentials(settings)


class DemoRuntimeValidator:
    """Declare the small host configuration projection required by demo isolation."""

    configuration_keys = (
        "COYOTE_DEMO_ENABLED",
        "COYOTE_DEMO_MODE",
        "COYOTE4_RUNTIME_MODE",
        "ENV_NAME",
        "COYOTE4_RUNTIME_ROOT",
        "COYOTE4_DATA_ROOT",
        "TESTING",
        "DEVELOPMENT",
        *DEMO_DATABASES,
        *DEMO_MONGO_URI_KEYS,
        "CACHE_REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "AUTHENTICATION_PROVIDERS",
        "LDAP_HOST",
        "SMTP_HOST",
        "GENS_URI",
        "IGV_URI",
        "ONCOKB_PUBLIC_LOOKUPS_ENABLED",
        "CLINPGX_PUBLIC_LOOKUPS_ENABLED",
        "PUBLIC_BASE_URL",
    )

    def __call__(self, settings: Mapping[str, Any]) -> None:
        """Validate the host-projected demo settings before initialization.

        Args:
            settings: Explicit values for configuration_keys only.

        Raises:
            ValueError: An enabled deployment is unsafe.
            PyMongoError: The local demo credential cannot be verified.
        """
        validate_runtime(settings)


runtime_validator = DemoRuntimeValidator()
