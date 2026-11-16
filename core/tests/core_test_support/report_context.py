"""Synthetic reusable fixtures for package-owned behavior tests."""


def context():
    """Return the synthetic inputs captured before extracting the embedded templates."""
    return {
        "sample": {"name": "SYNTHETIC_EXTRACTION", "case": {}, "control": {}},
        "assay_config": {"reporting": {"report_header": "Synthetic report"}},
        "report_header": "Synthetic report",
        "report_sections": [],
        "report_sections_data": {},
        "fusions": [],
        "genes_covered_in_panel": {},
    }
