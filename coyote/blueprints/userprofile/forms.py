from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, EmailField
from wtforms.validators import DataRequired, Email, Optional, EqualTo, Length, Regexp
from coyote.extensions import store


class UserForm(FlaskForm):
    """
    User form with enhanced password validation and email validation.
    """

    fullname = StringField("Full Name", validators=[DataRequired(message="Full Name is required.")])

    username = StringField(
        "User Name",
        validators=[
            DataRequired(message="User Name is required."),
            Regexp(
                r"^[a-zA-Z0-9_.]+$",
                message="Username must contain only letters, numbers, and underscores.",
            ),
        ],
    )

    email = EmailField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Invalid email address."),
        ],
    )

    password = PasswordField(
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
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )

    groups = StringField("Groups", validators=[DataRequired(message="Groups are required.")])
    role = SelectField(
        "Role",
        choices=[("user", "User"), ("admin", "Admin")],
        validators=[DataRequired(message="Role is required.")],
    )
    submit = SubmitField("Create User")


class UserUpdateForm(UserForm):
    password = PasswordField("New Password", validators=[Optional()])
    confirm_password = PasswordField("Confirm New Password", validators=[Optional()])
    submit = SubmitField("Update Information")


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


class SearchUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    submit = SubmitField("Search")
