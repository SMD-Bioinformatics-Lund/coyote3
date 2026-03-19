"""
Coyote3 Report Utility Module
=====================================
This module provides the ReportUtility class, which contains utility methods and mappings
for generating and managing genomic data analysis reports. It includes tier definitions,
descriptions, and variant class translations used in clinical diagnostics and reporting.
"""

from typing import Dict


class ReportUtility:
    """
    The `ReportUtility` class provides static mappings and utility methods for generating and managing
    genomic data analysis reports. It includes:

    - Tier name mappings (`TIER_NAME`): Maps tier numbers to their Roman numeral representations.
    - Tier short descriptions (`TIER_SHORT_DESC`): Maps tier numbers to concise clinical significance descriptions (in Swedish).
    - Tier detailed descriptions (`TIER_DESC`): Maps tier numbers to detailed clinical significance descriptions (in Swedish).
    - Variant class translations (`VARIANT_CLASS_TRANSLATION`): Maps variant class identifiers to human-readable labels.

    These mappings are used throughout the reporting and clinical diagnostics workflow to standardize
    terminology and facilitate report generation.
    """

    TIER_NAME: Dict[int, str] = {
        1: "I",
        2: "II",
        3: "III",
        4: "IV",
    }

    TIER_SHORT_DESC: Dict[int, str] = {
        0: "None",
        1: "Stark klinisk signifikans",
        2: "Potentiell klinisk signifikans",
        3: "Oklar klinisk signifikans",
        4: "Benign/sannolikt benign",
    }

    TIER_DESC: Dict[int, str] = {
        0: "None",
        1: "Variant av stark klinisk signifikans",
        2: "Variant av potentiell klinisk signifikans",
        3: "Variant av oklar klinisk signifikans",
        4: "Variant bedömd som benign eller sannolikt benign",
    }

    VARIANT_CLASS_TRANSLATION: Dict[str, str] = {
        "missense_variant": "missense",
        "stop_gained": "stop gained",
        "frameshift_variant": "frameshift",
        "synonymous_variant": "synonymous",
        "frameshift_deletion": "frameshift del",
        "inframe_insertion": "in-frame ins",
        "inframe_deletion": "in-frame del",
        "coding_sequence_variant": "kodande variant",
        "feature_elongation": "feature elongation",
        "INS": "insertion",
        "DEL": "deletion",
    }
