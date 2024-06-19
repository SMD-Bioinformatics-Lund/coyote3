"""Login page routes, login_mangager funcs and User class"""

# LoginForm dependencies
from flask_wtf import FlaskForm

# User-class dependencies:
from werkzeug.security import check_password_hash
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired


# User class:
class User:
    def __init__(self, username, groups, role):
        self.username = username
        self.groups = groups
        self.role = role

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.username

    def get_groups(self):
        return self.groups

    def get_role(self):
        if self.role:
            return self.role
        return "admin" if "admin" in self.groups else "user"

    @staticmethod
    def validate_login(password_hash, password):
        return check_password_hash(password_hash, password)


# LoginForm
class LoginForm(FlaskForm):
    """Login form"""

    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
