from typing import Any
from flask import current_app as app, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from coyote.extensions import store, util
from coyote.blueprints.genepanels import genepanels_bp
from coyote.blueprints.genepanels.forms import GenePanelForm, UpdateGenePanelForm


@genepanels_bp.route("/", methods=["GET", "POST"])
@login_required
def display_genepanels() -> str:
    """
    Gene Panels
    """
    assays = store.panel_handler.get_all_panel_assays()
    assays.sort()

    if request.method == "POST":
        selected_assay = request.form.get("selected_assay")
    else:
        selected_assay = assays[0]

    genepanels = util.genepanels.format_genepanel_list(
        store.panel_handler.get_assay_all_panels(selected_assay), selected_assay
    )

    return render_template(
        "genepanels.html", assays=assays, genepanels=genepanels, selected_assay=selected_assay
    )


@genepanels_bp.route("/view_genepanel_genes/<string:genepanel_id>")
@login_required
def view_genepanel_genes(genepanel_id):
    """
    View Gene Panel Genes
    """
    genelist = store.panel_handler.get_panel_genes(genepanel_id)
    return render_template("genelist.html", genelist=genelist)


@genepanels_bp.route("/create_genelist", methods=["GET", "POST"])
@login_required
def create_genelist():
    """
    Create Gene Panel
    """
    available_assays = store.panel_handler.get_all_panel_assays()

    form = GenePanelForm()
    form.version.data = 1.0

    if form.validate_on_submit():
        data = dict(form.data)

        # Insert the new gene list into the database
        if store.panel_handler.update_genelist(data):
            flash("Gene list created successfully!", "green")
        else:
            flash("Gene list creation failed!", "red")
        return redirect(url_for("genepanels_bp.create_genelist"))

    return render_template("create_genelist.html", form=form, available_assays=available_assays)


@genepanels_bp.route("/validate_name", methods=["POST"])
@login_required
def validate_name():
    data = request.json
    name = data.get("value", "")
    genepanel_id = data.get("genepanel_id", None)
    exists = util.genepanels.validate_panel_name(name, genepanel_id)
    return jsonify({"exists": exists})


@genepanels_bp.route("/validate_displayname", methods=["POST"])
@login_required
def validate_displayname():
    data = request.json
    displayname = data.get("value", "")
    genepanel_id = data.get("genepanel_id", None)
    exists = util.genepanels.validate_panel_displayname(displayname, genepanel_id)
    return jsonify({"exists": exists})


@genepanels_bp.route("/validate_genepanel_version/<string:genepanel_id>", methods=["POST"])
@login_required
def validate_version(genepanel_id):
    data: Any | None = request.json
    form_version = data.get("value", "")
    exists = util.genepanels.validate_panel_version(genepanel_id, form_version)
    return jsonify({"exists": exists})


@genepanels_bp.route("/edit_genepanel/<string:genepanel_id>", methods=["POST", "GET"])
@login_required
def edit_genepanel(genepanel_id):
    """
    Edit Gene Panel
    """
    panel_data = store.panel_handler.get_genepanel(genepanel_id)
    latest_version = store.panel_handler.get_latest_genepanel_version(genepanel_id)
    available_assays = store.panel_handler.get_all_panel_assays()
    form = UpdateGenePanelForm()

    # Pre-fill the form fields with existing data
    if request.method == "GET":
        form.name.data = panel_data["name"]
        form.displayname.data = panel_data["displayname"]
        form.type.data = panel_data["type"]
        form.version.data = latest_version
        form.assays.data = ",".join(panel_data["assays"])  # For hidden field
        form.genes_text.data = ",".join(panel_data["genes"])  # For hidden field

    if form.validate_on_submit():
        # Process the form data and update the gene panel
        form_data = dict(form.data)
        form_data["_id"] = genepanel_id
        form_data["changelog"] = panel_data["changelog"]
        if store.panel_handler.update_genelist(form_data):
            flash("Gene list updated successfully!", "green")
        else:
            flash("Gene list update failed!", "red")
        return redirect(url_for("genepanels_bp.display_genepanels"))

    return render_template(
        "edit_genepanel.html",
        form=form,
        panel_data=panel_data,
        available_assays=available_assays,
    )


@genepanels_bp.route("/delete_genepanel/<string:genepanel_id>", methods=["POST", "GET"])
@login_required
def delete_genepanel(genepanel_id):
    if store.panel_handler.delete_genelist(genepanel_id):
        flash("Gene list deleted successfully!", "green")
    else:
        flash("Gene list deletion failed!", "red")
    return redirect(url_for("genepanels_bp.display_genepanels"))
