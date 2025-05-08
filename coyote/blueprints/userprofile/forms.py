from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, EmailField
from wtforms.validators import DataRequired, Email, Optional, EqualTo, Length, Regexp
from coyote.extensions import store


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


class SearchUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    submit = SubmitField("Search")
