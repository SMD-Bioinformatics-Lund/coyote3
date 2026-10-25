"""Pure reporting helpers shared by domain workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from coyote3.config.contracts.notation import CLINICAL_NOTATION

TIER_NAME: dict[int, str] = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}

TIER_SHORT_DESC: dict[int, str] = {
    0: "None",
    1: "Stark klinisk signifikans",
    2: "Potentiell klinisk signifikans",
    3: "Oklar klinisk signifikans",
    4: "Benign/sannolikt benign",
}

TIER_DESC: dict[int, str] = {
    0: "None",
    1: "Variant av stark klinisk signifikans",
    2: "Variant av potentiell klinisk signifikans",
    3: "Variant av oklar klinisk signifikans",
    4: "Variant bedömd som benign eller sannolikt benign",
}

TIER_SUMMARY_LABELS: dict[int, str] = {
    1: " av stark klinisk signifikans (Tier I)",
    2: " av potentiell klinisk signifikans (Tier II)",
    3: " av oklar klinisk signifikans (Tier III)",
    4: " av benign/sannolikt benign (Tier IV)",
}

STANDARD_TIER_SUMMARY_PHRASES: dict[str, Any] = {
    "first_prefix": "Vid analysen finner man ",
    "next_prefix": "Vidare ses ",
    "final_prefix": "Slutligen ses ",
    "number_gender": "n",
    "finding_singular": "mutation",
    "finding_plural_suffix": "er",
    "tier_labels": {str(tier): label for tier, label in TIER_SUMMARY_LABELS.items()},
    "single_gene_prefix": " i ",
    "multiple_gene_prefix": ": ",
    "gene_count_joiner": " i ",
    "value_open": " (",
    "value_close": ")",
    "read_context_prefix": "i ",
    "read_context_suffix": " av läsningarna",
    "multiple_gene_read_prefix_tiers": [1],
    "respectively": "respektive",
    "gene_joiner": "och",
    "sentence_suffix": ". ",
    "single_gene_always_read_context": False,
}

VARIANT_CLASS_TRANSLATION: dict[str, str] = {
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


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def nl_num(i: int, gender: str) -> Any | str:
    """Return Swedish words for small numbers used in report summaries."""
    names = (
        CLINICAL_NOTATION.swedish_small_cardinals_neuter
        if gender == "t"
        else CLINICAL_NOTATION.swedish_small_cardinals_common
    )
    if 0 <= i < len(names):
        return names[i]
    return str(i)


def nl_join(arr: list[str], joiner: str) -> str:
    """Join text fragments with a natural-language conjunction."""
    if len(arr) == 1:
        return arr[0]
    if len(arr) == 2:
        return f"{arr[0]} {joiner} {arr[1]}"
    if len(arr) > 2:
        last = arr[-1]
        return f"{', '.join(arr[:-1])} {joiner} {last}"
    return ""
