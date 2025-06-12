# login_bp dependencies
from flask import current_app as app, flash
from flask import redirect, render_template, request, url_for, session
from flask_login import login_user, logout_user

from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm

from coyote.models.user import UserModel
from coyote.services.auth.user_session import User
from coyote.extensions import login_manager, mongo, ldap_manager, store


# Login route
@login_bp.route("/", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        email = form.username.data.strip()
        password = form.password.data.strip()

        # Fetch user
        user_doc = store.user_handler.user(email)
        if not user_doc or not user_doc.get("is_active", True):
            flash("User not found or inactive.", "red")
            app.logger.warning(
                f"Login failed: user not found or inactive ({email})"
            )
            return render_template("login.html", form=form)

        # Authenticate
        use_internal = user_doc.get("auth_type") == "coyote3"
        valid = (
            UserModel.validate_login(user_doc["password"], password)
            if use_internal
            else ldap_authenticate(email, password)
        )

        if not valid:
            flash("Invalid credentials", "red")
            app.logger.warning(f"Login failed: invalid credentials ({email})")
            return render_template("login.html", form=form)

        # Merge role + build user model
        role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
        user_model = UserModel.from_mongo(user_doc, role_doc)
        user = User(user_model)

        # Login and update last login timestamp
        login_user(user)
        store.user_handler.update_user_last_login(user_doc["_id"])
        app.logger.info(
            f"User logged in: {email} (access_level: {user.access_level})"
        )

        return redirect(url_for("home_bp.samples_home"))

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login_bp.login"))


@login_manager.user_loader
def load_user(user_id: str):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        return None

    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    user_model = UserModel.from_mongo(user_doc, role_doc)
    return User(user_model)


def ldap_authenticate(username, password):
    authorized = False

    try:
        authorized = ldap_manager.authenticate(
            username=username,
            password=password,
            base_dn=app.config.get("LDAP_BASE_DN")
            or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
        )
    except Exception as ex:
        flash(ex, "red")

    return authorized
