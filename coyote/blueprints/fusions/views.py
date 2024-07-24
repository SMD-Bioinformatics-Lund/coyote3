"""
Coyote case variants
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory
from flask_login import current_user, login_required

from coyote.blueprints.variants.forms import FusionFilter
from wtforms import BooleanField
from wtforms.validators import Optional
from coyote.extensions import store
from coyote.blueprints.fusions import fusions_bp
from coyote.extensions import util


@fusions_bp.route("/rna/sample/<string:id>", methods=["GET", "POST"])
@login_required
def list_fusions(id):
    """
    Creates a functional elements to the fusion displays

    Parameters:
    id (str) : Sample id

    Returns:


    """
    sample = store.sample_handler.get_sample(id)

    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    smp_grp = sample["groups"][0]

    group_params = util.common.get_group_parameters(smp_grp)
    settings = util.common.get_group_defaults(group_params)
    assay = util.common.get_assay_from_sample(sample)

    app.logger.info(app.config["GROUP_CONFIGS"])  # get group config from app config instead
    app.logger.info(f"the sample has these groups {smp_grp}")
    app.logger.info(f"this is the group from collection {group_params}")

    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
    app.logger.info(f"this is the gene_lists, genelists_assay {gene_lists},{genelists_assay}")

    # Save new filter settings if submitteds
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!

    form = FusionFilter()
    print("this is the form data")
    print(form.data)
    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data == True:
            store.sample_handler.reset_sample_settings(_id, settings)
        # Change filters
        else:
            store.sample_handler.update_sample_settings(_id, form)
            ## get sample again to recieve updated forms!
            sample = store.sample_handler.get_sample_with_id(_id)
    ############################################################################
    # Check if sample has hidden comments
    has_hidden_comments = 1 if store.sample_handler.hidden_sample_comments(sample.get("_id")) else 0

    sample_settings = util.common.get_fusions_settings(sample, settings)

    # min_spanreads = sample.get("checked_cnveffects", settings["default_spanreads"])
    # min_spanpairs = sample.get("checked_cnveffects", settings["default_spanpairs"])
    # fusionlist_filter = sample.get("checked_fusionlists", settings["default_checked_fusionlists"])
    # fusioneffect_filter = sample.get("checked_fusioneffects", settings["default_checked_fusioneffects"])
    # fusioncaller_filter = sample.get("checked_fusioncallers", settings["default_checked_fusioncallers"])

    # app.logger.info(f"this is the sample {sample}")
    app.logger.info(f"this is the sample and settings  {settings}")
    # app.logger.info(f"this is the sample_settings {sample_settings}")

    # app.logger.info(f"this is the sample,{sample}")
    ## Change this to fusionquery.py
    if assay == "fusion" or assay == "fusionrna":
        fusion_query = {
            "SAMPLE_ID": str(sample["_id"]),
            "calls": {
                "$elemMatch": {
                    "spanreads": {"$gte": sample_settings["min_spanreads"]},
                    "spanpairs": {"$gte": sample_settings["min_spanreads"]},
                }
            },
        }

    fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))

    for fus_idx, fus in enumerate(fusions):
        # app.logger.info(f"these are fus, {fus_idx} {fus}")
        (fusions[fus_idx]["global_annotations"], fusions[fus_idx]["classification"]) = (
            store.fusion_handler.get_fusion_annotations(fusions[fus_idx])
        )

    # app.logger.info(f"this is the fusion and fusion query,{fusions},{fusion_query}")

    # Your logic for handling RNA samples
    return render_template("rna.html", sample=sample, form=form, fusions=fusions)
