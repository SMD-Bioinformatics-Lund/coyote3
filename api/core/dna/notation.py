"""DNA notation helpers shared by API routes/services."""

from __future__ import annotations

import re


_AA_3_TO_1 = {
    "Cys": "C",
    "Asp": "D",
    "Ser": "S",
    "Gln": "Q",
    "Lys": "K",
    "Ile": "I",
    "Pro": "P",
    "Thr": "T",
    "Phe": "F",
    "Asn": "N",
    "Gly": "G",
    "His": "H",
    "Leu": "L",
    "Arg": "R",
    "Trp": "W",
    "Ala": "A",
    "Val": "V",
    "Glu": "E",
    "Tyr": "Y",
    "Met": "M",
    "Ter": "*",
}
_AA_PATTERN = re.compile("|".join(_AA_3_TO_1.keys()))


def one_letter_p(value: str | None) -> str:
    """Convert 3-letter protein notation to 1-letter notation."""
    if not value:
        return ""
    return _AA_PATTERN.sub(lambda m: _AA_3_TO_1[m.group()], value)


def standard_hgvs(value: str | None) -> str:
    """Normalize HGVS by wrapping version with parentheses."""
    if not value:
        return ""
    parts = value.rsplit(".", 1)
    if len(parts) == 2:
        return f"{parts[0]}.({parts[1]})"
    return value

