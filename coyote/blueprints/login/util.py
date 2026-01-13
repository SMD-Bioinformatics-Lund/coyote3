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
Utility functions and classes for user authentication and login management.
Part of the Coyote3 genomic data analysis framework.
"""

from flask import current_app as app
from coyote.extensions import ldap_manager
from flask import flash


class LoginUtility:
    """
    LoginUtility provides helper methods for user authentication and session management.

    This class centralizes utilities used by the login blueprint, for example:
    - LDAP authentication (ldap_authenticate)
    - account lookup / provisioning hooks
    - password, session, and token handling helpers
    - integration with Flask flash messaging and application config

    Methods are implemented as staticmethods so they can be used without instantiating the class.
    """

    @staticmethod
    def ldap_authenticate(username: str, password: str) -> bool:
        """
        Authenticate a user against the configured LDAP server.

        Args:
            username (str): The username or login identifier.
            password (str): The user's password.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        authorized = False

        try:
            authorized = ldap_manager.authenticate(
                username=username,
                password=password,
                base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
                attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
            )
        except Exception as ex:
            app.logger.error(f"LDAP authentication error: {ex}")
            flash(str(ex), "red")

        return authorized
