# login_bp dependencies
from flask import current_app as app, flash
from flask import redirect, render_template, request, url_for, session
from flask_login import login_user, logout_user


from coyote.blueprints.login import login_bp
from coyote.blueprints.login.forms import LoginForm

from coyote.models.user import UserModel
from coyote.services.auth.user_session import User
from coyote.extensions import login_manager, mongo, ldap_manager, store


# users_collection = mongo.cx["coyote"]["users"]

# Login routes:


@login_bp.route("/", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        username = str(form.username.data)
        password = str(form.password.data)
        if ldap_authenticate(username, password):
            user_doc = store.user_handler.user(username)
            user_model = UserModel(**user_doc)
            user = User(user_model)
            login_user(user)
            return redirect(url_for("home_bp.home_screen"))
        else:
            app.logger.info("yes?")
            return render_template("login.html", form=form, error="Invalid credentials")

    return render_template("login.html", title="login", form=form)


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
