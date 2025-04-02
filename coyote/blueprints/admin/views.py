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


#### ASSAY CONFIGURATION PART ####
@admin_bp.route("/assay-config/dna/new", methods=["GET", "POST"])
@require_admin
def create_dna_assay_config():
    schema = store.schema_handler.get_schema("DNA-Assay-Config")

    if not schema:
        flash("DNA config schema not found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))
    
    if request.method == "POST":
        # Automatically flatten single-value fields
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
        flash(f"{config["assay_name"]} assay config created!", "green")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template("assay_configs/assay_config_create.html", schema=schema)


@admin_bp.route("/assay-config/rna/new", methods=["GET", "POST"])
@require_admin
def create_rna_assay_config():
    schema = store.schema_handler.get_schema("RNA-Assay-Config")

    if not schema:
        flash("RNA config schema not found!", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    if request.method == "POST":
        # Automatically flatten single-value fields
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

        config = util.admin.process_form_to_config(form_data, schema)

        config["_id"] = config["assay_name"]
        config["created_by"] = current_user.email
        config["created_on"] = datetime.utcnow()
        config["updated_by"] = current_user.email
        config["updated_on"] = datetime.utcnow()

        store.assay_config_handler.insert_assay_config(config)
        flash(f"{config["assay_name"]} assay config created!", "green")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template("assay_configs/assay_config_create.html", schema=schema)


@admin_bp.route("/assay-configs")
@require_admin
def assay_configs():
    assay_configs = store.assay_config_handler.get_all_assay_configs()
    return render_template("assay_configs/assay_configs.html", assay_configs=assay_configs)


@admin_bp.route("/assay-config/<assay_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_assay_config(assay_id):
    schema = store.schema_handler.get_schema("DNA-Assay-Config")  # or dynamically by type
    assay_config = store.assay_config_handler.get_assay_config(assay_id)

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
    delete an assay configuration and redirect to assay list.
    """
    config = store.assay_config_handler.get_assay_config(assay_id)
    if not config:
        return abort(404)

    store.assay_config_handler.delete_assay_config(assay_id)
    flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    return redirect(url_for("admin_bp.assay_configs"))


#### SCHEMAS PART ####
@admin_bp.route("/schemas")
@require_admin
def schemas():
    """
    List all schemas
    """
    schemas = store.schema_handler.get_all_schemas()
    return render_template("schemas/schemas.html", schemas=schemas)


@admin_bp.route("/schemas/<schema_id>/toggle", methods=["POST", "GET"])
@require_admin
def toggle_schema_active(schema_id):
    schema = store.schema_handler.get_schema(schema_id)
    if not schema:
        return abort(404)

    new_status = not schema.get("is_active", False)
    store.schema_handler.toggle_active(schema_id,  new_status)
    flash(f"Schema '{schema_id}' is now {'active' if new_status else 'inactive'}.", "green")
    return redirect(url_for("admin_bp.schemas"))



@admin_bp.route("/schemas/<schema_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_schema(schema_id):
    """
    Edit schema
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
    Create a new schema
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
    Delete a schema and redirect to schema list.
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
