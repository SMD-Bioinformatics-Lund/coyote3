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
This module defines Flask-WTF form classes for genomic data analysis and reporting in the Coyote3 project.
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, FloatField
from wtforms.validators import InputRequired, NumberRange, Optional
from coyote.extensions import store


class DNAFilterForm(FlaskForm):
    """
    Filter form for DNA variant analysis.

    This form provides numeric and boolean filters for DNA variant data,
    including read depth, allele frequency, CNV size, VEP consequences,
    CNV effects, and genelist options. Used in the Coyote3 genomic analysis
    workflow to allow users to customize variant filtering criteria.
    """

    # Core numeric filters
    min_alt_reads = IntegerField(
        "Min Alt Reads", validators=[InputRequired(), NumberRange(min=0)]
    )
    min_depth = IntegerField(
        "Min Depth", validators=[InputRequired(), NumberRange(min=0)]
    )
    min_freq = FloatField(
        "Min Freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    max_freq = FloatField(
        "Max Freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    max_control_freq = FloatField(
        "Max Control Freq",
        validators=[InputRequired(), NumberRange(min=0, max=1)],
    )
    max_popfreq = FloatField(
        "Population Freq",
        validators=[InputRequired(), NumberRange(min=0, max=1)],
    )
    min_cnv_size = IntegerField(
        "Min CNV Size", validators=[InputRequired(), NumberRange(min=1)]
    )
    max_cnv_size = IntegerField(
        "Max CNV Size", validators=[InputRequired(), NumberRange(min=2)]
    )
    cnv_loss_cutoff = FloatField(
        "CNV Loss Cutoff", validators=[InputRequired(), NumberRange()]
    )
    cnv_gain_cutoff = FloatField(
        "CNV Gain Cutoff", validators=[InputRequired(), NumberRange()]
    )
    warn_cov = IntegerField(
        "Coverage Warning Threshold",
        validators=[InputRequired(), NumberRange(min=0)],
    )
    error_cov = IntegerField(
        "Coverage Error Threshold",
        validators=[InputRequired(), NumberRange(min=0)],
    )

    # VEP consequence boolean fields (prefixed with `vep_`)
    vep_splicing = BooleanField("Splicing")
    vep_stop_gained = BooleanField("Stop Gained")
    vep_stop_lost = BooleanField("Stop Lost")
    vep_start_lost = BooleanField("Start Lost")
    vep_frameshift = BooleanField("Frameshift")
    vep_inframe_indel = BooleanField("Inframe Indel")
    vep_missense = BooleanField("Missense")
    vep_other_coding = BooleanField("Other Coding")
    vep_synonymous = BooleanField("Synonymous")
    vep_UTR = BooleanField("UTR")
    vep_non_coding = BooleanField("Non-Coding")
    vep_intronic = BooleanField("Intronic")
    vep_intergenic = BooleanField("Intergenic")
    vep_regulatory = BooleanField("Regulatory")
    vep_feature_elon_trunc = BooleanField("Feature Elongation/Truncation")
    vep_transcript_structure = BooleanField("Transcript Structure")
    vep_miRNA = BooleanField("miRNA")
    vep_NMD = BooleanField("NMD")

    # CNV effects
    cnveffect_loss = BooleanField("CNV Loss")
    cnveffect_gain = BooleanField("CNV Gain")

    # default genelist for the diagnosis/subpanel
    use_diagnosis_genelist = BooleanField("Use Diagnosis Genelist")

    # Reset button
    reset = BooleanField("reset")


class FusionFilter(FlaskForm):
    """
    FusionFilter is a Flask-WTF form for filtering gene fusion events in genomic data analysis.

    This form provides boolean and numeric fields to filter fusion events based on:
    - Known fusion lists (e\.g\., FCknown, Mitelman)
    - Fusion caller tools (Arriba, FusionCatcher, STAR-Fusion)
    - Minimum spanning pairs and reads
    - Fusion effect types (in-frame, out-frame)
    - VEP consequence categories (splicing, stop gained/lost, frameshift, etc\.)

    Used in the Coyote3 workflow to allow users to customize fusion event filtering criteria.
    """

    fusionlist_FCknown = BooleanField(validators=[Optional()])
    fusionlist_mitelman = BooleanField(validators=[Optional()])

    fusioncaller_arriba = BooleanField(validators=[Optional()])
    fusioncaller_fusioncatcher = BooleanField(validators=[Optional()])
    fusioncaller_starfusion = BooleanField(validators=[Optional()])

    min_spanpairs = IntegerField(
        "Spanning pairs", validators=[InputRequired(), NumberRange(min=0)]
    )
    min_spanreads = IntegerField(
        "Spanning reads", validators=[InputRequired(), NumberRange(min=0)]
    )

    fusioneffect_inframe = BooleanField(validators=[Optional()])
    fusioneffect_outframe = BooleanField(validators=[Optional()])

    # VEP consequence boolean fields (prefixed with `vep_`)
    vep_splicing = BooleanField("Splicing")
    vep_stop_gained = BooleanField("Stop Gained")
    vep_stop_lost = BooleanField("Stop Lost")
    vep_start_lost = BooleanField("Start Lost")
    vep_frameshift = BooleanField("Frameshift")
    vep_inframe_indel = BooleanField("Inframe Indel")
    vep_missense = BooleanField("Missense")
    vep_other_coding = BooleanField("Other Coding")
    vep_synonymous = BooleanField("Synonymous")
    vep_UTR = BooleanField("UTR")
    vep_non_coding = BooleanField("Non-Coding")
    vep_intronic = BooleanField("Intronic")
    vep_intergenic = BooleanField("Intergenic")
    vep_regulatory = BooleanField("Regulatory")
    vep_feature_elon_trunc = BooleanField("Feature Elongation/Truncation")

    reset = BooleanField("reset")


def create_assay_group_form():
    """
    Create a dynamic Flask-WTF form class with BooleanField checkboxes for each assay group.

    This function queries all available assay groups from the ASP handler and generates a form
    class with a BooleanField for each group, allowing users to select one or more groups.
    An additional 'historic' checkbox is always included.

    Returns:
        type: A dynamically created subclass of FlaskForm with BooleanFields for each assay group.
    """
    assay_groups = store.asp_handler.get_all_asp_groups()

    fields = {
        group: BooleanField(
            group.replace("_", " ").capitalize(), validators=[Optional()]
        )
        for group in assay_groups
    }

    fields["historic"] = BooleanField("Historic", validators=[Optional()])

    # Dynamically create a FlaskForm class
    return type("DynamicAssayGroupForm", (FlaskForm,), fields)
