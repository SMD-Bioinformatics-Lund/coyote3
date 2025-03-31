# views.py

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from coyote.extensions import store
from coyote.blueprints.userprofile.forms import (
    ProfileForm,
    PasswordChangeForm,
    UserForm,
    UserUpdateForm,
)
from coyote.services.auth.user_session import User
from coyote.blueprints.userprofile import profile_bp
from flask_wtf.csrf import generate_csrf
from coyote.extensions import util
from datetime import datetime


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def profile():
    """
    Profile page for the user
    """
    user = store.user_handler.user_with_id(current_user.username)
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
    user_id = current_user.username
    fullname = data.get("fullname", "")
    store.user_handler.update_user_fullname(user_id, fullname)
    if current_user.is_admin:
        store.user_handler.update_user_groups(user_id, groups)

    return jsonify({"status": "success"})


@profile_bp.route("/manage_users", methods=["POST", "GET"])
@login_required
def manage_users():
    """
    Manage user info
    """
    users = store.user_handler.get_all_users()
    # print(users)
    # print(jsonify({"users": users}))
    # return jsonify({"users": users})
    return render_template("manage_users.html", users=users)


@profile_bp.route("/update_user/<user_id>", methods=["GET", "POST"])
@login_required
def update_user(user_id):
    user = store.user_handler.user_with_id(user_id)
    form = UserUpdateForm(obj=user)
    if form.validate_on_submit():
        user["_id"] = form.username.data
        user["fullname"] = form.fullname.data
        user["email"] = form.email.data
        user["role"] = form.role.data
        user["groups"] = form.groups.data.split(",")
        user["updated"] = datetime.now()
        # Update the user in the database
        store.user_handler.update_user(user)
        flash("User updated successfully!", "success")
        return redirect(url_for("profile_bp.manage_users"))
    return render_template("update_user.html", form=form, user=user)


@profile_bp.route("/delete_user/<user_id>", methods=["GET", "POST"])
@login_required
def delete_user(user_id):
    store.user_handler.delete_user(user_id)
    redirect(url_for("profile_bp.manage_users"))


@profile_bp.route("/create_user", methods=["GET", "POST"])
@login_required
def create_user():
    form = UserForm()
    csrf_token = generate_csrf()
    if request.method == "POST" and form.validate_on_submit():
        print(form.data)
        user_data = util.profile.format_new_user_data(form.data)
        store.user_handler.create_user(user_data)
        # Process form data here (e.g., create new user in database)
        flash("User created successfully!", "success")
    return render_template("create_user.html", form=form, csrf_token=csrf_token)


@profile_bp.route("/validate_username", methods=["POST"])
@login_required
def validate_username():
    username = request.json.get("username")
    if store.user_handler.user_exists(user_id=username):
        return jsonify({"exists": True})
    return jsonify({"exists": False})


@profile_bp.route("/validate_email", methods=["POST"])
@login_required
def validate_email():
    email = request.json.get("email")
    if store.user_handler.user_exists(email=email):
        return jsonify({"exists": True})
    return jsonify({"exists": False})
