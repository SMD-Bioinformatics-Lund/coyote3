"""DNA notation helpers used by API routes/services."""

from __future__ import annotations

import re

from api.config.contracts.notation import CLINICAL_NOTATION

_AA_THREE_TO_ONE_PATTERN = re.compile(
    "|".join(re.escape(code) for code in CLINICAL_NOTATION.amino_acid_three_to_one)
)
_HGVS_ONE_LETTER_PROTEIN_PATTERN = re.compile(
    r"(?P<source>(?<=p\.)[ACDEFGHIKLMNPQRSTVWY*](?=\d))"
    r"|(?P<target>(?<=\d)[ACDEFGHIKLMNPQRSTVWY*](?=$|[?=)]))"
)


def one_letter_p(value: str | None) -> str:
    """Convert 3-letter protein notation to 1-letter notation."""
    if not value:
        return ""
    return _AA_THREE_TO_ONE_PATTERN.sub(
        lambda m: CLINICAL_NOTATION.amino_acid_three_to_one[m.group()], value
    )


def three_letter_p(value: str | None) -> str:
    """Convert simple one-letter HGVS protein substitutions to three-letter notation.

    Complex or non-standard HGVS expressions are preserved rather than guessed.
    """
    if not value:
        return ""

    def replace(match: re.Match[str]) -> str:
        residue = match.group("source") or match.group("target")
        return CLINICAL_NOTATION.amino_acid_one_to_three[residue]

    return _HGVS_ONE_LETTER_PROTEIN_PATTERN.sub(replace, value)


def standard_hgvs(value: str | None) -> str:
    """Normalize HGVS by wrapping version with parentheses."""
    if not value:
        return ""
    parts = value.rsplit(".", 1)
    if len(parts) == 2:
        return f"{parts[0]}.({parts[1]})"
    return value
