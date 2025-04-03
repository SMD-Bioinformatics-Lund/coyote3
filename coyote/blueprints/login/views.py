# login_bp dependencies
from flask import current_app as app, flash
from flask import redirect, render_template, request, url_for, session
from flask_login import login_user, logout_user


from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm

from coyote.models.user import UserModel
from coyote.services.auth.user_session import User
from coyote.extensions import login_manager, mongo, ldap_manager, store

INTERNAL_USERS = {
    "coyote3.developer@skane.se",
    "coyote3.tester@skane.se",
    "coyote3.external@skane.se",
}


# Login routes:
@login_bp.route("/", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        username = str(form.username.data).strip()
        password = str(form.password.data).strip()

        user_doc = store.user_handler.user(username)
        if not user_doc:
            flash("User not found in system.", "red")
            app.logger.error(f"User not found: {username}")
            return render_template("login.html", form=form)

        use_internal = username in INTERNAL_USERS
        valid = (
            UserModel.validate_login(user_doc["password"], password)
            if use_internal
            else ldap_authenticate(username, password)
        )

        if not valid:
            app.logger.warning(f"Auth failed for user: {username} (internal: {use_internal})")
            return render_template("login.html", form=form, error="Invalid credentials")

        if not user_doc.get("is_active", True):
            flash("Your account is inactive. Please contact the administrator.", "red")
            app.logger.warning(f"Inactive login attempt: {username}")
            return render_template("login.html", form=form)

        # Login user
        user_model = UserModel(**user_doc)
        user = User(user_model)
        login_user(user)

        # Update last login timestamp
        user_doc = store.user_handler.user(username)
        store.user_handler.update_user_last_login(user_doc.get("_id"))

        return redirect(url_for("home_bp.home_screen"))

    return render_template("login.html", title="Login", form=form)


@login_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login_bp.login"))


@login_manager.user_loader
def load_user(username):
    user = store.user_handler.user_with_id(username)
    if not user:
        return None
    user_model = UserModel(**user)
    return User(user_model)


def ldap_authenticate(username, password):
    authorized = False

    try:
        authorized = ldap_manager.authenticate(
            username=username,
            password=password,
            base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
        )
    except Exception as ex:
        flash(ex, "red")

    return authorized
