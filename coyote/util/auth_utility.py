"""Authentication-related utility helpers."""

from flask import current_app as app

from coyote.extensions import ldap_manager


class AuthUtility:
    @staticmethod
    def ldap_authenticate(username: str, password: str) -> bool:
        try:
            return bool(
                ldap_manager.authenticate(
                    username=username,
                    password=password,
                    base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
                    attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
                )
            )
        except Exception:
            app.logger.exception("LDAP authentication error for %s", username)
            return False

