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
This module defines WTForms forms for user authentication and management in the Coyote3 project.

Classes:
    PasswordChangeForm: Form for changing a user's password with strong validation.
    SearchUserForm: Form for searching users by username.
"""


from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Regexp,
)


# PasswordChangeForm
class PasswordChangeForm(FlaskForm):
    """
    WTForms form for changing a user's password with strong validation requirements.

    Fields:
        old_password (PasswordField): The user's current password. Required.
        new_password (PasswordField): The new password. Must be at least 15 characters,
            contain at least one uppercase letter, one digit, and one special character.
        confirm_password (PasswordField): Confirmation of the new password. Must match new_password.
        submit (SubmitField): Button to submit the form.
    """

    old_password = PasswordField("Old Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(
                min=15, message="Password must be at least 15 characters long."
            ),
            Regexp(
                r"(?=.*[A-Z])",
                message="Password must contain at least one uppercase letter.",
            ),
            Regexp(
                r"(?=.*\d)",
                message="Password must contain at least one digit.",
            ),
            Regexp(
                r"(?=.*[\W_])",
                message="Password must contain at least one special character.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Change Password")


class SearchUserForm(FlaskForm):
    """
    WTForms form for searching users by username.

    Fields:
        username (StringField): The username to search for. Required.
        submit (SubmitField): Button to submit the search form.
    """

    username = StringField("Username", validators=[DataRequired()])
    submit = SubmitField("Search")
