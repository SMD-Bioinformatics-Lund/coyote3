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
This module defines the User session class for Flask-Login integration.

Classes:
    User: Wraps a UserModel instance to provide user session management
          and access control for the Coyote3 framework.
"""

from flask_login import UserMixin
from coyote.models.user import UserModel


class User(UserMixin):
    """
    User session wrapper for Flask-Login integration.

    This class wraps a `UserModel` instance to provide session management
    and access control for the Coyote3 framework.

    Args:
        user_model (UserModel): The user model instance to wrap.

    Attributes:
        user_model (UserModel): The underlying user model instance.
    """

    def __init__(self, user_model: UserModel):
        """
        Initialize the User session with a UserModel instance.

        Args:
            user_model (UserModel): The user model instance to wrap.
        """
        self.user_model = user_model

    def get_id(self) -> str:
        """
        Return the unique identifier for the user.

        Returns:
            str or int: The unique ID of the user, as required by Flask-Login.
        """
        return self.user_model.id

    def __getattr__(self, name) -> any:
        """
        Delegate attribute access to the underlying user_model.

        Args:
            name (str): The attribute name to access.

        Returns:
            Any: The value of the requested attribute from user_model.

        Raises:
            AttributeError: If the attribute does not exist on user_model.
        """
        return getattr(self.user_model, name)

    def to_dict(self) -> dict:
        """
        Serialize the user session to a dictionary.

        Returns:
            dict: A dictionary representation of the underlying user model.
        """
        return self.user_model.to_dict()

    @property
    def access_level(self):
        """
        Get the access level of the user.

        Returns:
            The access level attribute from the underlying user model.
        """
        return self.user_model.access_level
