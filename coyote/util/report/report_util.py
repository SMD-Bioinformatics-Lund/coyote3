import os
from copy import deepcopy
from pathlib import Path
from flask import current_app as app
from typing import Any, Literal, Dict, Tuple
from datetime import datetime
import base64


class ReportUtility:
    """
    Utility class for generating and managing reports.
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
