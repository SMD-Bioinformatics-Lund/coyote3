"""LDAP authentication helper for API runtime."""

from __future__ import annotations

import logging
import ssl
from urllib.parse import urlparse

from ldap3 import ALL, Connection, Server, Tls

LOG = logging.getLogger(__name__)


class LdapManager:
    """Framework-neutral LDAP manager used by API auth service."""

    def __init__(self) -> None:
        self._config: dict = {}
        self._server: Server | None = None

    def init_from_config(self, config: dict) -> None:
        """Initialize LDAP server settings from runtime config."""
        self._config = config
        ssl_defaults = ssl.get_default_verify_paths()

        host_value = str(config.get("LDAP_HOST") or config.get("LDAP_SERVER") or "localhost")
        parsed = urlparse(host_value) if "://" in host_value else None
        host = parsed.hostname if parsed and parsed.hostname else host_value

        use_ssl = bool(config.get("LDAP_USE_SSL", False))
        if parsed and parsed.scheme == "ldaps":
            use_ssl = True

        port = int(config.get("LDAP_PORT") or (parsed.port if parsed else 389) or 389)

        tls = Tls(
            local_private_key_file=config.get("LDAP_CLIENT_PRIVATE_KEY"),
            local_certificate_file=config.get("LDAP_CLIENT_CERT"),
            validate=(
                config.get("LDAP_REQUIRE_CERT", ssl.CERT_REQUIRED)
                if config.get("LDAP_CLIENT_CERT")
                else ssl.CERT_NONE
            ),
            version=config.get("LDAP_TLS_VERSION", ssl.PROTOCOL_TLSv1_2),
            ca_certs_file=config.get("LDAP_CA_CERTS_FILE", ssl_defaults.cafile),
            valid_names=config.get("LDAP_VALID_NAMES"),
            ca_certs_path=config.get("LDAP_CA_CERTS_PATH", ssl_defaults.capath),
            ca_certs_data=config.get("LDAP_CA_CERTS_DATA"),
            local_private_key_password=config.get("LDAP_PRIVATE_KEY_PASSWORD"),
        )

        self._server = Server(
            host=host,
            port=port,
            use_ssl=use_ssl,
            connect_timeout=int(config.get("LDAP_CONNECT_TIMEOUT", 10)),
            tls=tls,
            get_info=ALL,
        )

    def authenticate(
        self,
        username: str,
        password: str,
        base_dn: str | None = None,
        attribute: str | None = None,
    ) -> bool:
        """Authenticate credentials against configured LDAP server."""
        if not username or not password or self._server is None:
            return False

        if base_dn and attribute:
            bind_user = f"{attribute}={username},{base_dn}"
        else:
            bind_user = username

        try:
            conn = Connection(
                self._server,
                user=bind_user,
                password=password,
                auto_bind=True,
                raise_exceptions=False,
                read_only=True,
            )
            ok = bool(conn.bound)
            conn.unbind()
            return ok
        except Exception as exc:
            LOG.warning("LDAP authentication failed for '%s': %s", username, exc)
            return False

