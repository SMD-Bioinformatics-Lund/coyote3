
"""
This module defines form classes for user authentication in the Coyote3 project.

Classes:
    LoginForm: A Flask-WTF form for user login, requiring username and password fields.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    """
    A form for user authentication in the Coyote3 project.

    Fields
    ------
    username : StringField
        The username of the user. Required.
    password : PasswordField
        The password of the user. Required.
    """

    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
