# views.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from coyote.extensions import store
from coyote.blueprints.userprofile.profile import ProfileForm, PasswordChangeForm
from coyote.blueprints.login.login import User
from coyote.blueprints.userprofile import profile_bp
from flask_wtf.csrf import generate_csrf


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """
    Profile page for the user
    """
    user = store.user_handler.user_with_id(current_user.get_id())
    groups = list(filter(None, user.get("groups", [])))
    email = user.get("email", "")
    username = user.get("_id", "")
    if user.get("role"):
        role = user.get("role")
    else:
        role = "Admin" if "admin" in groups or "Admin" in groups else "User"
    fullname = user.get("fullname", "")

    csrf_token = generate_csrf()

    return render_template(
        "profile.html",
        username=username,
        email=email,
        role=role,
        groups=groups,
        fullname=fullname,
        csrf_token=csrf_token,
    )


@profile_bp.route("/change-password/<username>", methods=["GET", "POST"])
@login_required
def change_password(username):
    """
    Change password for a user
    """

    form = PasswordChangeForm()
    user = store.user_handler.user_with_id(username)

    if form.validate_on_submit():
        if user and User.validate_login(user.password, form.old_password.data):
            store.user_handler.update_password(
                username,
                generate_password_hash(
                    form.new_password.data,
                    method="pbkdf2:sha256",
                ),
            )
            flash("Password updated successfully", "success")
            return redirect(url_for("profile_bp.profile"))
        else:
            form.old_password.errors.append("Old password is incorrect")

    return render_template("change_password.html", form=form, username=username)


@profile_bp.route("/update-info", methods=["POST"])
@login_required
def update_info():
    """
    Update user info
    """
    data = request.get_json()
    groups = data.get("groups", [])
    user_id = current_user.get_id()
    fullname = data.get("fullname", "")
    store.user_handler.update_user_fullname(user_id, fullname)
    if current_user.is_admin():
        store.user_handler.update_user_groups(user_id, groups)

    return jsonify({"status": "success"})
