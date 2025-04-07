"""
Coyote admin views.
"""

from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    flash,
    abort,
    jsonify,
)
from flask_login import current_user
from coyote.blueprints.admin import admin_bp
from coyote.services.auth.decorators import require_admin
from coyote.services.audit_logs.decorators import log_action
from coyote.blueprints.home.util import SampleSearchForm
from pprint import pformat
from copy import deepcopy
from coyote.extensions import store, util
from typing import Literal, Any
from datetime import datetime
import json
import json5


@admin_bp.route("/")
@require_admin
def admin_home() -> Any:
    """
    Renders the admin home page template.
    """
    return render_template("admin_home.html")


# This section handles the deletion of samples, including removing all traces
# of a sample from the system and redirecting to the list of all samples.
@admin_bp.route("/manage-samples", methods=["GET", "POST"])
@require_admin
def all_samples():
    """
    Handle the retrieval and display of samples with optional search functionality.
    """

    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    limit_samples = 50
    samples = store.sample_handler.get_all_samples(limit_samples, search_str)

    # logic + render template
    return render_template("samples/all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/manage-samples/<string:sample_id>/delete", methods=["GET"])
@require_admin
@log_action("delete_sample_route", call_type="admin_call")
def delete_sample(sample_id):
    """
    Deletes a sample and all associated traces, then redirects to the list of all samples.

    Args:
        sample_id (int): The ID of the sample to delete.

    Returns:
        Response: A redirect response to the 'all_samples' view.
    """
    util.admin.delete_all_sample_traces(sample_id)
    return redirect(url_for("admin_bp.all_samples"))


#### END OF SAMPLE DELETION PART ###


# This section handles all operations related to user management,
# including listing, creating, editing, deleting, and toggling user accounts.
@admin_bp.route("/users", methods=["GET"])
@require_admin
def manage_users():
    """
    Fetches all users from the user handler and renders the manage users template.

    Returns:
        str: Rendered HTML template for managing users.
    """
    users = store.user_handler.get_all_users()
    return render_template("users/manage_users.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require_admin
def create_user():
    """
    Handles the creation of a new user based on a selected schema.
    Fetches active user schemas, processes form data, and stores the new user.
    """
    # Fetch all active user schemas
    active_schemas = store.schema_handler.get_schemas_by_filter(
        schema_type="user", schema_category="user_management", is_active=True
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

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        user_data = util.admin.process_form_to_config(form_data, schema)

        user_data["_id"] = user_data["username"]
        user_data["schema_name"] = schema["_id"]
        user_data["schema_version"] = schema["version"]
        user_data["created_by"] = current_user.email
        user_data["created_on"] = datetime.utcnow()
        user_data["updated_by"] = current_user.email
        user_data["updated_on"] = datetime.utcnow()
        user_data["email"] = user_data["email"].lower()
        user_data["username"] = user_data["username"].lower()

        # Hash the password
        if "password" in user_data:
            user_data["password"] = util.profile.hash_password(user_data["password"])

        store.user_handler.create_user(user_data)
        flash("User created successfully!", "green")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_create.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_user(user_id):
    """
    Edit an existing user's details based on the provided user ID.

    Args:
        user_id (str): The unique identifier of the user to be edited.

    Returns:
        Response: Renders the user edit template or redirects after a successful update.
    """
    user_doc = store.user_handler.user_with_id(user_id)
    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))

    if "groups" in user_doc:
        user_doc["groups"] = {group: True for group in user_doc["groups"]}

    if request.method == "POST":
        form_data = request.form.to_dict()

        updated_user = util.admin.process_form_to_config(form_data, schema)

        # Proceed with update
        updated_user["updated_on"] = datetime.utcnow()
        updated_user["updated_by"] = current_user.email

        if "password" in updated_user:
            updated_user["password"] = util.profile.hash_password(updated_user["password"])
        else:
            updated_user["password"] = user_doc["password"]

        updated_user["email"] = updated_user["email"].lower()
        updated_user["username"] = updated_user["username"].lower()
        updated_user["groups"] = list(updated_user.get("groups", {}).keys())
        updated_user["schema_name"] = schema["_id"]
        updated_user["schema_version"] = schema["version"]

        store.user_handler.update_user(user_id, updated_user)
        flash("User updated successfully.", "green")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template("users/user_edit.html", schema=schema, config=user_doc)


