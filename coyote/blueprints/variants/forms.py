from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, FloatField
from wtforms.validators import InputRequired, NumberRange, Optional


class FilterForm(FlaskForm):
    """Filter form"""

    min_reads = IntegerField("minreads", validators=[InputRequired(), NumberRange(min=0)])
    min_depth = IntegerField("mindepth", validators=[InputRequired(), NumberRange(min=0)])
    min_freq = FloatField("Min freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_freq = FloatField("Max freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_popfreq = FloatField(
        "Population freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    min_cnv_size = IntegerField("Min CNV size", validators=[InputRequired(), NumberRange(min=1)])
    max_cnv_size = IntegerField("Max CNV size", validators=[InputRequired(), NumberRange(min=2)])

    exonic = BooleanField()
    utr = BooleanField()
    ncrna = BooleanField()

    stopgain = BooleanField()
    stoploss = BooleanField()
    fs_indels = BooleanField()
    nfs_indels = BooleanField()
    unknown = BooleanField()
    empty = BooleanField()

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

    reset = BooleanField()

    # fusionlist_Leukemi = BooleanField(validators=[Optional()])
    # fusionlist_barntumor = BooleanField(validators=[Optional()])
    fusionlist_FCknown = BooleanField(validators=[Optional()])
    fusionlist_mitelman = BooleanField(validators=[Optional()])

    fusioncaller_arriba = BooleanField(validators=[Optional()])
    fusioncaller_fusioncatcher = BooleanField(validators=[Optional()])
    fusioncaller_starfusion = BooleanField(validators=[Optional()])

    min_spanpairs = IntegerField("Spanning pairs", validators=[Optional()])
    min_spanreads = IntegerField("Spanning reads", validators=[Optional()])

    fusioneffect_inframe = BooleanField(validators=[Optional()])
    fusioneffect_outframe = BooleanField(validators=[Optional()])

    ### assays filters
    solid = BooleanField()
    myeloid = BooleanField()
    tumwgs = BooleanField()
    lymphoid = BooleanField()
    parp = BooleanField()
    historic = BooleanField()
