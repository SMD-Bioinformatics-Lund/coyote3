from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, FloatField
from wtforms.validators import InputRequired, NumberRange, Optional


class FilterForm(FlaskForm):
    """Filter form"""


class FilterForm(FlaskForm):
    """Filter form"""

    # Core numeric filters
    min_alt_reads = IntegerField("Min Alt Reads", validators=[InputRequired(), NumberRange(min=0)])
    min_depth = IntegerField("Min Depth", validators=[InputRequired(), NumberRange(min=0)])
    min_freq = FloatField("Min Freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_freq = FloatField("Max Freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_control_freq = FloatField(
        "Max Control Freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    max_popfreq = FloatField(
        "Population Freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    min_cnv_size = IntegerField("Min CNV Size", validators=[InputRequired(), NumberRange(min=1)])
    max_cnv_size = IntegerField("Max CNV Size", validators=[InputRequired(), NumberRange(min=2)])
    cnv_loss_cutoff = FloatField("CNV Loss Cutoff", validators=[InputRequired()])
    cnv_gain_cutoff = FloatField("CNV Gain Cutoff", validators=[InputRequired()])
    warn_cov = IntegerField(
        "Coverage Warning Threshold", validators=[InputRequired(), NumberRange(min=0)]
    )
    error_cov = IntegerField(
        "Coverage Error Threshold", validators=[InputRequired(), NumberRange(min=0)]
    )
    min_spanreads = IntegerField("Spanning Reads", validators=[Optional()])
    min_spanpairs = IntegerField("Spanning Pairs", validators=[Optional()])

    # VEP consequence booleans
    splicing = BooleanField()
    stop_gained = BooleanField()
    stop_lost = BooleanField()
    start_lost = BooleanField()
    frameshift = BooleanField()
    inframe_indel = BooleanField()
    missense = BooleanField()
    other_coding = BooleanField()
    synonymous = BooleanField()
    UTR = BooleanField()
    non_coding = BooleanField()
    intronic = BooleanField()
    intergenic = BooleanField()
    regulatory = BooleanField()
    feature_elon_trunc = BooleanField()

    # CNV effects
    cnveffect_loss = BooleanField("CNV Loss", validators=[Optional()])
    cnveffect_gain = BooleanField("CNV Gain", validators=[Optional()])

    # Fusion and filtering features
    use_diagnosis_genelist = BooleanField("Use Diagnosis Genelist")

    # TODO: Assay filters (existing) These are doubtful, do we need them?
    solid = BooleanField()
    myeloid = BooleanField()
    tumwgs = BooleanField()
    lymphoid = BooleanField()
    parp = BooleanField()
    historic = BooleanField()

    # Reset button
    reset = BooleanField()


class GeneForm(FilterForm):
    pass


class FusionFilter(FlaskForm):

    min_reads = IntegerField("minreads", validators=[Optional()])
    min_depth = IntegerField("mindepth", validators=[Optional()])
    min_freq = FloatField("Min freq", validators=[Optional()])
    max_freq = FloatField("Max freq", validators=[Optional()])
    max_popfreq = FloatField("Population freq", validators=[Optional()])
    min_cnv_size = IntegerField("Min CNV size", validators=[Optional()])
    max_cnv_size = IntegerField("Max CNV size", validators=[Optional()])

    splicing = BooleanField()
    stop_gained = BooleanField()
    frameshift = BooleanField()
    stop_lost = BooleanField()
    start_lost = BooleanField()
    inframe_indel = BooleanField()
    missense = BooleanField()
    other_coding = BooleanField()
    synonymous = BooleanField()
    UTR = BooleanField()
    non_coding = BooleanField()
    intronic = BooleanField()
    intergenic = BooleanField()
    regulatory = BooleanField()
    feature_elon_trunc = BooleanField()

    cnveffect_loss = BooleanField(validators=[Optional()])
    cnveffect_gain = BooleanField(validators=[Optional()])

    fusionlist_FCknown = BooleanField(validators=[Optional()])
    fusionlist_mitelman = BooleanField(validators=[Optional()])

    fusioncaller_arriba = BooleanField(validators=[Optional()])
    fusioncaller_fusioncatcher = BooleanField(validators=[Optional()])
    fusioncaller_starfusion = BooleanField(validators=[Optional()])

    min_spanpairs = IntegerField("Spanning pairs", validators=[InputRequired(), NumberRange(min=0)])
    min_spanreads = IntegerField("Spanning reads", validators=[InputRequired(), NumberRange(min=0)])

    fusioneffect_inframe = BooleanField(validators=[Optional()])
    fusioneffect_outframe = BooleanField(validators=[Optional()])

    reset = BooleanField()
