# views.py

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from coyote.extensions import store
from coyote.blueprints.userprofile.forms import PasswordChangeForm
from coyote.services.auth.user_session import User
from coyote.blueprints.userprofile import profile_bp
from flask_wtf.csrf import generate_csrf
from coyote.extensions import util
from datetime import datetime


@profile_bp.route("/", methods=["GET"])
@login_required
def profile():
    """
    Profile page for the user
    """
    csrf_token = generate_csrf()

    return render_template(
        "profile.html",
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value.title(),
        groups=current_user.groups,
        fullname=current_user.fullname,
        csrf_token=csrf_token,
    )


# TODO: Should be a ldap call currently disabled
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
    Update current user's profile info (fullname, optionally groups if admin)
    """
    data = request.get_json() or {}

    user_id = current_user.username
    fullname = data.get("fullname", "").strip()
    groups = data.get("groups", [])

    if fullname:
        store.user_handler.update_user_fullname(user_id, fullname)

    if current_user.is_admin and isinstance(groups, list):
        store.user_handler.update_user_groups(user_id, groups)

    # Optionally update timestamp
    store.user_handler.update_user_timestamp(user_id, field="updated")

    return jsonify({"status": "success"})
