"""
Coyote case variants
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
)
from flask_login import current_user, login_required
from pprint import pformat
from copy import deepcopy
from werkzeug import Response
from wtforms import BooleanField
from coyote.extensions import store, util
from coyote.blueprints.dna import dna_bp, varqueries_notbad, filters
from coyote.blueprints.home import home_bp
from coyote.blueprints.dna.varqueries import build_query
from coyote.blueprints.dna.cnvqueries import build_cnv_query
from coyote.blueprints.dna.forms import DNAFilterForm, create_assay_group_form
from coyote.errors.exceptions import AppError
from typing import Literal, Any
from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from flask_weasyprint import HTML, render_pdf
from coyote.util.decorators.access import require_sample_group_access
from coyote.services.auth.decorators import require
from PIL import Image
import os
import io


@dna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
@login_required
@require_sample_group_access("sample_id")
def list_variants(sample_id):
    """
    List variants for a given sample.
    """
    # Find sample data by name
    sample = store.sample_handler.get_sample(sample_id)  # sample_id = name

    # Get sample data by id if name is none
    if sample is None:
        sample = store.sample_handler.get_sample_with_id(
            sample_id
        )  # sample_id = id

    sample_has_filters = sample.get("filters", None)

    # Get case and control samples
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    ## Check the length of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
    sample_assay = util.common.select_one_sample_group(sample.get("groups"))

    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.home_screen"))

    # New way to retrive assay group config from db assay configs
    assay_config = store.assay_config_handler.get_assay_config_filtered(
        sample_assay
    )

    if not assay_config:
        flash(f"No config found for the the assay {sample_assay}", "red")
        return redirect(url_for("home_bp.home_screen"))

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get(
        "assay_group", "unknown"
    )  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.
    dna_sections = list(assay_config.get("DNA", {}).keys())
    display_sections_data = {}
    summary_sections_data = {}
    app.logger.debug(
        f"Assay group: {assay_group} - DNA config: {pformat(dna_sections)}"
    )
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.panel_handler.get_panel(panel_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = (
        store.insilico_genelist_handler.get_genelists_by_panel(sample_assay)
    )
    all_panel_genelist_names = util.common.get_assay_genelist_names(
        insilico_panel_genelists
    )

    # Adding the default gene lists to the assay_config, if use_diagnosis_genelist is set to true
    if (
        assay_config["FILTERS"].get("use_diagnosis_genelist", False)
        and subpanel
    ):
        assay_default_config_genelist_ids = (
            store.insilico_genelist_handler.get_genelists_ids(
                sample_assay, subpanel, "genelist"
            )
        )
        assay_config["FILTERS"]["genelists"].extend(
            assay_default_config_genelist_ids
        )

    # Get filter settings from the sample and merge with assay config if sample does not have values
    sample = util.common.merge_sample_settings_with_assay_config(
        sample, assay_config
    )
    sample_filters = deepcopy(sample.get("filters", {}))

    # Update the sample filters with the default values from the assay config if the sample is new and does not have any filters set
    if not sample_has_filters:
        store.sample_handler.reset_sample_settings(
            sample["_id"], assay_config.get("FILTERS")
        )

    # Inherit DNAFilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(DNAFilterForm, f"genelist_{gene_list}", BooleanField())

    form = DNAFilterForm()

    ###########################################################################
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        app.logger.debug(f"form data: {form.data}")
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            app.logger.debug("Resetting filters to default settings")
            store.sample_handler.reset_sample_settings(
                _id, assay_config.get("FILTERS")
            )
        else:
            store.sample_handler.update_sample_settings(_id, form)

        ## get sample again to recieve updated forms!
        sample = store.sample_handler.get_sample_with_id(_id)
        sample_filters = deepcopy(sample.get("filters"))

    ############################################################################

    # Check if the sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(
        sample.get("_id")
    )

    # sample filters, either set, or default
    cnv_effects = sample_filters.get("cnveffects", [])
    checked_genelists = sample_filters.get("genelists", [])

    # Get the genelists for the sample panel checked genelists from the filters
    checked_genelists_genes_dict: list[dict] = (
        store.insilico_genelist_handler.get_genelist_docs_by_ids(
            checked_genelists
        )
    )
    genes_covered_in_panel: list[dict] = (
        util.common.get_genes_covered_in_panel(
            checked_genelists_genes_dict, assay_panel_doc
        )
    )

    filter_conseq = util.dna.get_filter_conseq_terms(
        sample_filters.get("vep_consequences", [])
    )

    # Create a unique list of genes from the selected genelists which are currently active in the panel
    filter_genes = util.common.create_filter_genelist(genes_covered_in_panel)
    filter_cnveffects = util.dna.create_cnveffectlist(cnv_effects)

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{
                f"vep_{k}": True
                for k in sample_filters.get("vep_consequences", [])
            },
            **{
                f"cnveffect_{k}": True
                for k in sample_filters.get("cnveffects", [])
            },
            **{f"genelist_{k}": True for k in checked_genelists},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    # this is in config, but needs to be tested (2024-05-14) with a HD-sample of relevant name
    disp_pos = []
    if "verification_samples" in assay_config:
        print("Verification is assay")
        if sample["name"] in assay_config["verification_samples"]:
            print("Sample is verification sample")
            disp_pos = assay_config["verification_samples"][sample["name"]]

    ## SNV FILTRATION STARTS HERE ! ##
    ##################################
    ## The query should really be constructed according to some configured rules for a specific assay
    query = build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": sample_filters["max_freq"],
            "min_freq": sample_filters["min_freq"],
            "max_control_freq": sample_filters["max_control_freq"],
            "min_depth": sample_filters["min_depth"],
            "min_alt_reads": sample_filters["min_alt_reads"],
            "max_popfreq": sample_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
        },
    )

    variants_iter = store.variant_handler.get_case_variants(query)
    variants = list(variants_iter)

    # Add blacklist data
    variants = store.blacklist_handler.add_blacklist_data(
        variants, assay_group
    )

    # Add global annotations for the variants
    variants, tiered_variants = util.dna.add_global_annotations(variants, assay_group, subpanel)
    summary_sections_data['snvs'] = tiered_variants
    # Filter by population frequency, the same as in the query
    # variants = util.dna.popfreq_filter(variants, float(sample_filters["max_popfreq"]))

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    display_sections_data["snvs"] = deepcopy(variants)

    ### SNV FILTRATION ENDS HERE ###

    ## GET Other sections CNVs TRANSLOCS and OTHER BIOMARKERS ##
    if "CNV" in dna_sections:
        cnv_query = build_cnv_query(
            str(sample["_id"]),
            filters={**sample_filters, "filter_genes": filter_genes},
        )
        cnvs = store.cnv_handler.get_sample_cnvs(cnv_query)
        if filter_cnveffects:
            cnvs = util.dna.cnvtype_variant(cnvs, filter_cnveffects)
        cnvs = util.dna.cnv_organizegenes(cnvs)

        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = list(
            store.cnv_handler.get_interesting_sample_cnvs(
                sample_id=str(sample["_id"])
            )
        )

    if "BIOMARKER" in dna_sections:
        display_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
        )
        summary_sections_data['biomarkers'] = display_sections_data["biomarkers"]

    if "TRANSLOCATION" in dna_sections:
        display_sections_data["translocs"] = (
            store.transloc_handler.get_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )
        summary_sections_data["translocs"] = (
            store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )
    if "FUSION" in dna_sections:
        display_sections_data["fusions"] = []


    #################################################

    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith((".png", ".jpg", ".jpeg")):
            sample["cnvprofile"] = sample["cnv"]

    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = store.coverage_handler.get_sample_coverage(sample["name"])
    low_cov_chrs = list(set([x["chr"] for x in low_cov]))

    ## add cosmic to lowcov regions. Too many lowcov regions and this becomes very slow
    # this could maybe be something else than cosmic? config important regions?
    cosmic_ids = store.cosmic_handler.get_cosmic_ids(chr=low_cov_chrs)

    if assay_group != "solid":
        low_cov = util.dna.filter_low_coverage_with_cosmic(low_cov, cosmic_ids)

    display_sections_data["low_cov"] = deepcopy(low_cov)

    # Get bams
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(
        sample.get("vep", 103)
    )

    ######## TODO: AI TEXT ##############
    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    ai_text = util.bpcommon.generate_summary_text( assay_group, summary_sections_data, filter_genes, checked_genelists )


    return render_template(
        "list_variants_vep.html",
        sample=sample,
        sample_ids=sample_ids,
        assay=assay_group,
        dna_sections=dna_sections,
        display_sections_data=display_sections_data,
        assay_panels=insilico_panel_genelists,
        checked_genelists_dict=genes_covered_in_panel,
        hidden_comments=has_hidden_comments,
        vep_var_class_translations=vep_variant_class_meta,
        vep_conseq_translations=vep_conseq_meta,
        bam_id=bam_id,
        form=form,
        ai_text=ai_text,
    )


# TODO
@dna_bp.route("/<sample_id>/multi_class", methods=["POST"])
@login_required
@require_sample_group_access("sample_id")
@require("manage_snvs", min_role="user", min_level=9)
def classify_multi_variant(sample_id) -> Response:
    """
    Classify multiple variants
    """
    action = request.form.get("action")
    variants_to_modify = request.form.getlist("selected_object_id")
    assay = request.form.get("assay", None)
    subpanel = request.form.get("subpanel", None)
    tier = request.form.get("tier", None)
    irrelevant = request.form.get("irrelevant", None)
    false_positive = request.form.get("false_positive", None)

    if tier and action == "apply":
        variants_iter = []
        for variant in variants_to_modify:
            var_iter = store.variant_handler.get_variant(str(variant))
            variants_iter.append(var_iter)

        for var in variants_iter:
            selectec_csq = var["INFO"]["selected_CSQ"]
            transcript = selectec_csq.get("Feature", None)
            gene = selectec_csq.get("SYMBOL", None)
            hgvs_p = selectec_csq.get("HGVSp", None)
            hgvs_c = selectec_csq.get("HGVSc", None)
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = selectec_csq.get("Consequence", None)
            gene_oncokb = store.oncokb_handler.get_oncokb_gene(gene)
            text = util.dna.create_annotation_text_from_gene(
                gene, consequence, assay, gene_oncokb=gene_oncokb
            )

            nomenclature = "p"
            if hgvs_p != "" and hgvs_p is not None:
                variant = hgvs_p
            elif hgvs_c != "" and hgvs_c is not None:
                variant = hgvs_c
                nomenclature = "c"
            else:
                variant = hgvs_g
                nomenclature = "g"

            variant_data = {
                "gene": gene,
                "assay": assay,
                "subpanel": subpanel,
                "transcript": transcript,
            }

            # Add the variant to the database with class
            store.annotation_handler.insert_classified_variant(
                variant=variant,
                nomenclature=nomenclature,
                class_num=3,
                variant_data=variant_data,
            )

            # Add the annotation text to the database
            store.annotation_handler.insert_classified_variant(
                variant=variant,
                nomenclature=nomenclature,
                class_num=3,
                variant_data=variant_data,
                text=text,
            )
            if irrelevant:
                store.variant_handler.mark_irrelevant_var(var["_id"])
    if false_positive:
        if action == "apply":
            for variant in variants_to_modify:
                store.variant_handler.mark_false_positive_var(variant)
        elif action == "remove":
            for variant in variants_to_modify:
                store.variant_handler.unmark_false_positive_var(variant)
    if irrelevant:
        if action == "apply":
            for variant in variants_to_modify:
                store.variant_handler.mark_irrelevant_var(variant)
        elif action == "remove":
            for variant in variants_to_modify:
                store.variant_handler.unmark_irrelevant_var(variant)
    return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))


@dna_bp.route("/<string:sample_id>/plot/<string:fn>", endpoint="show_any_plot")  # type: ignore
@dna_bp.route("/<string:sample_id>/plot/rotated/<string:fn>", endpoint="show_any_plot_rotated")  # type: ignore
@login_required
@require_sample_group_access("sample_id")
def show_any_plot(sample_id, fn, angle=90):

    sample = store.sample_handler.get_sample(sample_id)

    if sample is None:
        sample = store.sample_handler.get_sample_with_id(sample_id)

    sample_assay = util.common.select_one_sample_group(sample.get("groups"))
    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.home_screen"))

    # New way to retrive assay group config from db assay configs
    assay_config = store.assay_config_handler.get_assay_config_filtered(
        sample_assay
    )

    if not assay_config:
        flash(f"No config found for the the assay {sample_assay}", "red")
        return redirect(url_for("home_bp.home_screen"))

    base_dir = assay_config.get("REPORT", {}).get("plots_path", None)

    if base_dir:
        file_path = os.path.join(base_dir, fn)
        if not os.path.exists(file_path):
            flash(f"File not found: {file_path}", "red")
            return request.url

    if request.endpoint == "dna_bp.show_any_plot_rotated":
        # Rotate the image by the specified angle (default is 90 degrees)

        try:
            with Image.open(os.path.join(base_dir, fn)) as img:
                rotated_img = img.rotate(-angle, expand=True)
                img_io = io.BytesIO()
                rotated_img.save(img_io, format="PNG")
                img_io.seek(0)
                return send_file(img_io, mimetype="image/png")
        except Exception as e:
            app.logger.error(f"Error rotating image: {e}")
            flash("Error processing image", "red")
            return request.url
    else:
        return send_from_directory(base_dir, fn)


## Individual variant view ##
@dna_bp.route("/<string:sample_id>/var/<string:var_id>")
@login_required
@require_sample_group_access("sample_id")
def show_variant(sample_id, var_id):

    variant = store.variant_handler.get_variant(var_id)
    sample = store.sample_handler.get_sample_with_id(variant["SAMPLE_ID"])

    ## Check the length of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
    sample_assay = util.common.select_one_sample_group(sample.get("groups"))
    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.home_screen"))

    # New way to retrive assay group config from db assay configs
    assay_config = store.assay_config_handler.get_assay_config_filtered(
        sample_assay
    )

    if not assay_config:
        flash(f"No config found for the the assay {sample_assay}", "red")
        return redirect(url_for("home_bp.home_screen"))

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("assay_group", "unknown")
    subpanel: str | None = sample.get("subpanel")

    # Get assay groups mappings with the sample assay
    assay_group_mappings = (
        store.assay_config_handler.get_assay_group_mappings()
    )

    # Get sample data if the variant is present in other samples
    in_other = store.variant_handler.get_variant_in_other_samples(variant)

    # Check if variant has hidden comments
    has_hidden_comments = store.variant_handler.hidden_var_comments(var_id)

    # TODO: We have to find a way to present this dataq
    expression = store.expression_handler.get_expression_data(
        list(variant.get("transcripts"))
    )

    # app.logger.debug(f"Expression data: {expression}")

    variant = store.blacklist_handler.add_blacklist_data(
        [variant], assay_group
    )[0]

    # Find civic data
    variant_desc = "NOTHING_IN_HERE"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "CALR"
        and variant["INFO"]["selected_CSQ"]["EXON"] == "9/9"
        and "frameshift_variant"
        in variant["INFO"]["selected_CSQ"]["Consequence"]
    ):
        variant_desc = "EXON 9 FRAMESHIFT"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "FLT3"
        and "SVLEN" in variant["INFO"]
        and variant["INFO"]["SVLEN"] > 10
    ):
        variant_desc = "ITD"

    civic = store.civic_handler.get_civic_data(variant, variant_desc)

    civic_gene = store.civic_handler.get_civic_gene_info(
        variant["INFO"]["selected_CSQ"]["SYMBOL"]
    )

    # Find OncoKB data
    oncokb_hgvsp = []
    if len(variant["INFO"]["selected_CSQ"]["HGVSp"]) > 0:
        hgvsp = filters.one_letter_p(variant["INFO"]["selected_CSQ"]["HGVSp"])
        hgvsp = hgvsp.replace("p.", "")
        oncokb_hgvsp.append(hgvsp)

    if variant["INFO"]["selected_CSQ"]["Consequence"] in [
        "frameshift_variant",
        "stop_gained",
        "frameshift_deletion",
        "frameshift_insertion",
    ]:
        oncokb_hgvsp.append("Truncating Mutations")

    oncokb = store.oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = store.oncokb_handler.get_oncokb_action(
        variant, oncokb_hgvsp
    )
    oncokb_gene = store.oncokb_handler.get_oncokb_gene(
        variant["INFO"]["selected_CSQ"]["SYMBOL"]
    )

    # Find BRCA-exchange data
    brca_exchange = store.brca_handler.get_brca_data(variant, assay_group)

    # Find IARC TP53 data
    iarc_tp53 = store.iarc_tp53_handler.find_iarc_tp53(variant)

    # Get bams
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Format PON (panel of normals) data
    pon = util.dna.format_pon(variant)

    # Get global annotations for the variant
    (
        annotations,
        classification,
        other_classifications,
        annotations_interesting,
    ) = store.annotation_handler.get_global_annotations(
        variant, assay_group, subpanel
    )

    if not classification or classification.get("class") == 999:
        variant = util.dna.add_alt_class(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(
        sample.get("vep", 103)
    )

    return render_template(
        "show_variant_vep.html",
        variant=variant,
        in_other=in_other,
        annotations=annotations,
        hidden_comments=has_hidden_comments,
        classification=classification,
        expression=expression,
        civic=civic,
        civic_gene=civic_gene,
        oncokb=oncokb,
        oncokb_action=oncokb_action,
        oncokb_gene=oncokb_gene,
        sample=sample,
        brca_exchange=brca_exchange,
        iarc_tp53=iarc_tp53,
        assay=assay_group,
        pon=pon,
        other_classifications=other_classifications,
        subpanel=subpanel,
        sample_ids=sample_ids,
        bam_id=bam_id,
        annotations_interesting=annotations_interesting,
        vep_var_class_translations=vep_variant_class_meta,
        vep_conseq_translations=vep_conseq_meta,
        assay_group_mappings=assay_group_mappings,
    )


@dna_bp.route("/gene_simple/<string:gene_name>", methods=["GET", "POST"])
@login_required
@require("view_gene_annotations", min_role="user", min_level=9)
def gene_view_simple(gene_name):
    AssayGroupForm = create_assay_group_form()
    form = AssayGroupForm()

    annotations = store.annotation_handler.get_gene_annotations(gene_name)
    annotations_dict = util.dna.process_gene_annotations(annotations)

    checked_assays = []
    if form.validate_on_submit():
        checked_assays = [
            k for k, v in form.data.items() if v and k not in ["csrf_token"]
        ]

    return render_template(
        "gene_view2.html",
        form=form,
        checked_assays=checked_assays,
        gene=gene_name,
        annotations=annotations,
        annodict=annotations_dict,
    )


@dna_bp.route("/gene/<string:gene_name>", methods=["GET", "POST"])
@login_required
@require("view_gene_annotations", min_role="user", min_level=9)
def gene_view(gene_name):

    variants_iter = store.variant_handler.get_variants_by_gene(gene_name)
    variants = list(variants_iter)

    app.logger.debug(f"gene specific variants: {len(variants)}")

    # TODO:  How slow is this????
    variants, tiered_variants = util.dna.add_global_annotations(variants, "assay", "subpanel")

    variant_summary = defaultdict(dict)
    sample_oids = []
    for var in variants:
        short_pos = var.get("simple_id", None)

        if not var.get("classification"):
            continue

        if var["classification"].get("class", 999) != 999:

            sample_oids.append(ObjectId(var["SAMPLE_ID"]))

            if short_pos in variant_summary:
                variant_summary[short_pos]["count"] += 1
                variant_summary[short_pos]["samples"].append(var["SAMPLE_ID"])
            else:
                variant_summary[short_pos]["count"] = 1
                variant_summary[short_pos]["CSQ"] = var["INFO"]["selected_CSQ"]
                variant_summary[short_pos]["anno"] = var["global_annotations"]
                variant_summary[short_pos]["class"] = var["classification"]
                variant_summary[short_pos]["samples"] = [var["SAMPLE_ID"]]

    # Get display names for the samples, from db.
    samples = store.sample_handler.get_samples_by_oids(sample_oids)

    # Create hash for translation ID -> display name, from samples
    sample_names = {}
    for sample in samples:
        sample_names[str(sample["_id"])] = sample["name"]

    return render_template(
        "gene_view.html", variants=variant_summary, sample_names=sample_names
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def unmark_false_variant(sample_id, var_id):
    """
    Unmark False Positive status of a variant in the database
    """
    store.variant_handler.unmark_false_positive_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def mark_false_variant(sample_id, var_id):
    """
    Mark False Positive status of a variant in the database
    """
    store.variant_handler.mark_false_positive_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def unmark_interesting_variant(sample_id, var_id):
    """
    Unmark interesting status of a variant in the database
    """
    store.variant_handler.unmark_interesting_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def mark_interesting_variant(sample_id, var_id):
    """
    Mark interesting status of a variant in the database
    """
    store.variant_handler.mark_interesting_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/unirrelevant", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def unmark_irrelevant_variant(sample_id, var_id):
    """
    Unmark irrelevant status of a variant in the database
    """
    store.variant_handler.unmark_irrelevant_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def mark_irrelevant_variant(sample_id, var_id):
    """
    Mark irrelevant status of a variant in the database
    """
    store.variant_handler.mark_irrelevant_var(id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def add_variant_to_blacklist(sample_id, var_id):

    var = store.variant_handler.get_variant(id)
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    assay = util.common.get_assay_from_sample(sample)
    store.blacklist_handler.blacklist_variant(var, assay)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, id=id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/ordersanger", methods=["POST"]
)
@login_required
@require("manage_snvs", min_role="admin")
@require_sample_group_access("sample_id")
def order_sanger(sample_id, var_id):
    variant = store.variant_handler.get_variant(id)
    variants, protein_coding_genes = util.dna.get_protein_coding_genes(
        [variant]
    )
    var = variants[0]
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    canonical_dict = store.canonical_handler.get_canonical_by_genes(
        list(protein_coding_genes)
    )

    var["INFO"]["selected_CSQ"], var["INFO"]["selected_CSQ_criteria"] = (
        util.select_csq(var["INFO"]["CSQ"], canonical_dict)
    )

    html, tx_info = util.dna.compose_sanger_email(var, sample["name"])

    email_status = util.dna.send_sanger_email(html, tx_info["SYMBOL"])

    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/classify", methods=["POST"]
)
@login_required
@require(permission="tier_dna_variant", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def classify_variant(sample_id, var_id):
    form_data = request.form.to_dict()
    class_num = util.dna.get_tier_classification(form_data)
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if class_num != 0:
        store.annotation_handler.insert_classified_variant(
            variant, nomenclature, class_num, form_data
        )

    if class_num != 0:
        if nomenclature == "f":
            return redirect(url_for("rna_bp.show_fusion", id=var_id))

    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/rmclassify", methods=["POST"]
)
@login_required
@require(permission="remove_dna_variant_tier", min_role="admin")
@require_sample_group_access("sample_id")
def remove_classified_variant(sample_id, var_id):
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", id=var_id))
    per_assay = store.annotation_handler.delete_classified_variant(
        variant, nomenclature, form_data
    )
    app.logger.debug(per_assay)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/add_variant_comment",
    methods=["POST"],
    endpoint="add_variant_comment",
)
@dna_bp.route(
    "/<string:sample_id>/cnv/<string:cnv_id>/add_cnv_comment",
    methods=["POST"],
    endpoint="add_cnv_comment",
)
@dna_bp.route(
    "/<string:sample_id>/fusion/<string:fus_id>/add_fusion_comment",
    methods=["POST"],
    endpoint="add_fusion_comment",
)
@dna_bp.route(
    "/<string:sample_id>/translocation/<string:transloc_id>/add_translocation_comment",
    methods=["POST"],
    endpoint="add_translocation_comment",
)
@login_required
@require("add_variant_comment", min_role="user", min_level=9)
@require_sample_group_access("sample_id")
def add_var_comment(sample_id, id=None, **kwargs):
    """
    Add a comment to a variant
    """

    id = (
        id
        or request.view_args.get("var_id")
        or request.view_args.get("cnv_id")
        or request.view_args.get("fus_id")
        or request.view_args.get("transloc_id")
    )

    # If global checkbox. Save variant with the protein, coding och genomic nomenclature in decreasing priority
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    doc = util.dna.create_comment_doc(
        form_data, nomenclature=nomenclature, variant=variant
    )
    _type = form_data.get("global", None)
    if _type == "global":
        store.annotation_handler.add_anno_comment(doc)
        flash("Global comment added", "green")

    if nomenclature == "f":
        if _type != "global":
            store.fusion_handler.add_fusion_comment(id, doc)
        return redirect(
            url_for("rna_bp.show_fusion", sample_id=sample_id, id=id)
        )
    elif nomenclature == "t":
        if _type != "global":
            store.transloc_handler.add_transloc_comment(id, doc)
        return redirect(
            url_for(
                "dna_bp.show_transloc", sample_id=sample_id, transloc_id=id
            )
        )
    elif nomenclature == "cn":
        if _type != "global":
            store.cnv_handler.add_cnv_comment(id, doc)
        return redirect(
            url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=id)
        )
    else:
        if _type != "global":
            store.variant_handler.add_var_comment(id, doc)

    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/hide_variant_comment",
    methods=["POST"],
)
@login_required
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def hide_variant_comment(sample_id, var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.hide_var_comment(var_id, comment_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/unhide_variant_comment",
    methods=["POST"],
)
@login_required
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def unhide_variant_comment(sample_id, var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.unhide_variant_comment(var_id, comment_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


###### CNVS VIEW PAGE #######
@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>")
@login_required
@require_sample_group_access("sample_id")
def show_cnv(sample_id, cnv_id):
    """
    Show CNVs view page
    """
    cnv = store.cnv_handler.get_cnv(cnv_id)
    sample = store.sample_handler.get_sample_with_id((cnv["SAMPLE_ID"]))
    sample_assay = util.common.select_one_sample_group(sample.get("groups"))
    # sample_assay = util.common.get_assay_from_sample(sample)
    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.home_screen"))

    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_cnv_comments = store.cnv_handler.hidden_cnv_comments(cnv_id)

    annotations = store.cnv_handler.get_cnv_annotations(cnv)
    return render_template(
        "show_cnvwgs.html",
        cnv=cnv,
        sample=sample,
        assay=sample_assay,
        classification=999,
        annotations=annotations,
        sample_ids=sample_ids,
        bam_id=bam_id,
        hidden_comments=hidden_cnv_comments,
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/uninterestcnv", methods=["POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_interesting_cnv(sample_id, cnv_id):
    """
    Unmark CNV as interesting
    """
    store.cnv_handler.unmark_interesting_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/interestcnv", methods=["POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_interesting_cnv(sample_id, cnv_id):
    """
    Mark CNV as interesting
    """
    store.cnv_handler.mark_interesting_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/fpcnv", methods=["POST"])
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_false_cnv(sample_id, cnv_id):
    """
    Mark CNV as false positive
    """
    store.cnv_handler.mark_false_positive_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "/<string:sample_id>/cnv/<string:cnv_id>/unfpcnv", methods=["POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_false_cnv(sample_id, cnv_id):
    """
    Unmark CNV as false positive
    """
    store.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/noteworthycnv", methods=["POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_noteworthy_cnv(sample_id, cnv_id):
    """
    Mark CNV as note worthy
    """
    store.cnv_handler.noteworthy_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/unnoteworthycnv", methods=["POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_noteworthy_cnv(sample_id, cnv_id):
    """
    Unmark CNV as note worthy
    """
    store.cnv_handler.unnoteworthy_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/hide_cnv_comment", methods=["POST"]
)
@login_required
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def hide_cnv_comment(sample_id, cnv_id):
    """
    Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/unhide_cnv_comment",
    methods=["POST"],
)
@login_required
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def unhide_cnv_comment(sample_id, cnv_id):
    """
    Un Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


###### TRANSLOCATIONS VIEW PAGE #######
@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>")
@login_required
@require_sample_group_access("sample_id")
def show_transloc(sample_id, transloc_id):
    """
    Show Translocation view page
    """
    transloc = store.transloc_handler.get_transloc(transloc_id)
    sample = store.sample_handler.get_sample_with_id((transloc["SAMPLE_ID"]))
    sample_assay = util.common.get_assay_from_sample(sample)
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_transloc_comments = store.transloc_handler.hidden_transloc_comments(
        transloc_id
    )

    annotations = store.transloc_handler.get_transloc_annotations(transloc)
    return render_template(
        "show_transloc.html",
        tl=transloc,
        sample=sample,
        assay=sample_assay,
        classification=999,
        annotations=annotations,
        bam_id=bam_id,
        hidden_comments=hidden_transloc_comments,
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/interesttransloc",
    methods=["POST"],
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_interesting_transloc(sample_id, transloc_id):
    store.transloc_handler.mark_interesting_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/uninteresttransloc",
    methods=["POST"],
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_interesting_transloc(sample_id, transloc_id):
    store.transloc_handler.unmark_interesting_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/fptransloc",
    methods=["POST"],
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_false_transloc(sample_id, transloc_id):
    store.transloc_handler.mark_false_positive_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/unfptransloc",
    methods=["POST"],
)
@login_required
@require_sample_group_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_false_transloc(sample_id, transloc_id):
    store.transloc_handler.unmark_false_positive_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/hide_variant_comment",
    methods=["POST"],
)
@login_required
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def hide_transloc_comment(sample_id, transloc_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/unhide_variant_comment",
    methods=["POST"],
)
@login_required
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_group_access("sample_id")
def unhide_transloc_comment(sample_id, transloc_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


##### PREVIEW REPORT ######
@dna_bp.route(
    "/sample/<string:sample_id>/preview_report", methods=["GET", "POST"]
)
@login_required
@require_sample_group_access("sample_id")
@require("preview_report", min_role="user", min_level=9)
def generate_dna_report(sample_id, **kwargs) -> Response | str:
    """
    Generate and render a DNA report for a given sample.
    This function retrieves sample and assay configuration data, applies filters,
    gathers variant and biomarker information, and prepares all necessary data
    for rendering a comprehensive DNA report. The report includes SNVs, CNVs,
    biomarkers, translocations, fusions, and low coverage regions, depending on
    the assay configuration and available data.
    Args:
        sample_id (str): The identifier (name or ID) of the sample to generate the report for.
        **kwargs: Additional keyword arguments. Supported:
            - save (int, optional): If set, indicates the report should be saved.
    Returns:
        flask.Response: Rendered HTML template for the DNA report, or a redirect
        response if required data is missing.
    Side Effects:
        - Flashes messages to the user if sample or assay configuration is missing.
        - Redirects to the home screen if critical data is not found.
        - Logs debug information about the assay group and configuration.
    """

    sample = store.sample_handler.get_sample(sample_id)  # sample_id = name

    if not sample:
        sample = store.sample_handler.get_sample_with_id(
            sample_id
        )  # sample_id = id

    sample_assay = util.common.select_one_sample_group(sample.get("groups"))

    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.home_screen"))

    # New way to retrive assay group config from db assay configs
    assay_config = store.assay_config_handler.get_assay_config_filtered(
        sample_assay
    )

    if not assay_config:
        flash(f"No config found for the the assay {sample_assay}", "red")
        return redirect(url_for("home_bp.home_screen"))

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("assay_group", "unknown")
    subpanel = sample.get("subpanel")
    dna_sections = list(assay_config.get("DNA", {}).keys())
    display_sections_data = {}
    app.logger.debug(
        f"Assay group: {assay_group} - DNA config: {pformat(dna_sections)}"
    )
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get number of the samples in this report (paired, unpaired)
    sample["num_samples"] = store.variant_handler.get_num_samples(
        str(sample["_id"])
    )

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.panel_handler.get_panel(panel_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = (
        store.insilico_genelist_handler.get_genelists_by_panel(sample_assay)
    )
    all_panel_genelist_names = util.common.get_assay_genelist_names(
        insilico_panel_genelists
    )

    # Load all genelist and panel names for the assay group
    # assay_group_genelists, assay_group_genelists_docs = store.panel_handler.get_assay_panels(
    #     assay_group
    # )

    # sample filters
    if not sample.get("filters"):
        sample = util.common.merge_sample_settings_with_assay_config(
            sample, assay_config
        )

    sample_filters = deepcopy(sample.get("filters", {}))

    # Get the genelist filters from the sample settings
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict: list[dict] = (
        store.insilico_genelist_handler.get_genelist_docs_by_ids(
            checked_genelists
        )
    )

    genes_covered_in_panel: list[dict] = (
        util.common.get_genes_covered_in_panel(
            checked_genelists_genes_dict, assay_panel_doc
        )
    )

    filter_conseq = util.dna.get_filter_conseq_terms(
        sample_filters.get("vep_consequences", [])
    )
    # Create a unique list of genes from the selected genelists which are currently active in the panel
    filter_genes = util.common.create_filter_genelist(genes_covered_in_panel)

    disp_pos = []
    if "verification_samples" in assay_config:
        if sample["name"] in assay_config["verification_samples"]:
            disp_pos = assay_config["verification_samples"][sample["name"]]

    # Get all the variants for the report
    query = build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": sample_filters["max_freq"],
            "min_freq": sample_filters["min_freq"],
            "max_control_freq": sample_filters["max_control_freq"],
            "min_depth": sample_filters["min_depth"],
            "min_alt_reads": sample_filters["min_alt_reads"],
            "max_popfreq": sample_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
            "fp": {"$ne": True},
            "irrelevant": {"$ne": True},
        },
    )

    variants_iter = store.variant_handler.get_case_variants(query)
    variants = list(variants_iter)

    # Add blacklist data
    variants = store.blacklist_handler.add_blacklist_data(
        variants, assay=assay_group
    )

    # Add global annotations for the variants
    variants, tiered_variants = util.dna.add_global_annotations(variants, assay_group, subpanel)

    # # Filter by population frequency
    # variants = util.dna.popfreq_filter(variants, float(sample_settings["max_popfreq"]))

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    # Filter variants for report
    variants = util.dna.filter_variants_for_report(
        variants, filter_genes, assay_group
    )

    # Sample dict for the variant summary table in the report
    display_sections_data["snvs"] = util.dna.get_simple_variants_for_report(
        variants, assay_config
    )

    ## GET CNVs TRANSLOCS and OTHER BIOMARKERS ##
    if "CNV" in dna_sections:
        display_sections_data["cnvs"] = list(
            store.cnv_handler.get_interesting_sample_cnvs(
                sample_id=str(sample["_id"])
            )
        )
        display_sections_data["cnv_profile_base64"] = util.common.get_plot(
            os.path.basename(sample.get("cnvprofile", "")), assay_config
        )

    if "BIOMARKER" in dna_sections:
        display_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
        )

    if "TRANSLOCATION" in dna_sections:
        display_sections_data["translocs"] = (
            store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )

    if "FUSION" in dna_sections:
        display_sections_data["fusions"] = []

    # TODO: LOW COV
    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = store.coverage_handler.get_sample_coverage(sample["name"])
    low_cov_chrs = list(set([x["chr"] for x in low_cov]))
    cosmic_ids = store.cosmic_handler.get_cosmic_ids(chr=low_cov_chrs)

    if assay_group != "solid":
        low_cov = util.dna.filter_low_coverage_with_cosmic(low_cov, cosmic_ids)
    # low_cov = store.coverage_handler.get_sample_coverage(sample["name"])
    display_sections_data["low_cov"] = deepcopy(low_cov)

    # report header and date
    assay_config["REPORT"]["header"] = util.common.get_report_header(
        assay_group, sample, assay_config["REPORT"].get("header", "Unknown")
    )

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )

    save = kwargs.get("save", 0)
    report_date = datetime.now().date()

    fernet = app.config["FERNET"]

    return render_template(
        "dna_report.html",
        assay_config=assay_config,
        dna_sections=dna_sections,
        display_sections_data=display_sections_data,
        sample=sample,
        translation=util.report.VARIANT_CLASS_TRANSLATION,
        vep_var_class_translations=vep_variant_class_meta,
        class_desc=util.report.TIER_DESC,
        class_desc_short=util.report.TIER_SHORT_DESC,
        report_date=report_date,
        save=save,
        sample_assay=sample_assay,
        encrypted_panel_doc=util.common.encrypt_json(assay_panel_doc, fernet),
        encrypted_genelists=util.common.encrypt_json(
            genes_covered_in_panel, fernet
        ),
    )


@dna_bp.route("/sample/<string:sample_id>/report/save")
@login_required
@require_sample_group_access("sample_id")
@require("save_dna_report", min_role="admin")
def save_dna_report(sample_id) -> Response:
    """
    Saves a DNA report for the specified sample.
    This function retrieves a sample by its ID, determines the appropriate assay group,
    and generates a DNA report in HTML format. The report is saved to a file system path
    based on the assay group and sample information. If a report with the same name already
    exists, an error is raised. The function also updates the sample's report records and
    provides user feedback via flash messages.
    Args:
        sample_id (str): The unique identifier of the sample for which the DNA report is to be saved.
    Returns:
        werkzeug.wrappers.Response: A redirect response to the home screen.
    Raises:
        AppError: If a report with the same name already exists or if saving the report fails.
    """
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)
    if not sample:
        flash("Sample not found.", "red")
        return redirect(url_for("home_bp.home_screen"))

    sample_assay = util.common.select_one_sample_group(sample.get("groups"))
    if not sample_assay:
        flash("No assay group found for sample.", "red")
        return redirect(url_for("home_bp.home_screen"))

    assay_config = store.assay_config_handler.get_assay_config_filtered(
        sample_assay
    )
    if not assay_config:
        flash(f"No config found for the assay {sample_assay}.", "red")
        return redirect(url_for("home_bp.home_screen"))

    assay_group = assay_config.get("assay_group", "unknown")
    report_num = sample.get("report_num", 0) + 1
    report_id = f"{sample_id}.{report_num}"
    report_path = os.path.join(app.config["REPORTS_BASE_PATH"], assay_group)
    os.makedirs(report_path, exist_ok=True)
    report_file = os.path.join(report_path, f"{report_id}.html")

    if os.path.exists(report_file):
        flash("Report already exists.", "red")
        app.logger.warning(f"Report file already exists: {report_file}")
        raise AppError(
            status_code=409,
            message="Report already exists with the requested name.",
            details=f"File name: {os.path.basename(report_file)}",
        )

    try:

        html = generate_dna_report(sample_id=sample_id, save=1)

        if not util.common.write_report(html, report_file):
            raise AppError(
                status_code=500,
                message=f"Failed to save report {report_id}.html",
                details="Could not write the report to the file system.",
            )
        store.sample_handler.save_report(
            sample_id=sample_id,
            report_id=report_id,
            filepath=report_file,
        )
        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info(f"Report saved: {report_file}")
    except AppError as app_err:
        flash(app_err.message, "red")
        app.logger.error(
            f"AppError: {app_err.message} | Details: {app_err.details}"
        )
    except Exception as exc:
        flash("An unexpected error occurred while saving the report.", "red")
        app.logger.exception(f"Unexpected error: {exc}")

    return redirect(url_for("home_bp.home_screen"))
