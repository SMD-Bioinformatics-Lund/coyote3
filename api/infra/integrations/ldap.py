"""LDAP authentication helper for API runtime."""

from __future__ import annotations

import logging
import re
import ssl
from urllib.parse import urlsplit

from ldap3 import (
    ALL,
    ANONYMOUS,
    AUTO_BIND_NO_TLS,
    AUTO_BIND_TLS_BEFORE_BIND,
    SIMPLE,
    SUBTREE,
    Connection,
    Server,
    Tls,
)
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPInvalidDnError
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import parse_dn

LOG = logging.getLogger(__name__)


class LdapManager:
    """Framework-neutral LDAP manager used by API auth service."""

    def __init__(self) -> None:
        """Create an unconfigured manager; initialization does not bind to LDAP."""
        self._config: dict = {}
        self._server: Server | None = None

    @property
    def is_configured(self) -> bool:
        """Return whether this runtime has an initialized LDAP server."""
        return self._server is not None

    def init_from_config(self, config: dict) -> bool:
        """Initialize LDAP settings when this deployment configures LDAP.

        LDAP provider selection is controlled by deployment configuration. The
        connection settings may be absent at process startup; in that case the
        manager remains uninitialized and an LDAP login receives a clear
        configuration error at the authentication boundary.
        """
        self._config = {}
        self._server = None

        host = str(config.get("LDAP_HOST") or "").strip()
        if not host:
            LOG.info("LDAP connection settings are absent; LDAP manager remains uninitialized")
            return False
        endpoint = urlsplit(host if "://" in host else f"ldap://{host}")
        if (
            endpoint.scheme not in {"ldap", "ldaps"}
            or not endpoint.hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.path not in {"", "/"}
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("LDAP_HOST must be a hostname or ldap:// or ldaps:// endpoint")
        use_ssl = endpoint.scheme == "ldaps" or bool(config.get("LDAP_USE_SSL", False))
        port = int(config.get("LDAP_PORT") or endpoint.port or (636 if use_ssl else 389))
        timeout = int(config.get("LDAP_CONNECT_TIMEOUT", 10))
        if not 1 <= port <= 65535 or timeout <= 0:
            raise ValueError("LDAP_PORT must be 1-65535 and LDAP_CONNECT_TIMEOUT must be positive")
        if bool(config.get("LDAP_BINDDN")) != bool(config.get("LDAP_SECRET")):
            raise ValueError("Configure both LDAP_BINDDN and LDAP_SECRET, or leave both empty")
        self._config = {**config, "LDAP_USE_SSL": use_ssl, "LDAP_PORT": port}
        if not use_ssl and not config.get("LDAP_USE_TLS", True):
            LOG.warning(
                "LDAP transport is unencrypted; enable StartTLS or LDAPS before production use"
            )

        tls = Tls(
            local_private_key_file=config.get("LDAP_CLIENT_PRIVATE_KEY"),
            local_certificate_file=config.get("LDAP_CLIENT_CERT"),
            validate=ssl.CERT_REQUIRED,
            version=config.get("LDAP_TLS_VERSION"),
            ca_certs_file=config.get("LDAP_CA_CERTS_FILE") or None,
            valid_names=config.get("LDAP_VALID_NAMES"),
            ca_certs_path=config.get("LDAP_CA_CERTS_PATH"),
            ca_certs_data=config.get("LDAP_CA_CERTS_DATA"),
            local_private_key_password=config.get("LDAP_PRIVATE_KEY_PASSWORD"),
        )

        self._server = Server(
            host=endpoint.hostname,
            port=port,
            use_ssl=use_ssl,
            connect_timeout=timeout,
            tls=tls,
            get_info=ALL,
        )
        LOG.info(
            "LDAP server host='%s' port=%s use_ssl=%s",
            endpoint.hostname,
            port,
            use_ssl,
        )
        return True

    def _auto_bind_mode(self) -> int:
        """Use StartTLS before bind unless the socket already uses implicit TLS."""
        if self._config.get("LDAP_USE_TLS", True) and not self._config.get("LDAP_USE_SSL", False):
            return AUTO_BIND_TLS_BEFORE_BIND
        return AUTO_BIND_NO_TLS

    def _connect(
        self,
        user: str | None,
        password: str | None,
        *,
        anonymous: bool = False,
        read_only: bool = True,
    ) -> Connection:
        """Open a bound, read-only connection using the configured transport.

        Args:
            user: Bind DN, or None for anonymous search.
            password: Bind password; never written to logs.
            anonymous: Use anonymous authentication instead of simple bind.
            read_only: Prevent directory modifications through this connection.

        Returns:
            Bound connection owned by the caller, which must unbind it.

        Raises:
            LDAPException: The server is unconfigured or connection/bind fails.
        """
        if self._server is None:
            raise LDAPBindError("LDAP server not initialized")
        return Connection(
            self._server,
            auto_bind=self._auto_bind_mode(),
            authentication=ANONYMOUS if anonymous else SIMPLE,
            user=None if anonymous else user,
            password=None if anonymous else password,
            raise_exceptions=False,
            read_only=read_only,
            auto_referrals=False,
            receive_timeout=int(self._config.get("LDAP_CONNECT_TIMEOUT", 10)),
        )

    def _lookup_user_dn(self, username: str, base_dn: str, attribute: str) -> str | None:
        """Resolve exactly one directory entry with an escaped equality filter.

        Args:
            username: Submitted login value, escaped as LDAP filter data.
            base_dn: Complete configured directory search base.
            attribute: Configured LDAP attribute name or numeric OID.

        Returns:
            Unique matching DN, or None after failed or ambiguous lookup.
        """
        if not re.fullmatch(
            r"(?:[A-Za-z][A-Za-z0-9-]*|[0-9]+(?:\.[0-9]+)+)(?:;[A-Za-z0-9-]+)*", attribute
        ):
            return None
        bind_dn = self._config.get("LDAP_BINDDN")
        bind_secret = self._config.get("LDAP_SECRET")
        anonymous = not (bind_dn and bind_secret)
        conn = None
        try:
            conn = self._connect(
                user=str(bind_dn) if bind_dn else None,
                password=str(bind_secret) if bind_secret else None,
                anonymous=anonymous,
                read_only=True,
            )
            if not conn.bound:
                return None
            user_filter = f"({attribute}={escape_filter_chars(username)})"
            succeeded = conn.search(
                base_dn,
                user_filter,
                SUBTREE,
                attributes=[attribute],
                size_limit=2,
            )
            entries = [
                item for item in (conn.response or []) if item.get("type") == "searchResEntry"
            ]
            if not succeeded or len(entries) != 1:
                return None
            dn = entries[0].get("dn")
            return str(dn) if dn else None
        except LDAPException as error:
            LOG.warning("LDAP directory lookup failed (%s)", type(error).__name__)
            return None
        finally:
            self._close_connection(conn)

    @staticmethod
    def _close_connection(connection: Connection | None) -> None:
        """Unbind without replacing an authentication result with a cleanup error."""
        if connection is None:
            return
        try:
            connection.unbind()
        except LDAPException as error:
            LOG.warning("LDAP connection cleanup failed (%s)", type(error).__name__)

    def authenticate(
        self,
        username: str,
        password: str,
        base_dn: str | None = None,
        attribute: str | None = None,
    ) -> bool:
        """Resolve a login identifier and verify its password with a user bind.

        Args:
            username: Login identifier or an explicit directory DN.
            password: Submitted directory password.
            base_dn: Complete search base, required for non-DN identifiers.
            attribute: Search attribute, required for non-DN identifiers.

        Returns:
            False for empty credentials, missing configuration, lookup failures,
            ambiguous entries, or rejected binds; True for a successful user bind.
        """
        if not username or not password or self._server is None:
            return False

        bind_user = username
        try:
            parse_dn(username)
        except LDAPInvalidDnError:
            if not base_dn or not attribute:
                return False
            resolved_dn = self._lookup_user_dn(
                username=username, base_dn=base_dn, attribute=attribute
            )
            if not resolved_dn:
                return False
            bind_user = resolved_dn

        conn = None
        try:
            conn = self._connect(user=bind_user, password=password, read_only=True)
            return bool(conn.bound)
        except LDAPException as error:
            LOG.warning("LDAP user bind failed (%s)", type(error).__name__)
            return False
        finally:
            self._close_connection(conn)
