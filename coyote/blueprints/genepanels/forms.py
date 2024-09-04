from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    FileField,
    SubmitField,
    FloatField,
)
from wtforms.validators import DataRequired, Length, Regexp


class GenePanelForm(FlaskForm):
    """
    Gene Panel Form used for creating gene panels.
    """

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=1, max=50, message="Name must be between 1 and 50 characters."),
            Regexp(
                r"^[a-zA-Z][a-zA-Z0-9_]*$",
                message="Name must start with a letter and contain no special characters.",
            ),
        ],
    )
    displayname = StringField(
        "Display Name",
        validators=[
            DataRequired(),
            Length(min=1, max=100, message="Display name must be between 1 and 100 characters."),
            Regexp(
                r"^[a-zA-Z][a-zA-Z0-9_ ]*$",
                message="Display name must start with a letter and contain no special characters.",
            ),
        ],
    )
    type = SelectField(
        "Type",
        choices=[
            ("genelist", "Gene List"),
            ("fusionlist", "Fusion List"),
            ("fusion", "Fusion"),
            ("cnv", "CNV"),
        ],
        validators=[DataRequired()],
    )
    genes_file = FileField("Upload Genes (TSV File)")
    genes_text = TextAreaField("Paste Genes (comma-separated or newline-separated)")
    assays = StringField(
        "Assays",
        validators=[DataRequired()],
        render_kw={"placeholder": "Add or select assays"},
    )
    version = FloatField("Version", validators=[DataRequired()])
    submit = SubmitField("Create Gene Panel")


class UpdateGenePanelForm(GenePanelForm):
    """
    Update Gene Panel Form used for updating gene panels.
    """

    submit = SubmitField("Update Gene Panel")
