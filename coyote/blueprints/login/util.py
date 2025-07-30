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
from coyote.extensions import store, ldap_manager
from flask import flash



class LoginUtility:
    """
    DNAUtility provides static utility methods for processing, annotating, and reporting DNA variants.
    It includes functions for variant classification, consequence selection, CNV handling, annotation text generation, and report preparation.
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
            flash(str(ex), "red")

        return authorized
