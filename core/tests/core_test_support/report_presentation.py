"""Synthetic reusable fixtures for package-owned behavior tests."""

from core_test_support.report_context import context


def structural_context():
    """Supply synthetic findings for compact summary and detailed evidence checks."""
    inputs = empty_context()
    inputs["sample"]["paired"] = True
    inputs["report_scope_label"] = "Synthetic diagnosis · parad analys"
    inputs["latest_sample_comment_text"] = "Synthetic reviewed conclusion."
    inputs["report_sections"] = ["SNV", "CNV", "TRANSLOCATION"]
    inputs["report_sections_data"].update(
        snvs=[
            {
                "symbol": "TP53",
                "chr": "17",
                "pos": 10001,
                "class_type": "Somatisk",
                "variant_class": "SNV",
                "var_type": "snv",
                "feature": "ENST_SYNTHETIC_001",
                "consequence": "missense",
                "exon": ["4/11"],
                "variant": "p.(K4E)",
                "cdna": "c.10A>G",
                "af": 0.4,
                "indel_size": 0,
                "class": 1,
                "class_short_desc": "Synthetic clinical significance",
                "class_long_desc": "Synthetic interpretation",
                "protein_changes": ["p.(K4E)", "p.(Lys4Glu)"],
                "global_annotations": [],
                "annotations_interesting": {},
            }
        ],
        cnvs=[
            {
                "genes": [{"gene": "MYC", "class": 1}],
                "chr": "8",
                "start": 10001,
                "end": 20000,
                "size": 10000,
                "type": "DUP",
                "ratio": 1,
                "nprobes": 20,
                "classification": {"class": 2},
                "global_annotations": [],
            }
        ],
        translocs=[
            {
                "CHROM": "22",
                "POS": 10001,
                "ALT": "N[9:20001[",
                "INFO": {"ANN": [{"Gene_Name": "BCR&ABL1", "Rank": "2/10"}]},
                "GT": [{"type": "case", "PR": [100, 20], "SR": [50, 0]}],
                "classification": {"class": 1},
                "global_annotations": [],
            }
        ],
    )
    return inputs


def empty_context(analyte="dna"):
    """Prepare enabled sections with no reportable findings and complete metadata."""
    inputs = context()
    inputs["sample"].update(
        case_id="SYNTHETIC_CASE",
        control_id="SYNTHETIC_CONTROL",
        sample_no=2,
    )
    inputs["assay_config"]["reporting"]["report_method"] = "Synthetic method"
    inputs["report_date"] = "2026-10-25"
    inputs["report_timestamp"] = "SYNTHETIC_REPORT_ID"
    inputs["report_sections"] = [
        "SNV",
        "CNV",
        "TRANSLOCATION",
        "HRD",
        "MSI",
        "TMB",
        "BIOMARKER",
        "PGX",
    ]
    inputs["report_sections_data"] = {
        "snvs": [],
        "germline_snvs": [],
        "cnvs": [],
        "translocs": [],
        "hrd": [],
        "msi": [],
        "tmb": [],
        "biomarkers": [],
        "pgx": [],
    }
    if analyte == "rna":
        inputs["report_sections"] = ["FUSION", "PGX"]
        inputs["pgx"] = []
    return inputs
