# login_bp dependencies
from flask import current_app as app, flash
from flask import redirect, render_template, request, url_for, session
from flask_login import login_user, logout_user


from coyote.blueprints.login import login_bp
from coyote.blueprints.login.login import LoginForm, User
from coyote.extensions import login_manager, mongo
from flask_ldapconn import LDAPConn

ldap_manager = LDAPConn(app)

users_collection = mongo.cx["coyote"]["users"]

# Login routes:

@login_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        username = str(form.username.data)
        password = str(form.password.data)
        if ldap_authenticate(username, password):
            app.logger.info("anything?")
            session['username'] = username
            return redirect(url_for('home'))
        else:
            app.logger.info("yes?")
            return render_template('login.html',form=form, error="Invalid credentials")

    return render_template("login.html", title="login", form=form)


@login_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login_bp.login"))


@login_manager.user_loader
def load_user(username):
    user = users_collection.find_one({"_id": username})
    if not user:
        return None
    return User(user["_id"], user["groups"])

def ldap_authenticate(username, password):
    authorized = False
    try:
        ldap_manager.authenticate(
            username="test",
            password="tesiter",
            base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR")
        )
        app.logger.info(f"am I? {authorized}")
    except Exception as ex:
        flash(ex, "danger")

    return authorized