# forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, EqualTo, Length, Regexp


# ProfileForm
class ProfileForm(FlaskForm):
    """Profile form"""

    username = StringField("Username", validators=[DataRequired()])
    userid = StringField("User ID", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    role = StringField("Role", validators=[Optional()])
    groups = StringField("Groups", validators=[Optional()])


# PasswordChangeForm


class PasswordChangeForm(FlaskForm):
    old_password = PasswordField("Old Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=15, message="Password must be at least 15 characters long."),
            Regexp(r"(?=.*[A-Z])", message="Password must contain at least one uppercase letter."),
            Regexp(r"(?=.*\d)", message="Password must contain at least one digit."),
            Regexp(r"(?=.*[\W_])", message="Password must contain at least one special character."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Change Password")