@admin_bp.route("/users/<user_id>/delete", methods=["GET"])
@require_admin
def delete_user(user_id):
    """
    Deletes a user account by the given user ID and redirects to the manage users page.
    """
    store.user_handler.delete_user(user_id)
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/validate_username", methods=["POST"])
@require_admin
def validate_username():
    """
    Validates if a username already exists in the system.

    Returns:
        Response: JSON response indicating whether the username exists.
    """
    username = request.json.get("username").lower()
    return jsonify({"exists": store.user_handler.user_exists(user_id=username)})


@admin_bp.route("/users/validate_email", methods=["POST"])
@require_admin
def validate_email():
    """
    Validate if an email exists in the user database.

    Returns:
        Response: A JSON response indicating whether the email exists.
    """
    email = request.json.get("email").lower()
    return jsonify({"exists": store.user_handler.user_exists(email=email)})


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_user_active(user_id):
    """
    Toggles the active status of an user configuration by its ID.

    Args:
        user_id (str): The ID of the user configuration to toggle.

    Returns:
        Response: Redirects to the user configurations page or aborts with 404 if not found.
    """
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        return abort(404)

    new_status = not user_doc.get("is_active", False)
    store.user_handler.toggle_active(user_id, new_status)
    flash(f"User: '{user_id}' is now {'active' if new_status else 'inactive'}.", "green")
    return redirect(url_for("admin_bp.manage_users"))


#### END OF MANAGE USERS PART ###


# This section handles all operations related to assay configurations,
# including fetching, creating, editing, toggling active status, and deleting
# both DNA and RNA assay configurations.
@admin_bp.route("/assay-configs")
@require_admin
def assay_configs():
    """
    Fetch and render all assay configurations.
    Returns:
        Response: Rendered HTML template displaying assay configurations.
    """
    assay_configs = store.assay_config_handler.get_all_assay_configs()
    return render_template("assay_configs/assay_configs.html", assay_configs=assay_configs)


@admin_bp.route("/assay-configs/<assay_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_assay_config_active(assay_id):
    """
    Toggles the active status of an assay configuration by its ID.

    Args:
        assay_id (str): The ID of the assay configuration to toggle.

    Returns:
        Response: Redirects to the assay configurations page or aborts with 404 if not found.
    """
    assay_config = store.assay_config_handler.get_assay_config(assay_id)
    if not assay_config:
        return abort(404)

    new_status = not assay_config.get("is_active", False)
    store.assay_config_handler.toggle_active(assay_id, new_status)
    flash(f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}.", "green")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/assay-config/<assay_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_assay_config(assay_id):
    """
    Handle the editing of an assay configuration.

    Args:
        assay_id (str): The unique identifier of the assay configuration to edit.

    Returns:
        Response: Renders the edit template or redirects based on the request method and outcome.
    """
    assay_config = store.assay_config_handler.get_assay_config(assay_id)
    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))

    if request.method == "POST":
        form_data = request.form.to_dict()

        try:
            updated_config = util.admin.process_form_to_config(form_data, schema)

            current_clean = util.admin.clean_config_for_comparison(assay_config)
            incoming_clean = util.admin.clean_config_for_comparison(updated_config)

            if current_clean == incoming_clean:
                flash("No changes detected. Configuration was not updated.", "yellow")
                return redirect(url_for("admin_bp.assay_configs"))

            # Proceed with update
            updated_config["updated_on"] = datetime.utcnow()
            updated_config["updated_by"] = current_user.email
            updated_config["version"] = assay_config.get("version", 1) + 1

            store.assay_config_handler.update_assay_config(assay_id, updated_config)
            flash("Assay configuration updated successfully.", "green")
            return redirect(url_for("admin_bp.assay_configs"))

        except Exception as e:
            flash(f"Error: {e}", "red")

    return render_template(
        "assay_configs/assay_config_edit.html", schema=schema, config=assay_config
    )


