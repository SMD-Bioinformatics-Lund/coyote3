#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Coyote admin views.
"""

from flask import (
    redirect,
    render_template,
    request,
    url_for,
    flash,
    abort,
    jsonify,
    g,
    Response,
    current_app as app,
)
from flask_login import current_user
from coyote.blueprints.admin import admin_bp
from coyote.services.auth.decorators import require
from coyote.services.audit_logs.decorators import log_action
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.extensions import store, util
from datetime import datetime, timezone
from copy import deepcopy
from typing import Any
import json
from pathlib import Path


@admin_bp.route("/")
@require(min_role="manager", min_level=99)
def admin_home() -> Any:
    """
    Renders the admin home page template.
    """
    return render_template("admin_home.html")


# ==============================
# === SAMPLE MANAGEMENT PART ===
# ==============================
# This section handles the deletion of samples, including removing all traces of a sample from the system
# and redirecting to the list of all samples. It ensures proper cleanup and user redirection.
@admin_bp.route("/manage-samples", methods=["GET", "POST"])
@require("view_sample_global", min_role="developer", min_level=9999)
def all_samples() -> str | Response:
    """
    Retrieve and display a list of samples with optional search functionality.

    This function handles both GET and POST requests. For POST requests, it processes
    a search form to filter the samples based on the provided search string. The samples
    are limited to a predefined number and are filtered based on the current user's groups.

    Returns:
       str | Response: Rendered HTML template displaying the list of samples and the search form.

    Template:
        samples/all_samples.html

    Context:
        all_samples (list): A list of sample objects retrieved from the data store.
        form (SampleSearchForm): The search form for filtering samples.
    """

    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    limit_samples = None  # 300
    assays = current_user.assays
    samples = list(store.sample_handler.get_all_samples(assays, limit_samples, search_str))

    return render_template("samples/all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/samples/<sample_id>/edit", methods=["GET", "POST"])
@require("edit_sample", min_role="developer", min_level=9999)
@log_action(action_name="edit_sample", call_type="developer_call")
def edit_sample(sample_id: str) -> str | Response:
    """
    Handle the editing of a sample by its ID.

    Args:
        sample_id (str): The unique identifier of the sample to edit.

    Returns:
        Response: Renders the sample edit page or redirects based on the operation outcome.
    """

    sample_doc = store.sample_handler.get_sample(sample_id)

    sample_obj = sample_doc.pop("_id")

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_sample = json.loads(json_blob)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "red")
            return redirect(request.url)

        # Optional: Add timestamp or updated_by tracking here
        updated_sample["updated_on"] = util.common.utc_now()
        updated_sample["updated_by"] = current_user.email

        try:
            # Ensure the schema _id remains intact
            updated_sample = util.admin.restore_objectids(deepcopy(updated_sample))
            updated_sample["_id"] = sample_obj
            store.sample_handler.update_sample(sample_obj, updated_sample)
            flash("Sample updated successfully.", "green")
            return redirect(url_for("admin_bp.all_samples"))
        except Exception as e:
            print(e)
            flash(f"Error updating sample: {e}", "red")

        # Log Action
        g.audit_metadata = {"sample_id": str(sample_obj), "sample_name": sample_id}

    return render_template("samples/sample_edit.html", sample_blob=sample_doc)


@admin_bp.route("/manage-samples/<string:sample_id>/delete", methods=["GET"])
@require("delete_sample_global", min_role="developer", min_level=9999)
@log_action("delete_sample", call_type="admin_call")
def delete_sample(sample_id: str) -> Response:
    """
    Deletes a sample and all associated traces, then redirects to the list of all samples.
    Args:
        sample_id (int): The unique identifier of the sample to be deleted.
    Returns:
        werkzeug.wrappers.Response: A redirect response to the "all_samples" page.
    """
    sample_name = store.sample_handler.get_sample_name(sample_id)

    # log Action
    g.audit_metadata = {"sample": sample_name}

    util.admin.delete_all_sample_traces(sample_id)
    return redirect(url_for("admin_bp.all_samples"))


# ============================
# === USER MANAGEMENT PART ===
# ============================
# This section handles all operations related to user management,
# including listing, creating, editing, deleting, and toggling user accounts.
@admin_bp.route("/users", methods=["GET"])
@require("view_user", min_role="admin", min_level=99999)
def manage_users() -> str | Response:
    """
    Retrieve and display a list of all users.

    This function fetches all users from the user handler and renders the
    "manage_users.html" template to display the list of users.

    Returns:
        flask.Response: The rendered HTML page displaying the list of users.
    """
    users = store.user_handler.get_all_users()
    roles = store.roles_handler.get_role_colors()
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require("create_user", min_role="admin", min_level=99999)
@log_action(action_name="create_user", call_type="admin_call")
def create_user() -> Response | str:
    """
    Handles the creation of a new user.

    Fetches active user schemas, processes form data, and creates a new user.
    Includes role injection, password hashing, and group processing.

    Returns:
        - Redirects to user management page on success or errors.
        - Renders "users/user_create.html" template for GET requests.

    Flash Messages:
        - "No active user schemas found!" (red): No schemas available.
        - "User schema not found!" (red): Invalid schema.
        - "User created successfully!" (green): User created.

    Dependencies:
        - `store.schema_handler.get_schemas_by_category_type`: Fetch schemas.
        - `store.roles_handler.get_all_role_names`: Get roles.
        - `util.admin.process_form_to_config`: Process form data.
        - `util.common.hash_password`: Hash password.
        - `store.user_handler.create_user`: Save user.
    """

    # Fetch all active user schemas
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )

    if not active_schemas:
        flash("No active user schemas found!", "red")
        return redirect(url_for("admin_bp.manage_users"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("User schema not found!", "red")
        return redirect(url_for("admin_bp.manage_users"))

    # Inject Roles from the Roles collections
    available_roles = store.roles_handler.get_all_role_names()
    schema["fields"]["role"]["options"] = available_roles

    # create a mapping of role_id to role_name, permissions, deny_permissions and level
    all_roles = store.roles_handler.get_all_roles()
    role_map = {}
    for role in all_roles:
        role_map[role["_id"]] = {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }

    # Inject permissions from permissions collections
    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    # Inject assay groups from the assay_panels collections
    assay_groups: list = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups

    # get all assays for each group in a dict
    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = util.common.create_assay_group_map(assay_groups_panels)

    # Inject meta audit fields
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        # Remove all the permissions that are already there in the role and add any additional permissions to the user doc
        # This is to ensure that the user does not get duplicate permissions
        role_permissions = role_map.get(form_data["role"], {})
        form_data["permissions"] = list(
            set(form_data.get("permissions", [])) - set(role_permissions.get("permissions", []))
        )
        form_data["deny_permissions"] = list(
            set(form_data.get("deny_permissions", []))
            - set(role_permissions.get("deny_permissions", []))
        )

        user_data: dict = util.admin.process_form_to_config(form_data, schema)
        user_data["_id"] = user_data["username"]
        user_data["schema_name"] = schema["_id"]
        user_data["schema_version"] = schema["version"]
        user_data["email"] = user_data["email"].lower()
        user_data["username"] = user_data["username"].lower()

        # Hash the password
        if user_data["auth_type"] == "coyote3" and user_data["password"]:
            user_data["password"] = util.common.hash_password(user_data["password"])
        else:
            user_data["password"] = None

        # Inject version history with delta
        user_data = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(user_data),
            is_new=True,
        )

        # Log Action
        g.audit_metadata = {"user": user_data["username"]}

        store.user_handler.create_user(user_data)
        flash("User created successfully!", "green")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_create.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
        assay_group_map=assay_group_map,
        role_map=role_map,
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@require("edit_user", min_role="admin", min_level=99999)
@log_action("edit_user", call_type="admin_call")
def edit_user(user_id: str) -> Response | str:
    """
    Edit an existing user's details based on the provided user ID.

    Args:
        user_id (str): The unique identifier of the user to be edited.

    Returns:
        Response: Renders the user edit template or redirects after a successful update.
    """

    user_doc = store.user_handler.user_with_id(user_id)
    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))

    # Inject Roles from the Roles collections
    available_roles = store.roles_handler.get_all_role_names()
    schema["fields"]["role"]["options"] = available_roles

    # Inject checkbox options directly into schema field definition
    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    # create a mapping of role_id to role_name, permissions, deny_permissions and level
    all_roles = store.roles_handler.get_all_roles()
    role_map = {}
    for role in all_roles:
        role_map[role["_id"]] = {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }

    schema["fields"]["permissions"]["default"] = user_doc.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = user_doc.get("deny_permissions")

    # Inject assay groups from the assay_panels collections
    assay_groups = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups
    schema["fields"]["assay_groups"]["default"] = user_doc.get("assay_groups", [])

    # get all assays for each group in a dict
    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}

    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    schema["fields"]["assays"]["default"] = user_doc.get("assays", [])

    # --- Rewind logic ---
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(user_doc.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)
            delta = delta_blob
            user_doc["_id"] = user_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        updated_user = util.admin.process_form_to_config(form_data, schema)

        updated_user["permissions"] = list(
            set(updated_user.get("permissions", []))
            - set(role_map.get(updated_user["role"], {}).get("permissions", []))
        )
        updated_user["deny_permissions"] = list(
            set(updated_user.get("deny_permissions", []))
            - set(role_map.get(updated_user["role"], {}).get("deny_permissions", []))
        )

        # Proceed with update
        updated_user["updated_on"] = util.common.utc_now()
        updated_user["updated_by"] = current_user.email

        # Hash the password
        if updated_user["auth_type"] == "coyote3" and updated_user["password"]:
            updated_user["password"] = util.common.hash_password(updated_user["password"])
        else:
            updated_user["password"] = user_doc.get("password")

        updated_user["schema_name"] = schema["_id"]
        updated_user["schema_version"] = schema["version"]
        updated_user["version"] = user_doc.get("version", 1) + 1

        # Inject version history with delta
        updated_user = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_user,
            old_config=user_doc,
            is_new=False,
        )

        # Log Action
        g.audit_metadata = {"user": user_id}

        store.user_handler.update_user(user_id, updated_user)
        flash("User updated successfully.", "green")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_edit.html",
        schema=schema,
        user=user_doc,
        assay_group_map=assay_group_map,
        role_map=role_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/view", methods=["GET"])
@require("view_user", min_role="admin", min_level=99999)
@log_action("view_user", call_type="admin_call or user_call")
def view_user(user_id: str) -> str | Response:
    """
    Renders a read-only view of a user's profile, allowing optional version rewind to display historical user data for auditing or review purposes.

    Args:
        user_id (str): The unique identifier of the user whose profile is being viewed.

    Returns:
        str | Response: Rendered HTML template showing the user's profile, optionally at a previous version if specified.
    """
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        flash("User not found.", "red")
        return redirect(url_for("admin_bp.manage_users"))

    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        flash("Schema not found for user.", "red")
        return redirect(url_for("admin_bp.manage_users"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(user_doc.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            delta = delta_blob  # Used for UI highlighting
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)

    return render_template(
        "users/user_view.html",
        schema=schema,
        user=user_doc,
        selected_version=selected_version or user_doc.get("version"),
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/delete", methods=["GET"])
@require("delete_user", min_role="admin", min_level=99999)
@log_action(action_name="delete_user", call_type="admin_call")
def delete_user(user_id: str) -> Response:
    """
    Deletes a user by their ID and redirects to the manage users page.

    Args:
        user_id (int): The ID of the user to be deleted.
    """

    store.user_handler.delete_user(user_id)

    # Log Action
    g.audit_metadata = {"user": user_id}

    flash(f"User '{user_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/validate_username", methods=["POST"])
@require("create_user", min_role="admin", min_level=99999)
def validate_username() -> Response:
    """
    Validates if a username already exists in the system.

    Returns:
        Response: JSON response indicating whether the username exists.
    """
    username = request.json.get("username").lower()
    return jsonify({"exists": store.user_handler.user_exists(user_id=username)})


@admin_bp.route("/users/validate_email", methods=["POST"])
@require("create_user", min_role="admin", min_level=99999)
def validate_email():
    """
    Validate if an email exists in the user database.

    Returns:
        Response: A JSON response indicating whether the email exists.
    """
    email = request.json.get("email").lower()
    return jsonify({"exists": store.user_handler.user_exists(email=email)})


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@require("edit_user", min_role="admin", min_level=99999)
@log_action(action_name="edit_user", call_type="admin_call")
def toggle_user_active(user_id: str):
    """
    Toggles the active status of a user configuration by its ID.

    Args:
        user_id (str): The ID of the user configuration to toggle.

    Returns:
        Response: Redirects to the user configurations page or aborts with 404 if not found.
    """
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        return abort(404)

    new_status = not user_doc.get("is_active", False)

    # Log Action
    g.audit_metadata = {
        "user": user_id,
        "user_status": "Active" if new_status else "Inactive",
    }

    store.user_handler.toggle_user_active(user_id, new_status)
    flash(
        f"User: '{user_id}' is now {'active' if new_status else 'inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.manage_users"))


#### END OF MANAGE USERS PART ###


# ==============================
# === SCHEMA MANAGEMENT PART ===
# ==============================
# This section handles all operations related to schemas, including fetching,
# creating, editing, toggling active status, and deleting schemas.
@admin_bp.route("/schemas")
@require("view_schema", min_role="developer", min_level=9999)
def schemas() -> str:
    """
    Fetches all schemas and renders the schemas template.

    Returns:
        Response: Rendered HTML template with the list of schemas.
    """
    schemas = store.schema_handler.get_all_schemas()
    return render_template("schemas/schemas.html", schemas=schemas)


@admin_bp.route("/schemas/<schema_id>/toggle", methods=["POST", "GET"])
@require("edit_schema", min_role="developer", min_level=9999)
@log_action(action_name="edit_schema", call_type="developer_call")
def toggle_schema_active(schema_id: str) -> Response:
    """
    Toggles the active status of a schema by its ID.

    Args:
        schema_id (str): The ID of the schema to toggle.

    Returns:
        Response: A redirect to the schemas page or a 404 error if the schema is not found.
    """
    schema = store.schema_handler.get_schema(schema_id)
    if not schema:
        return abort(404)

    new_status = not schema.get("is_active", False)

    # Log Action
    g.audit_metadata = {
        "schema": schema_id,
        "schema_status": "Active" if new_status else "Inactive",
    }
    store.schema_handler.toggle_schema_active(schema_id, new_status)
    flash(
        f"Schema '{schema_id}' is now {'active' if new_status else 'inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.schemas"))


@admin_bp.route("/schemas/<schema_id>/edit", methods=["GET", "POST"])
@require("edit_schema", min_role="developer", min_level=9999)
@log_action(action_name="edit_schema", call_type="developer_call")
def edit_schema(schema_id: str) -> str | Response:
    """
    Handle the editing of a schema by its ID.

    Args:
        schema_id (str): The unique identifier of the schema to edit.

    Returns:
        Response: Renders the schema edit page or redirects based on the operation outcome.
    """

    schema_doc = store.schema_handler.get_schema(schema_id)

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_schema = json.loads(json_blob)
            errors = util.admin.validate_schema_structure(updated_schema)
            if errors:
                for err in errors:
                    flash(f"{err}", "red")
                return render_template("schemas/schema_edit.html", schema_blob=updated_schema)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "red")
            return redirect(request.url)

        # Optional: Add timestamp or updated_by tracking here
        updated_schema["updated_on"] = util.common.utc_now()
        updated_schema["updated_by"] = current_user.email
        updated_schema["version"] = schema_doc.get("version", 1) + 1

        try:
            # Ensure the schema _id remains intact
            updated_schema["_id"] = schema_doc["_id"]
            store.schema_handler.update_schema(schema_id, updated_schema)
            flash("Schema updated successfully.", "green")
            return redirect(url_for("admin_bp.schemas"))
        except Exception as e:
            flash(f"Error updating schema: {e}", "red")

        # Log Action
        g.audit_metadata = {"schema": schema_id}

    return render_template("schemas/schema_edit.html", schema_blob=schema_doc)


@admin_bp.route("/schemas/new", methods=["GET", "POST"])
@require("create_schema", min_role="developer", min_level=9999)
@log_action(action_name="create_schema", call_type="developer_call")
def create_schema() -> str | Response:
    """
    Handles the creation of a new schema.

    This function processes both GET and POST requests. On GET, it renders the schema creation template. On POST, it validates the submitted schema structure, adds metadata such as timestamps and user information, and saves the schema to the database. If validation fails, it displays error messages and re-renders the form with the provided data.

    Returns:
        str | Response: Rendered HTML template for schema creation or a redirect after successful creation.
    """

    if request.method == "POST":
        json_blob = request.form.get("json_blob")
        try:
            parsed_schema = json.loads(json_blob)  # Parse without comments, use json5 if needed

            errors = util.admin.validate_schema_structure(parsed_schema)
            if errors:
                for err in errors:
                    flash(f"{err}", "red")
                return render_template("schemas/schema_create.html", initial_blob=parsed_schema)

            # Metadata
            parsed_schema["_id"] = parsed_schema.get("schema_name")
            parsed_schema["created_on"] = util.common.utc_now()
            parsed_schema["created_by"] = current_user.email
            parsed_schema["updated_on"] = util.common.utc_now()
            parsed_schema["updated_by"] = current_user.email

            store.schema_handler.create_schema(parsed_schema)
            flash("Schema created successfully!", "green")
            return redirect(url_for("admin_bp.schemas"))

        except Exception as e:
            flash(f"Error: {e}", "red")

        # Log Action
        g.audit_metadata = {"schema": parsed_schema.get("schema_name")}

    # Load the initial schema template
    initial_blob = util.admin.load_json5_template()

    return render_template("schemas/schema_create.html", initial_blob=initial_blob)


@admin_bp.route("/schemas/<schema_id>/delete", methods=["GET"])
@require("delete_schema", min_role="admin", min_level=99999)
@log_action(action_name="delete_schema", call_type="admin_call")
def delete_schema(schema_id: str) -> Response:
    """
    Deletes a schema by its ID.

    Parameters:
        schema_id (str): The unique identifier of the schema to delete.

    Returns:
        Response: Redirects to the schemas management page if successful, or aborts with a 404 error if the schema is not found.
    """

    schema = store.schema_handler.get_schema(schema_id)
    if not schema:
        return abort(404)

    store.schema_handler.delete_schema(schema_id)

    # Log Action
    g.audit_metadata = {"schema": schema_id}
    flash(f"Schema '{schema_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.schemas"))


# ===================================
# === PERMISSIONS MANAGEMENT PART ===
# ===================================
# This section handles all operations related to permissions management,
# including listing, creating, editing, toggling active status, and deleting permissions.
@admin_bp.route("/permissions")
@require("view_permission_policy", min_role="admin", min_level=99999)
def list_permissions() -> str:
    """
    Retrieves and groups inactive permissions by category, then renders the permissions template.

    Returns:
        str: Rendered HTML template with grouped permissions.
    """
    permission_policies = store.permissions_handler.get_all_permissions(is_active=False)
    grouped = {}
    for p in permission_policies:
        grouped.setdefault(p["category"], []).append(p)
    return render_template("permissions/permissions.html", grouped_permissions=grouped)


@admin_bp.route("/permissions/new", methods=["GET", "POST"])
@require("create_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="create_permission", call_type="admin_call")
def create_permission() -> Response | str:
    """
    Creates a new permission policy using a selected schema.

    - On GET: Renders a form for entering permission details.
    - On POST: Validates and processes the form submission, then stores the new permission policy.

    Returns:
        Response | str: Rendered HTML form for creation or a redirect after successful creation.
    """

    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        flash("No active permission schemas found!", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    # Inject meta audit
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        policy = util.admin.process_form_to_config(form_data, schema)

        policy["_id"] = policy["permission_name"]
        policy["schema_name"] = schema["_id"]
        policy["schema_version"] = schema["version"]

        # Inject version history with delta
        policy = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(policy),
            is_new=True,
        )

        store.permissions_handler.create_new_policy(policy)

        # Log Action
        g.audit_metadata = {"permission": policy["_id"]}

        flash(f"Permission policy '{policy['_id']}' created.", "green")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/create_permission.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/permissions/<perm_id>/edit", methods=["GET", "POST"])
@require("edit_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="edit_permission", call_type="admin_call")
def edit_permission(perm_id: str) -> Response | str:
    """
    Handle the editing of a permission policy.

    Args:
        perm_id (str): The unique identifier of the permission policy to edit.

    Returns:
        Response: Renders the edit permission template or redirects after updating.
    """
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        return abort(404)

    schema = store.schema_handler.get_schema(permission.get("schema_name"))

    # --- Rewind logic ---
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(permission.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)
            delta = delta_blob
            permission["_id"] = perm_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        updated_permission = util.admin.process_form_to_config(form_data, schema)

        # Proceed with update
        updated_permission["updated_on"] = util.common.utc_now()
        updated_permission["updated_by"] = current_user.email
        updated_permission["version"] = permission.get("version", 1) + 1
        updated_permission["schema_name"] = schema["_id"]
        updated_permission["schema_version"] = schema["version"]

        # Inject version history with delta
        updated_permission = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_permission,
            old_config=permission,
            is_new=False,
        )

        # Log Action
        g.audit_metadata = {"permission": perm_id}

        store.permissions_handler.update_policy(perm_id, updated_permission)
        flash(f"Permission policy '{perm_id}' updated.", "green")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/edit_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/view", methods=["GET"])
@require("view_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="view_permission", call_type="admin_call")
def view_permission(perm_id: str) -> str | Response:
    """
    View a permission policy by its ID.

    Args:
        perm_id (str): The unique identifier of the permission policy to view.

    Returns:
        Response: Renders the view permission template or redirects if not found.
    """
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        return abort(404)

    schema = store.schema_handler.get_schema(permission.get("schema_name"))

    if not schema:
        flash("Schema for this permission is missing.", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(permission.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            delta = delta_blob  # Used for UI highlighting
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)

    return render_template(
        "permissions/view_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version or permission.get("version"),
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@require("edit_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="edit_permission", call_type="admin_call")
def toggle_permission_active(perm_id: str) -> Response:
    """
    Toggles the active status of a permission based on its ID.

    Args:
        perm_id (str): The unique identifier of the permission to toggle.

    Returns:
        Response: A redirect to the permissions list page if successful.
        If the permission is not found, returns a 404 error response.

    Side Effects:
        - Updates the active status of the specified permission in the store.
        - Displays a flash message indicating the new status of the permission.
    """
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        return abort(404)

    new_status = not perm.get("is_active", False)

    # Log Action
    g.audit_metadata = {
        "permission": perm_id,
        "permission_status": "Active" if new_status else "Inactive",
    }
    store.permissions_handler.toggle_policy_active(perm_id, new_status)
    flash(
        f"Permission '{perm_id}' is now {'Active' if new_status else 'Inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@require("delete_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="delete_permission", call_type="admin_call")
def delete_permission(perm_id: str) -> Response:
    """
    Deletes a permission policy by its ID.

    Args:
        perm_id (str): The unique identifier of the permission policy to be deleted.

    Returns:
        Response: A redirect to the list of permissions if the deletion is successful.
                    Returns a 404 error if the permission policy is not found.

    Side Effects:
        - Deletes the specified permission policy from the permissions handler.
        - Displays a success message using flash if the deletion is successful.
    """
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        return abort(404)

    # Log Action
    g.audit_metadata = {"permission": perm_id}

    store.permissions_handler.delete_policy(perm_id)
    flash(f"Permission policy '{perm_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.list_permissions"))


# ============================
# === ROLE MANAGEMENT PART ===
# ============================
# --- Role listing page ---
# This section handles the listing of roles, including rendering the roles page
# and providing functionality for viewing, creating, editing, toggling, and deleting roles.
@admin_bp.route("/roles")
@require("view_role", min_role="admin", min_level=99999)
def list_roles() -> str:
    """
    Retrieve and render a list of all roles.

    Returns:
        str: Rendered HTML template displaying the roles.
    """
    roles = store.roles_handler.get_all_roles()
    return render_template("roles/roles.html", roles=roles)


# --- Role creation page ---
@admin_bp.route("/roles/new", methods=["GET", "POST"])
@require("create_role", min_role="admin", min_level=99999)
@log_action(action_name="create_role", call_type="admin_call")
def create_role() -> Response | str:
    """
    Handles the creation of a new role based on a selected schema and user input.

    Retrieves active role schemas and permission policies, processes form data,
    and saves the new role configuration to the database.

    Returns:
        Redirects to the roles list page or renders the role creation template.
    """

    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="rbac_role",
        schema_category="RBAC_role",
        is_active=True,
    )

    if not active_schemas:
        flash("No active role schemas found!", "red")
        return redirect(url_for("admin_bp.list_roles"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.list_roles"))

    # Inject checkbox options directly into schema field definition
    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    # inject audit data into the schema
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        role: dict = util.admin.process_form_to_config(form_data, schema)

        role["_id"] = role.get("name")
        role["schema_name"] = schema["_id"]
        role["schema_version"] = schema["version"]

        # Inject version history with delta
        role = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(role),
            is_new=True,
        )

        # Log Action
        g.audit_metadata = {"role": role["_id"]}

        store.roles_handler.create_role(role)
        flash(f"Role '{role["_id"]}' created successfully.", "green")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/create_role.html",
        schema=schema,
        selected_schema=schema,
        schemas=active_schemas,
    )


# --- Role edit page ---
@admin_bp.route("/roles/<role_id>/edit", methods=["GET", "POST"])
@require("edit_role", min_role="admin", min_level=99999)
@log_action(action_name="edit_role", call_type="admin_call")
def edit_role(role_id: str) -> Response | str:
    """
    Handle the editing of a role by its ID.

    Retrieves the role, updates its schema with permission options, and processes
    form submissions to update the role's configuration.

    Args:
        role_id (str): The ID of the role to be edited.

    Returns:
        Response: Renders the edit role page or redirects after processing.
    """
    role = store.roles_handler.get_role(role_id)
    if not role:
        return abort(404)

    schema = store.schema_handler.get_schema(role.get("schema_name"))

    # Inject checkbox options directly into schema field definition
    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    schema["fields"]["permissions"]["default"] = role.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = role.get("deny_permissions")

    # --- Rewind logic ---
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(role.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)
            delta = delta_blob
            role["_id"] = role_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        updated_role = util.admin.process_form_to_config(form_data, schema)

        updated_role["updated_by"] = current_user.email
        updated_role["updated_on"] = util.common.utc_now()
        updated_role["schema_name"] = schema["_id"]
        updated_role["schema_version"] = schema["version"]
        updated_role["version"] = role.get("version", 1) + 1
        updated_role["_id"] = role.get("_id")

        # Inject version history with delta
        updated_role = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_role,
            old_config=role,
            is_new=False,
        )

        # Log Action
        g.audit_metadata = {"role": role_id}

        store.roles_handler.update_role(role_id, updated_role)
        flash(f"Role '{role_id}' updated successfully.", "green")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/edit_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/view", methods=["GET"])
@require("view_role", min_role="admin", min_level=99999)
@log_action(action_name="view_role", call_type="admin_call")
def view_role(role_id: str) -> Response | str:
    """
    View the details of a role by its ID.

    Args:
        role_id (str): The ID of the role to view.

    Returns:
        Response: Rendered HTML template displaying the role details.
    """
    role = store.roles_handler.get_role(role_id)
    if not role:
        return abort(404)

    schema = store.schema_handler.get_schema(role.get("schema_name"))
    if not schema:
        flash("Schema for this role is missing.", "red")
        return redirect(url_for("admin_bp.list_roles"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(role.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            delta = delta_blob  # Used for UI highlighting
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)

    return render_template(
        "roles/view_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version or role.get("version"),
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/toggle", methods=["POST", "GET"])
@require("edit_role", min_role="admin", min_level=99999)
@log_action(action_name="edit_role", call_type="admin_call")
def toggle_role_active(role_id: str) -> Response:
    """
    Toggles the active status of a role by its ID.

    Args:
        role_id (int): The ID of the role to toggle.

    Returns:
        Response: A redirect to the roles list or a 404 error if the role is not found.
    """
    role = store.roles_handler.get(role_id)
    if not role:
        return abort(404)

    new_status = not role.get("is_active", False)

    # Log Action
    g.audit_metadata = {
        "role": role_id,
        "role_status": "Active" if new_status else "Inactive",
    }
    store.roles_handler.toggle_role_active(role_id, new_status)
    flash(
        f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@require("delete_role", min_role="admin", min_level=99999)
@log_action(action_name="delete_role", call_type="admin_call")
def delete_role(role_id: str) -> Response:
    """
    Deletes a role by its ID if it exists.

    Args:
        role_id (int): The ID of the role to delete.

    Returns:
        Response: A redirect to the roles list page or a 404 error if the role is not found.
    """
    role = store.roles_handler.get_role(role_id)
    if not role:
        return abort(404)

    # Log Action
    g.audit_metadata = {"role": role_id}

    store.roles_handler.delete_role(role_id)
    flash(f"Role '{role_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.list_roles"))


# ================================================
# ===== Assay Whole Panel Creation PART =====
# ================================================
@admin_bp.route("/asp/manage", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
def manage_assay_panels():
    """
    Retrieve all assay asp and render the management template.

    Returns:
        Response: Rendered HTML template displaying all assay asp.
    """
    panels = store.asp_handler.get_all_asps()
    return render_template("asp/manage_asp.html", panels=panels)


@admin_bp.route("/asp/new", methods=["GET", "POST"])
@require("create_asp", min_role="manager", min_level=99)
@log_action(action_name="create_asp", call_type="manager_call")
def create_assay_panel():
    """
    Creates a new Assay Panel (ASP) using a schema-driven form.

    - Accepts both GET and POST requests.
    - On GET: Renders the form for creating a new panel.
    - On POST: Processes form data, parses gene lists, and inserts a versioned document into the database.
    - Handles version history for auditability.
    - Displays success or error messages as appropriate.
    """
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="asp_schema",
        schema_category="ASP",
        is_active=True,
    )

    if not active_schemas:
        flash("No active panel schemas found!", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    # inject audit data into the schema
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        covered_genes = util.admin.extract_gene_list(
            request.files.get("genes_file"), form_data.get("genes_paste", "")
        )

        # Germline Genes
        germline_genes = util.admin.extract_gene_list(
            request.files.get("germline_genes_file"),
            form_data.get("germline_genes_paste", ""),
        )

        config = util.admin.process_form_to_config(form_data, schema)
        config["_id"] = config["assay_name"]
        config["covered_genes"] = covered_genes
        config["covered_genes_count"] = len(covered_genes)
        config["germline_genes"] = germline_genes
        config["germline_genes_count"] = len(germline_genes)

        config.update(
            {
                "schema_name": schema["_id"],
                "schema_version": schema["version"],
                "version": 1,
            }
        )

        # Inject version history (initial creation marker, no delta)
        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        store.asp_handler.create_asp(config)
        g.audit_metadata = {"panel": config["_id"]}
        flash(f"Panel {config['assay_name']} created successfully!", "green")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/create_asp.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/asp/<assay_panel_id>/edit", methods=["GET", "POST"])
@require("edit_asp", min_role="manager", min_level=99)
@log_action(action_name="edit_asp", call_type="manager_call")
def edit_assay_panel(assay_panel_id: str) -> str | Response:
    """
    Edit an existing assay panel by its ID.

    Retrieves the assay panel configuration and schema, processes form submissions
    to update the panel, and handles version history and gene list updates.

    Args:
        assay_panel_id (str): The unique identifier of the assay panel to edit.

    Returns:
        str | Response: Renders the edit panel template or redirects after updating.
    """
    panel = store.asp_handler.get_asp(assay_panel_id)
    schema = store.schema_handler.get_schema(panel.get("schema_name", "ASP-Schema"))

    if not panel or not schema:
        flash("Panel or schema not found.", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    selected_version = request.args.get("version", type=int)
    delta = None

    # Apply restoration logic if an older version is requested
    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(panel, delta_blob)
            delta = delta_blob
            panel["_id"] = assay_panel_id

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        covered_genes = util.admin.extract_gene_list(
            request.files.get("genes_file"),
            form_data.get("genes_paste", ""),
        )

        if not "genes_file" in request.files and not "genes_paste" in form_data:
            covered_genes = panel.get("covered_genes", [])

        # Germline Genes
        germline_genes = util.admin.extract_gene_list(
            request.files.get("germline_genes_file"),
            form_data.get("germline_genes_paste", ""),
        )
        if not "germline_genes_file" in request.files and not "germline_genes_paste" in form_data:
            germline_genes = panel.get("germline_genes", [])

        updated = util.admin.process_form_to_config(form_data, schema)
        updated["_id"] = panel["_id"]
        updated["covered_genes"] = covered_genes
        updated["covered_genes_count"] = len(covered_genes)
        updated["germline_genes"] = germline_genes
        updated["germline_genes_count"] = len(germline_genes)
        updated["updated_by"] = current_user.email
        updated["updated_on"] = util.common.utc_now()
        updated["schema_name"] = schema["_id"]
        updated["schema_version"] = schema["version"]
        updated["version"] = panel.get("version", 1) + 1

        # Inject version history with delta
        updated = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated,
            old_config=panel,
            is_new=False,
        )

        store.asp_handler.update_asp(assay_panel_id, updated)
        g.audit_metadata = {"panel": assay_panel_id}
        flash(f"Panel '{panel['assay_name']}' updated successfully!", "green")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/edit_asp.html",
        schema=schema,
        panel=panel,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/asp/<assay_panel_id>/view", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
def view_assay_panel(assay_panel_id: str) -> Response | str:
    """
    Displays the details of an assay panel by its ID.

    Args:
        assay_panel_id (str): The unique identifier of the assay panel.

    Returns:
        Response | str: Renders the assay panel view template, optionally showing a previous version if requested.
    """
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        flash(f"Panel '{assay_panel_id}' not found!", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    schema = store.schema_handler.get_schema(panel.get("schema_name", "ASP-Schema"))
    selected_version = request.args.get("version", type=int)
    delta = None

    # If a specific version is requested, and it's not the latest
    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(panel, delta_blob)
            delta = delta_blob
            panel["_id"] = assay_panel_id

    return render_template(
        "asp/view_asp.html",
        panel=panel,
        schema=schema,
        selected_version=selected_version or panel.get("version"),
        delta=delta,
    )


@admin_bp.route("/asp/<panel_id>/print", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
@log_action(action_name="print_asp", call_type="viewer_call")
def print_assay_panel(panel_id: str) -> str | Response:
    """
    Returns a compact, printable HTML view of an assay panel, with optional support for viewing a previous version using version rewind.

    Args:
        panel_id (str): The unique identifier of the assay panel.

    Returns:
        str | Response: Rendered HTML template for the printable assay panel view, optionally showing a previous version if requested.
    """
    panel = store.asp_handler.get_asp(panel_id)
    if not panel:
        flash("Panel not found.", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    schema = store.schema_handler.get_schema(panel.get("schema_name"))
    if not schema:
        flash("Schema not found for panel.", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(deepcopy(panel), delta_blob)
            panel["_id"] = panel_id
            panel["version"] = selected_version

    return render_template(
        "asp/print_asp.html",
        schema=schema,
        config=panel,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/asp/<assay_panel_id>/toggle", methods=["POST", "GET"])
@require("edit_asp", min_role="manager", min_level=99)
@log_action(action_name="toggle_asp", call_type="manager_call")
def toggle_assay_panel_active(assay_panel_id: str) -> Response:
    """
    Toggle the active status of an assay panel by its ID.

    Args:
        assay_panel_id (str): The unique identifier of the assay panel.

    Returns:
        Response: Redirects to the manage assay asp page or aborts with 404 if panel not found.
    """
    panel = store.asp_handler.get_asp(assay_panel_id)
    if not panel:
        return abort(404)
    new_status = not panel.get("is_active", False)
    store.asp_handler.toggle_asp_active(assay_panel_id, new_status)

    # Log Action
    g.audit_metadata = {
        "panel": assay_panel_id,
        "panel_status": "Active" if new_status else "Inactive",
    }

    flash(f"Panel '{assay_panel_id}' status toggled!", "green")
    return redirect(url_for("admin_bp.manage_assay_panels"))


@admin_bp.route("/asp/<assay_panel_id>/delete", methods=["GET"])
@require("delete_asp", min_role="admin", min_level=99999)
@log_action(action_name="delete_asp", call_type="admin_call")
def delete_assay_panel(assay_panel_id: str) -> Response:
    """
    Deletes an assay panel by its ID, logs the action, flashes a message, and redirects to the panel management page.

    Args:
        assay_panel_id (str): The unique identifier of the assay panel to delete.
    """
    store.asp_handler.delete_asp(assay_panel_id)

    # Log Action
    g.audit_metadata = {"panel": assay_panel_id}

    flash(f"Panel '{assay_panel_id}' deleted!", "green")
    return redirect(url_for("admin_bp.manage_assay_panels"))


# ====================================
# === ASSAY CONFIG MANAGEMENT PART ===
# ====================================
# This section handles all operations related to assay configurations,
# including fetching, creating, editing, toggling active status, and deleting
# both DNA and RNA assay configurations.
@admin_bp.route("/aspc")
@require("view_aspc", min_role="user", min_level=9)
def assay_configs() -> str:
    """
    Fetches all assay configurations from the data store and renders them in the assay configuration management template.

    Returns:
        str: Rendered HTML template displaying all assay configurations.

    Template:
        aspc/aspc.html

    Context:
        aspc (list): List of all assay configuration objects.
    """
    assay_configs = store.aspc_handler.get_all_aspc()
    return render_template("aspc/manage_aspc.html", assay_configs=assay_configs)


@admin_bp.route("/aspc/dna/new", methods=["GET", "POST"])
@require("create_aspc", min_role="manager", min_level=99)
@log_action(action_name="create_assay_config", call_type="manager_call")
def create_dna_assay_config() -> Response | str:
    """
    Creates a new DNA assay configuration using a schema-driven form.

    - Handles both GET and POST requests.
    - On GET: Loads active DNA schemas and renders the creation form.
    - On POST: Processes form data, applies version history, and saves the new configuration.
    - Supports pre-filling metadata from selected asp and tracks audit information.
    - Displays success or error messages and redirects as appropriate.

    Returns:
        Response | str: Redirects to the assay configs page on success, or renders the creation form template.
    """
    # Load active schemas
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="asp_config", schema_category="DNA", is_active=True
    )

    if not active_schemas:
        flash("No active DNA schemas found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    # Load all active assays from panel collection
    assay_panels = store.asp_handler.get_all_asps(is_active=True)

    # Build prefill_map and collect valid assay IDs
    prefill_map = {}
    valid_assay_ids = []

    for p in assay_panels:
        if p.get("asp_category") == "DNA":
            envs = store.aspc_handler.get_available_assay_envs(
                p["_id"], schema["fields"]["environment"]["options"]
            )
            if envs:
                valid_assay_ids.append(p["_id"])
                prefill_map[p["_id"]] = {
                    "display_name": p.get("display_name"),
                    "asp_group": p.get("asp_group"),
                    "asp_category": p.get("asp_category"),
                    "platform": p.get("platform"),
                    "environment": envs,
                }

    # Inject only valid assay IDs into the schema
    schema["fields"]["assay_name"]["options"] = valid_assay_ids

    # Inject other schema values
    schema["fields"]["vep_consequences"]["options"] = list(
        app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
    )

    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        # TODO: Update the process_form_to_config to handle JSON fields
        form_data["verification_samples"] = json.loads(
            request.form.get("verification_samples", "{}")
        )

        form_data["query"] = json.loads(request.form.get("query", "{}"))

        config = util.admin.process_form_to_config(form_data, schema)

        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
                "schema_name": schema["_id"],
                "schema_version": schema["version"],
                "version": 1,
            }
        )

        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        # Check if the config already exists
        existing_config = store.aspc_handler.get_aspc_with_id(config["_id"])
        if existing_config:
            flash(
                f"Assay config '{config['assay_name']} for {config['environment']}' already exists!",
                "red",
            )
        else:
            store.aspc_handler.create_aspc(config)
            flash(
                f"{config['assay_name']} : {config['environment']} assay config created!",
                "green",
            )

        # Log Action
        g.audit_metadata = {
            "assay": config["assay_name"],
            "environment": config["environment"],
        }

        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/create_aspc.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
        prefill_map_json=json.dumps(prefill_map),
    )


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@require("create_aspc", min_role="manager", min_level=99)
@log_action(action_name="create_assay_config", call_type="manager_call")
def create_rna_assay_config() -> Response | str:
    """
    Creates a new RNA assay configuration.

    - Loads active RNA assay schemas and renders the creation form (GET).
    - Processes submitted form data, applies version history, and saves the configuration (POST).
    - Prefills metadata from selected asp and tracks audit information.
    - Displays success or error messages and redirects as appropriate.

    Returns:
        Response | str: Redirects to the assay configs page on success, or renders the creation form template.
    """
    # Fetch all active RNA assay schemas
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="asp_config", schema_category="RNA", is_active=True
    )

    if not active_schemas:
        flash("No active RNA schemas found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    # Load all active assays from panel collection
    assay_panels = store.asp_handler.get_all_asps(is_active=True)

    # Build prefill_map and collect valid assay IDs
    prefill_map = {}
    valid_assay_ids = []

    for p in assay_panels:
        if p.get("asp_category") == "RNA":
            envs = store.aspc_handler.get_available_assay_envs(
                p["_id"], schema["fields"]["environment"]["options"]
            )
            if envs:
                valid_assay_ids.append(p["_id"])
                prefill_map[p["_id"]] = {
                    "display_name": p.get("display_name"),
                    "asp_group": p.get("asp_group"),
                    "asp_category": p.get("asp_category"),
                    "platform": p.get("platform"),
                    "environment": envs,
                }

    # Inject only valid assay IDs into the schema
    schema["fields"]["assay_name"]["options"] = valid_assay_ids

    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        config = util.admin.process_form_to_config(form_data, schema)

        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
                "schema_name": schema["_id"],
                "schema_version": schema["version"],
                "version": 1,
            }
        )

        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        # Check if the config already exists
        existing_config = store.aspc_handler.get_aspc_with_id(config["_id"])
        if existing_config:
            flash(
                f"Assay config '{config['assay_name']} for {config['environment']}' already exists!",
                "red",
            )
        else:
            store.aspc_handler.create_aspc(config)
            flash(
                f"{config['assay_name']} : {config['environment']} assay config created!",
                "green",
            )

        # Log Action
        g.audit_metadata = {
            "assay": config["assay_name"],
            "environment": config["environment"],
        }

        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/create_aspc.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
        prefill_map_json=json.dumps(prefill_map),
    )


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@require("edit_aspc", min_role="manager", min_level=99)
@log_action(action_name="edit_assay_config", call_type="developer_call")
def edit_assay_config(assay_id: str) -> Response | str:
    """
    Edit an existing DNA assay configuration with version rewind support.

    This view allows users to edit a DNA assay configuration identified by its ID.
    - On GET: Loads the current configuration and schema, supports loading a previous version if requested.
    - On POST: Processes form data, updates covered and germline genes from file or text input, applies changes, and saves a new version with version history.
    - Flashes messages and redirects on success or error.

    Args:
        assay_id (str): The unique identifier of the DNA assay configuration.

    Returns:
        Response | str: Renders the edit form or redirects after a successful update.
    """

    # --- Fetch config and schema ---
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema for this assay config is missing.", "red")
        return redirect(url_for("admin_bp.aspc"))

    # --- Inject dynamic options if needed ---
    vep_terms = list(app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
    if "vep_consequences" in schema["fields"]:
        schema["fields"]["vep_consequences"]["options"] = vep_terms

    # --- Rewind logic ---
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != assay_config.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(assay_config.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = assay_config["version_history"][version_index].get("delta", {})
            assay_config = util.admin.apply_version_delta(deepcopy(assay_config), delta_blob)
            delta = delta_blob
            assay_config["_id"] = assay_id

    # --- POST: handle form update ---
    if request.method == "POST":
        form_data = {
            key: (
                request.form.getlist(key)
                if len(request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        # TODO: Update the process_form_to_config to handle JSON fields
        form_data["verification_samples"] = util.common.safe_json_load(
            request.form.get("verification_samples", "{}")
        )

        form_data["query"] = util.common.safe_json_load(request.form.get("query", "{}"))

        updated_config = util.admin.process_form_to_config(form_data, schema)

        # Enrich with metadata
        updated_config["_id"] = assay_config.get("_id")
        updated_config["updated_on"] = util.common.utc_now()
        updated_config["updated_by"] = current_user.email
        updated_config["schema_name"] = schema["_id"]
        updated_config["schema_version"] = schema["version"]
        updated_config["version"] = assay_config.get("version", 1) + 1

        # Inject version history with delta
        updated_config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_config,
            old_config=assay_config,
            is_new=False,
        )

        store.aspc_handler.update_aspc(assay_id, updated_config)
        g.audit_metadata = {
            "assay": updated_config.get("assay_name"),
            "environment": updated_config.get("environment"),
        }

        flash("Assay configuration updated successfully.", "green")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/edit_aspc.html",
        schema=schema,
        assay_config=assay_config,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/view", methods=["GET"])
@require("view_aspc", min_role="user", min_level=9)
@log_action(action_name="view_assay_config", call_type="viewer_call")
def view_assay_config(assay_id: str) -> str | Response:
    """
    Displays the details of a DNA assay configuration, supporting version rewind.

    Args:
        assay_id (str): The unique identifier of the DNA assay configuration.

    Returns:
        str | Response: Renders the assay configuration view template, optionally showing a previous version if requested.
    """
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema for this assay config is missing.", "red")
        return redirect(url_for("admin_bp.aspc"))

    # Inject dynamic options like VEP consequences
    if "vep_consequences" in schema["fields"]:
        schema["fields"]["vep_consequences"]["options"] = list(
            app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
        )

    selected_version = request.args.get("version", type=int)
    delta = None

    # Version rewind logic
    if selected_version and selected_version != assay_config.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(assay_config.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = assay_config["version_history"][version_index].get("delta", {})
            assay_config = util.admin.apply_version_delta(deepcopy(assay_config), delta_blob)
            delta = delta_blob

    return render_template(
        "aspc/view_aspc.html",
        schema=schema,
        assay_config=assay_config,
        selected_version=selected_version or assay_config.get("version"),
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/print", methods=["GET"])
@require("view_aspc", min_role="user", min_level=9)
@log_action(action_name="print_assay_config", call_type="viewer_call")
def print_assay_config(assay_id: str) -> str | Response:
    """
    Returns a compact, printable HTML view of an assay configuration, with optional support for viewing a previous version using version rewind.

    Args:
        assay_id (str): The unique identifier of the assay configuration.

    Returns:
        str | Response: Rendered HTML template for the printable assay configuration view, optionally showing a previous version if requested.
    """
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema not found for assay config.", "red")
        return redirect(url_for("admin_bp.aspc"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    if selected_version and selected_version != assay_config.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(assay_config.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = assay_config["version_history"][version_index].get("delta", {})
            assay_config = util.admin.apply_version_delta(deepcopy(assay_config), delta_blob)
            assay_config["_id"] = assay_id
            assay_config["version"] = selected_version

    return render_template(
        "aspc/print_aspc.html",
        schema=schema,
        config=assay_config,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/aspc/<assay_id>/toggle", methods=["POST", "GET"])
@require("edit_aspc", min_role="manager", min_level=99)
@log_action(action_name="edit_assay_config", call_type="developer_call")
def toggle_assay_config_active(assay_id: str) -> Response:
    """
    Toggles the active status of an assay configuration by its ID.

    Args:
        assay_id (str): The ID of the assay configuration to toggle.

    Returns:
        Response: Redirects to the assay configurations page or aborts with 404 if not found.
    """
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        return abort(404)

    new_status = not assay_config.get("is_active", False)
    # Log Action
    g.audit_metadata = {
        "assay": assay_id,
        "assay_status": "Active" if new_status else "Inactive",
    }
    store.aspc_handler.toggle_aspc_active(assay_id, new_status)
    flash(
        f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@require("delete_aspc", min_role="admin", min_level=99999)
@log_action(action_name="delete_assay_config", call_type="admin_call")
def delete_assay_config(assay_id: str) -> Response:
    """
    Deletes the assay configuration for the given assay ID.

    Args:
        assay_id (str): The ID of the assay configuration to delete.

    Returns:
        Response: Redirects to the assay configurations page or aborts with 404 if not found.
    """
    store.aspc_handler.delete_aspc(assay_id)
    # Log Action
    g.audit_metadata = {"assay": assay_id}

    flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.assay_configs"))


# ====================================
# ===== Insilico Gene Lists PART =====
# ====================================
@admin_bp.route("/genelists", methods=["GET"])
@require("view_isgl", min_role="user", min_level=9)
def manage_genelists() -> str:
    """
    Renders a template displaying all gene lists for management.

    Returns:
        Response: Rendered HTML page with all gene lists and is_public flag set to False.
    """
    genelists = store.isgl_handler.get_all_isgl()
    return render_template("isgl/manage_isgl.html", genelists=genelists, is_public=False)


# Create Genelist
@admin_bp.route("/genelists/new", methods=["GET", "POST"])
@require("create_isgl", min_role="manager", min_level=99)
@log_action(action_name="create_genelist", call_type="manager_call")
def create_genelist() -> Response | str:
    """
    Handles the creation of a new genelist via a web form.

    - Fetches active genelist schemas and injects assay/group options.
    - Processes form data and uploaded gene files or pasted genes.
    - Validates and constructs the genelist config, then saves it.
    - Provides user feedback and redirects as appropriate.
    """
    # Fetch all active GeneLists schemas
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="isgl_config",
        schema_category="ISGL",
        is_active=True,
    )

    if not active_schemas:
        flash("No active genelist schemas found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Genelist schema not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    # Inject assay groups from the assay_panels collections
    assay_groups: list = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups

    # get all assays for each group in a dict
    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}

    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    # Inject meta audit
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        # Handle genes
        genes = []
        if "genes_file" in request.files and request.files["genes_file"].filename:
            file = request.files["genes_file"]
            content = file.read().decode("utf-8")
            genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
        elif "genes_paste" in form_data and form_data["genes_paste"].strip():
            genes = [
                g.strip()
                for g in form_data["genes_paste"].replace(",", "\n").splitlines()
                if g.strip()
            ]

        genes = list(set(deepcopy(genes)))
        genes.sort()
        config = util.admin.process_form_to_config(form_data, schema)
        config["_id"] = config["name"]
        config["genes"] = genes
        config["schema_name"] = schema["_id"]
        config["schema_version"] = schema["version"]
        config["gene_count"] = len(genes)

        # Inject version history with delta
        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        store.isgl_handler.create_isgl(config)

        flash(f"Genelist {config['name']} created successfully!", "green")
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/create_isgl.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
        assay_group_map=assay_group_map,
    )


@admin_bp.route("/genelists/<genelist_id>/edit", methods=["GET", "POST"])
@require("edit_isgl", min_role="manager", min_level=99)
@log_action(action_name="edit_genelist", call_type="manager_call")
def edit_genelist(genelist_id: str) -> Response | str:
    """
    Edit an existing genelist by handling GET and POST requests.

    - On GET: Renders the edit form with current genelist data and schema options.
    - On POST: Processes form data or uploaded file to update genelist fields, tracks changes in a changelog, and saves the updated genelist.
    - Redirects and flashes messages on success or error.
    """
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        flash("Genelist not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    schema = store.schema_handler.get_schema(genelist.get("schema_name"))

    # Inject assay groups from the assay_panels collections
    assay_groups = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups
    schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])

    # get all assays for each group in a dict
    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}

    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    schema["fields"]["assays"]["default"] = genelist.get("assays", [])

    # --- Rewind logic ---
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != genelist.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(genelist.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = genelist["version_history"][version_index].get("delta", {})
            genelist = util.admin.apply_version_delta(deepcopy(genelist), delta_blob)
            delta = delta_blob
            genelist["_id"] = genelist_id

    if request.method == "POST":
        form_data = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        updated = util.admin.process_form_to_config(form_data, schema)

        genes = []
        if "genes_file" in request.files and request.files["genes_file"].filename:
            file = request.files["genes_file"]
            content = file.read().decode("utf-8")
            genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
        elif "genes_paste" in form_data and form_data["genes_paste"].strip():
            pasted = form_data["genes_paste"].replace(",", "\n")
            genes = [g.strip() for g in pasted.splitlines() if g.strip()]
        else:
            genes = genelist.get("genes", [])

        genes = list(set(deepcopy(genes)))
        genes.sort()
        updated["genes"] = genes
        updated["gene_count"] = len(genes)
        updated["updated_by"] = current_user.email
        updated["updated_on"] = util.common.utc_now()
        updated["schema_name"] = schema["_id"]
        updated["schema_version"] = schema["version"]
        updated["version"] = genelist.get("version", 1) + 1

        # Inject version history with delta
        updated = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated,
            old_config=genelist,
            is_new=False,
        )
        store.isgl_handler.update_isgl(genelist_id, updated)

        # Log Action
        g.audit_metadata = {"genelist": genelist_id}

        flash(f"Genelist '{genelist_id}' updated successfully!", "green")
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/edit_isgl.html",
        isgl=genelist,
        schema=schema,
        assay_group_map=assay_group_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/genelists/<genelist_id>/toggle", methods=["GET"])
@require("edit_isgl", min_role="manager", min_level=99)
@log_action(action_name="toggle_genelist", call_type="manager_call")
def toggle_genelist(genelist_id: str) -> Response:
    """
    Toggles the active status of a genelist by its ID.

    Args:
        genelist_id (str): The unique identifier of the genelist.

    Returns:
        Response: Redirects to the genelist management page or aborts with 404 if not found.
    """
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        return abort(404)

    new_status = not genelist.get("is_active", True)

    # Log Action
    g.audit_metadata = {
        "genelist": genelist_id,
        "genelist_status": "Active" if new_status else "Inactive",
    }

    store.isgl_handler.toggle_isgl_active(genelist_id, new_status)

    flash(
        f"Genelist: '{genelist_id}' is now {'active' if new_status else 'inactive'}.",
        "green",
    )
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/delete", methods=["GET"])
@require("delete_isgl", min_role="admin", min_level=99999)
@log_action(action_name="delete_genelist", call_type="admin_call")
def delete_genelist(genelist_id: str) -> Response:
    """
    Deletes a genelist by its ID, logs the action for auditing, flashes a success message, and redirects to the genelist management page.

    Args:
        genelist_id (str): The unique identifier of the genelist to delete.
    """
    store.isgl_handler.delete_isgl(genelist_id)

    # Log Action
    g.audit_metadata = {"genelist": genelist_id}

    flash(f"Genelist '{genelist_id}' deleted successfully!", "green")
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
@require("view_isgl", min_role="user", min_level=9)
def view_genelist(genelist_id: str) -> Response | str:
    """
    Display a genelist's details and optionally filter its genes by a selected assay.

    Shows all genes by default, or only those covered by the selected assay panel if specified.
    Redirects with an error if the genelist is not found.
    """

    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        flash(f"Genelist '{genelist_id}' not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    # Handle optional version rewind
    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != genelist.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(genelist.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = genelist["version_history"][version_index].get("delta", {})
            delta = delta_blob  # Used for UI highlighting
            genelist = util.admin.apply_version_delta(deepcopy(genelist), delta_blob)

    selected_assay = request.args.get("assay")

    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])

    filtered_genes = all_genes
    panel_germline_genes = []
    if selected_assay and selected_assay in assays:
        panel = store.asp_handler.get_asp(selected_assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        panel_germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = sorted(set(all_genes).intersection(panel_genes))

    return render_template(
        "isgl/view_isgl.html",
        genelist=genelist,
        selected_assay=selected_assay,
        filtered_genes=filtered_genes,
        is_public=False,
        selected_version=selected_version or genelist.get("version"),
        panel_germline_genes=panel_germline_genes,
        delta=delta,
    )


# ===========================
# ===== AUDIT LOGS PART =====
# ===========================
@admin_bp.route("/audit")
@require("view_audit_logs", min_role="admin", min_level=99999)
def audit():
    """
    Retrieve and display audit logs from the last 30 days.
    This function collects log files from the specified audit logs directory,
    filters them based on their modification time (only logs modified within
    the last 30 days are included), and reads their contents. The logs are
    then reversed to ensure the newest entries appear first and rendered
    in the "audit/audit.html" template.
    Returns:
        str: Rendered HTML template displaying the audit logs.
    """

    logs_path = Path(app.config["LOGS"], "audit")
    cutoff_ts = util.common.utc_now().timestamp() - (30 * 24 * 60 * 60)  # last 30 days

    log_files = sorted(
        [f for f in logs_path.glob("*.log*") if f.stat().st_mtime >= cutoff_ts],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    logs_data = []

    for file in log_files:
        with file.open() as f:
            logs_data.extend([line.strip() for line in f])

    # Reverse the logs so the newest ones appear first
    logs_data = list(reversed(logs_data))

    return render_template(
        "audit/audit.html",
        logs=logs_data,
    )
