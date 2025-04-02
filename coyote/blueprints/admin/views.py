"""
Coyote admin views.
"""

from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
    abort,
    send_file,
    jsonify,
)
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from coyote.blueprints.admin import admin_bp
from coyote.services.auth.decorators import require_admin
from coyote.blueprints.home.util import SampleSearchForm
from coyote.blueprints.admin.forms import (
    UserForm,
    UserUpdateForm,
)
from pydantic import ValidationError
from pprint import pformat
from copy import deepcopy
from coyote.extensions import store, util
from typing import Literal, Any
from datetime import datetime
import os
import io
import json
import json5


@admin_bp.route("/")
@require_admin
def admin_home():
    return render_template("admin_home.html")


#### SAMPLE DELETION PART ####
@admin_bp.route("/all-samples", methods=["GET", "POST"])
@require_admin
def all_samples():

    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    limit_samples = 50
    samples = store.sample_handler.get_all_samples(limit_samples, search_str)

    # logic + render template
    return render_template("all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/sample/<string:sample_id>/delete", methods=["POST"])
@require_admin
def delete_sample(sample_id):

    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)

    sample_oid = sample["_id"]

    # delete from all collections
    # delete from variant collection
    store.variant_handler.delete_sample_variants(sample_oid)

    # delete from cnv collection
    store.cnv_handler.delete_sample_cnvs(sample_oid)

    # delete from coverage collection
    store.coverage_handler.delete_sample_coverage(sample_oid)

    # delete from coverage2 collection
    store.coverage2_handler.delete_sample_coverage(sample_oid)

    # delete from transloc collection
    store.transloc_handler.delete_sample_translocs(sample_oid)

    # delete from fusions collection
    store.fusion_handler.delete_sample_fusions(sample_oid)

    # delete from biomarker collection
    store.biomarker_handler.deleter_sample_biomarkers(sample_oid)

    # finally delete from sample collection
    store.sample_handler.delete_sample(sample_oid)

    flash(
        f"Sample {sample['name']} deleted successfully",
        "green",
    )

    # logic + render template
    return redirect(url_for("admin_bp.all_samples"))


#### END OF SAMPLE DELETION PART ###


#### MANAGE USERS PART ####
@admin_bp.route("/users", methods=["GET"])
@require_admin
def manage_users():
    """
    Admin view to list and manage all users.
    """
    users = store.user_handler.get_all_users()
    return render_template("users/manage_users.html", users=users)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@require_admin
def create_user():
    """
    Admin creates a new user account.
    """
    form = UserForm()
    if form.validate_on_submit():
        user_data = {
            "_id": form.username.data,
            "fullname": form.fullname.data,
            "email": form.email.data,
            "job_title": form.job_title.data,
            "groups": [g.strip() for g in form.groups.data.split(",") if g.strip()],
            "role": form.role.data,
            "password": util.profile.hash_password(form.password.data),
            "created": datetime.utcnow(),
            "updated": datetime.utcnow(),
            "is_active": form.is_active.data,
        }
        store.user_handler.create_user(user_data)
        return redirect(url_for("admin_bp.manage_users"))

    return render_template("users/create_user.html", form=form)


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@require_admin
def update_user(user_id):
    """
    Admin edits an existing user account.
    """
    user = store.user_handler.user_with_id(user_id)
    print("🛠 User data:", pformat(user))
    form = UserUpdateForm(data=user)
    form.username.data = user["_id"]

    if form.validate_on_submit():
        updated_user = {
            "_id": form.username.data,
            "fullname": form.fullname.data,
            "email": form.email.data,
            "job_title": form.job_title.data,
            "groups": [g.strip() for g in form.groups.data.split(",") if g.strip()],
            "role": form.role.data,
            "is_active": form.is_active.data,
            "updated": datetime.utcnow(),
        }

        if form.password.data:
            updated_user["password"] = util.profile.hash_password(form.password.data)

        store.user_handler.update_user(updated_user)
        return redirect(url_for("admin_bp.manage_users"))

    return render_template("users/update_user.html", form=form, user=user)


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@require_admin
def delete_user(user_id):
    """
    Admin deletes a user account.
    """
    store.user_handler.delete_user(user_id)
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/validate_username", methods=["POST"])
@require_admin
def validate_username():
    """
    Check if username already exists.
    """
    username = request.json.get("username")
    return jsonify({"exists": store.user_handler.user_exists(user_id=username)})


@admin_bp.route("/users/validate_email", methods=["POST"])
@require_admin
def validate_email():
    """
    Check if email already exists.
    """
    email = request.json.get("email")
    return jsonify({"exists": store.user_handler.user_exists(email=email)})


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


@admin_bp.route("/audit")
@require_admin
def audit():
    """
    Audit trail
    """
    # logic + render template
    return render_template("audit.html")