@admin_bp.route("/assay/<assay_id>/delete", methods=["GET"])
@require_admin
def delete_assay_config(assay_id):
    """
    Deletes the assay configuration for the given assay ID.

    Args:
        assay_id (str): The ID of the assay configuration to delete.

    Returns:
        Response: Redirects to the assay configurations page or aborts with 404 if not found.
    """
    config = store.assay_config_handler.get_assay_config(assay_id)
    if not config:
        return abort(404)

    store.assay_config_handler.delete_assay_config(assay_id)
    flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/assay-config/dna/new", methods=["GET", "POST"])
@require_admin
def create_dna_assay_config():
    """
    Handles the creation of a DNA assay configuration. Fetches active DNA schemas,
    processes form data, and saves the configuration to the database.
    """
    # Fetch all active DNA assay schemas
    active_schemas = store.schema_handler.get_schemas_by_filter(
        schema_type="assay_config", schema_category="DNA", is_active=True
    )

    if not active_schemas:
        flash("No active DNA schemas found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        config = util.admin.process_form_to_config(form_data, schema)

        config["_id"] = config["assay_name"]
        config["schema_name"] = schema["_id"]
        config["schema_version"] = schema["version"]
        config["created_by"] = current_user.email
        config["created_on"] = datetime.utcnow()
        config["updated_by"] = current_user.email
        config["updated_on"] = datetime.utcnow()

        store.assay_config_handler.insert_assay_config(config)
        flash(f"{config['assay_name']} assay config created!", "green")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "assay_configs/assay_config_create.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/assay-config/rna/new", methods=["GET", "POST"])
