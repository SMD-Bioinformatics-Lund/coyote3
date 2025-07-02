from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
)

from coyote.models.user import AppRole


class UserForm(FlaskForm):
    """
    Form for creating a new user.
    """

    fullname = StringField("Full Name", validators=[DataRequired()])
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Regexp(
                r"^[a-zA-Z0-9_.]+$",
                message="Username must contain only letters, numbers, underscores, or dots.",
            ),
        ],
    )
    email = EmailField("Email", validators=[DataRequired(), Email()])
    job_title = StringField("Job Title", validators=[Optional()])
    groups = StringField(
        "Groups (comma-separated)", validators=[DataRequired()]
    )

    role = SelectField(
        "App Role",
        choices=[
            (role.value, role.value.replace("_", " ").title())
            for role in AppRole
        ],
        validators=[DataRequired()],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=15, message="Password must be at least 15 characters."),
            Regexp(
                r"(?=.*[A-Z])",
                message="Must include at least one uppercase letter.",
            ),
            Regexp(r"(?=.*\d)", message="Must include at least one digit."),
            Regexp(
                r"(?=.*[\W_])",
                message="Must include at least one special character.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )

    is_active = BooleanField("Is Active?", default=True)

    submit = SubmitField("Create User")


class UserUpdateForm(UserForm):
    """
    Inherited form for updating an existing user.
    Makes password optional.
    """

    password = PasswordField(
        "New Password (optional)",
        validators=[
            Optional(),
            Length(min=15, message="Password must be at least 15 characters."),
            Regexp(
                r"(?=.*[A-Z])",
                message="Must include at least one uppercase letter.",
            ),
            Regexp(r"(?=.*\d)", message="Must include at least one digit."),
            Regexp(
                r"(?=.*[\W_])",
                message="Must include at least one special character.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            Optional(),
            EqualTo("password", message="Passwords must match."),
        ],
    )

    submit = SubmitField("Update User")


class ProfileForm(FlaskForm):
    """
    Display or edit logged-in user's own profile.
    """

    username = StringField("Username", render_kw={"readonly": True})
    email = EmailField("Email", validators=[DataRequired(), Email()])
    fullname = StringField("Full Name", validators=[DataRequired()])
    job_title = StringField("Job Title", validators=[Optional()])
    role = StringField("Role", render_kw={"readonly": True})
    groups = StringField("Groups", render_kw={"readonly": True})