@require_admin
def create_rna_assay_config():
    """
    Handles the creation of RNA assay configurations. Fetches active RNA schemas,
    processes form data, and saves the configuration to the database.
    """
    # Fetch all active RNA assay schemas
    active_schemas = store.schema_handler.get_schemas_by_filter(
        schema_type="assay_config", schema_category="RNA", is_active=True
    )

    if not active_schemas:
        flash("No active RNA schemas found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    # Determine which schema to use
    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        config = util.admin.process_form_to_config(form_data, schema)

        config["_id"] = config["assay_name"]
        config["schema_name"] = schema["_id"]
        config["schema_version"] = schema["version"]
        config["created_by"] = current_user.email
        config["created_on"] = datetime.utcnow()
        config["updated_by"] = current_user.email
        config["updated_on"] = datetime.utcnow()

        store.assay_config_handler.insert_assay_config(config)
        flash(f"{config['assay_name']} assay config created!", "green")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "assay_configs/assay_config_create.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


# This section handles all operations related to schemas, including fetching,
# creating, editing, toggling active status, and deleting schemas.
@admin_bp.route("/schemas")
@require_admin
def schemas():
    """
    Fetches all schemas and renders the schemas template.

    Returns:
        Response: Rendered HTML template with the list of schemas.
    """
    schemas = store.schema_handler.get_all_schemas()
    return render_template("schemas/schemas.html", schemas=schemas)


@admin_bp.route("/schemas/<schema_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_schema_active(schema_id):
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
    store.schema_handler.toggle_active(schema_id, new_status)
    flash(f"Schema '{schema_id}' is now {'active' if new_status else 'inactive'}.", "green")
    return redirect(url_for("admin_bp.schemas"))


@admin_bp.route("/schemas/<schema_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_schema(schema_id):
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
        updated_schema["updated_on"] = datetime.utcnow()
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

    return render_template("schemas/schema_edit.html", schema_blob=schema_doc)


@admin_bp.route("/schemas/new", methods=["GET", "POST"])
@require_admin
def create_schema():
    """
    Handles the creation of a new schema. Validates the schema structure,
    stores metadata, and saves it to the database. Renders the schema creation
    template on GET or in case of errors.
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
            parsed_schema["created_on"] = datetime.utcnow()
            parsed_schema["created_by"] = current_user.email
            parsed_schema["updated_on"] = datetime.utcnow()
            parsed_schema["updated_by"] = current_user.email

            store.schema_handler.insert_schema(parsed_schema)
            flash("Schema created successfully!", "green")
            return redirect(url_for("admin_bp.schemas"))

        except Exception as e:
            flash(f"Error: {e}", "red")

    # Load the initial schema template
    initial_blob = util.admin.load_json5_template()

    return render_template("schemas/schema_create.html", initial_blob=initial_blob)


@admin_bp.route("/schemas/<schema_id>/delete", methods=["GET"])
@require_admin
def delete_schema(schema_id):
    """
    Deletes a schema by its ID.

    Args:
        schema_id (str): The ID of the schema to delete.

    Returns:
        Response: Redirects to the schemas page or aborts with a 404 if the schema is not found.
    """

    schema = store.schema_handler.get_schema(schema_id)
    if not schema:
        return abort(404)

    store.schema_handler.delete_schema(schema_id)
    flash(f"Schema '{schema_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.schemas"))


#### END OF SCHEMA MANAGEMENT PART ###


#### Permission Management ####
@admin_bp.route("/permissions")
@require_admin
def list_permissions():
    """
    Retrieves and groups inactive permissions by category, then renders the permissions template.

    Returns:
        str: Rendered HTML template with grouped permissions.
    """
    policies = store.permissions_handler.get_all(is_active=False)
    categories = store.permissions_handler.get_categories()
    grouped = {}
    for p in policies:
        grouped.setdefault(p["category"], []).append(p)
    return render_template("access/permissions.html", grouped_permissions=grouped)


@admin_bp.route("/permissions/new", methods=["GET", "POST"])
@require_admin
def create_permission():
    """
    Handles the creation of a new permission policy based on a selected schema.
    Renders a form for input and processes the form submission to store the policy.
    """

    active_schemas = store.schema_handler.get_schemas_by_filter(
        schema_type="admin_config", schema_category="RBAC_permissions", is_active=True
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

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        policy = util.admin.process_form_to_config(form_data, schema)

        policy["permission_name"] = policy["_id"]
        policy["created_by"] = current_user.email
        policy["updated_by"] = current_user.email
        policy["created_on"] = datetime.utcnow().isoformat()
        policy["updated_on"] = datetime.utcnow().isoformat()
        policy["schema_name"] = schema["_id"]
        policy["schema_version"] = schema["version"]

        store.permissions_handler.insert_permission(policy)
        flash(f"Permission policy '{policy['_id']}' created.", "green")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "access/create_permission.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/permissions/<perm_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_permission(perm_id):
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

    if request.method == "POST":
        form_data = request.form.to_dict(flat=True)

        updated_permission = util.admin.process_form_to_config(form_data, schema)

        current_clean = util.admin.clean_config_for_comparison(permission)
        incoming_clean = util.admin.clean_config_for_comparison(updated_permission)
        if current_clean == incoming_clean:
            flash("No changes detected. Permission policy was not updated.", "yellow")
            return redirect(url_for("admin_bp.list_permissions"))

        # Proceed with update
        updated_permission["updated_on"] = datetime.utcnow()
        updated_permission["updated_by"] = current_user.email
        updated_permission["version"] = permission.get("version", 1) + 1

        store.permissions_handler.update_policy(perm_id, updated_permission)
        flash(f"Permission policy '{perm_id}' updated.", "green")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template("access/edit_permission.html", schema=schema, config=permission)


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_permission_active(perm_id):
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
    store.permissions_handler.toggle_active(perm_id, new_status)
    flash(f"Permission '{perm_id}' is now {'Active' if new_status else 'Inactive'}.", "green")
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@require_admin
def delete_permission(perm_id):
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

    store.permissions_handler.delete_permission(perm_id)
    flash(f"Permission policy '{perm_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.list_permissions"))


# --- Role listing page ---
@admin_bp.route("/roles")
@require_admin
def list_roles():
    """
    Retrieve and render a list of all roles.

    Returns:
        str: Rendered HTML template displaying the roles.
    """
    roles = store.roles_handler.get_all_roles()
    return render_template("access/roles.html", roles=roles)


# --- Role creation page ---
@admin_bp.route("/roles/new", methods=["GET", "POST"])
@require_admin
def create_role():
    """
    Handles the creation of a new role based on a selected schema and user input.

    Retrieves active role schemas and permission policies, processes form data,
    and saves the new role configuration to the database.

    Returns:
        Redirects to the roles list page or renders the role creation template.
    """

    active_schemas = store.schema_handler.get_schemas_by_filter(
        schema_type="admin_config", schema_category="access_control", is_active=True
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

    permission_policies = store.permissions_handler.get_all(is_active=True)

    # Inject checkbox options directly into schema field definition
    if "permissions" in schema["fields"]:
        schema["fields"]["permissions"]["options"] = [
            {
                "value": p["_id"],
                "label": p.get("label", p["_id"]),
                "category": p.get("category", "Uncategorized"),
            }
            for p in permission_policies
        ]

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        permissions = request.form.getlist("permissions") or []

        policy = util.admin.process_form_to_config(form_data, schema)

        policy["name"] = form_data.get("_id")

        policy["schema_name"] = schema["_id"]
        policy["schema_version"] = schema["version"]
        policy["permissions"] = permissions
        policy["created_by"] = current_user.email
        policy["created_on"] = datetime.utcnow().isoformat()
        policy["updated_by"] = current_user.email
        policy["updated_on"] = datetime.utcnow().isoformat()

        store.roles_handler.save_role(policy)
        flash(f"Role '{policy["_id"]}' created successfully.", "green")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "access/create_role.html",
        schema=schema,
        selected_schema=schema,
        schemas=active_schemas,
    )


# --- Role edit page ---
@admin_bp.route("/roles/<role_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_role(role_id):
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
    permission_policies = store.permissions_handler.get_all(is_active=True)

    # Inject checkbox options directly into schema field definition
    if "permissions" in schema["fields"]:
        schema["fields"]["permissions"]["options"] = [
            {
                "value": p["_id"],
                "label": p.get("label", p["_id"]),
                "category": p.get("category", "Uncategorized"),
            }
            for p in permission_policies
        ]

    if request.method == "POST":
        form_data = request.form.to_dict(flat=True)
        permissions = request.form.getlist("permissions") or []

        updated_role = util.admin.process_form_to_config(form_data, schema)
        current_clean = util.admin.clean_config_for_comparison(role)
        incoming_clean = util.admin.clean_config_for_comparison(updated_role)
        if current_clean == incoming_clean:
            flash("No changes detected. Role was not updated.", "yellow")
            return redirect(url_for("admin_bp.list_roles"))

        updated_role["permissions"] = permissions
        updated_role["updated_by"] = current_user.email
        updated_role["updated_on"] = datetime.utcnow().isoformat()
        updated_role["version"] = role.get("version", 1) + 1

        store.roles_handler.update_role(role_id, updated_role)
        flash(f"Role '{role_id}' updated successfully.", "green")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template("access/edit_role.html", schema=schema, config=role)


@admin_bp.route("/roles/<role_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_role_active(role_id):
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
    store.roles_handler.toggle_active(role_id, new_status)
    flash(f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.", "green")
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@require_admin
def delete_role(role_id):
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

    store.roles_handler.delete_role(role_id)
    flash(f"Role '{role_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.list_roles"))


# --- Permission policy schema from DB ---
@admin_bp.route("/schemas/permission_policies")
@require_admin
def get_permission_policy_schema():
    """
    Retrieve the schema for permission policies from the schema handler.

    Returns:
        dict: The permission policies schema, or an empty dictionary if not found.
    """
    return store.schema_handler.get_schema("permission_policies") or {}


# --- Role schema from DB ---
@admin_bp.route("/schemas/roles")
@require_admin
def get_roles_schema():
    """
    Retrieve the schema for roles from the schema handler.

    Returns:
        dict: The roles schema, or an empty dictionary if not found.
    """
    return store.schema_handler.get_schema("roles") or {}


@admin_bp.route("/audit")
@require_admin
def audit():
    """
    Audit trail
    """
    # logic + render template
    return render_template("audit.html")
