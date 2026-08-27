"""Clinical notation and report-language contracts owned by the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ClinicalNotationContract:
    """Approved residue names and Swedish small-cardinal wording."""

    swedish_small_cardinals_common: tuple[str, ...]
    swedish_small_cardinals_neuter: tuple[str, ...]
    amino_acid_three_to_one: dict[str, str]

    @property
    def amino_acid_one_to_three(self) -> dict[str, str]:
        return {
            one_letter: three_letter
            for three_letter, one_letter in self.amino_acid_three_to_one.items()
        }


CLINICAL_NOTATION: Final = ClinicalNotationContract(
    swedish_small_cardinals_common=(
        "noll",
        "en",
        "två",
        "tre",
        "fyra",
        "fem",
        "sex",
        "sju",
        "åtta",
        "nio",
        "tio",
        "elva",
        "tolv",
    ),
    swedish_small_cardinals_neuter=(
        "noll",
        "ett",
        "två",
        "tre",
        "fyra",
        "fem",
        "sex",
        "sju",
        "åtta",
        "nio",
        "tio",
        "elva",
        "tolv",
    ),
    amino_acid_three_to_one={
        "Ala": "A",
        "Arg": "R",
        "Asn": "N",
        "Asp": "D",
        "Cys": "C",
        "Gln": "Q",
        "Glu": "E",
        "Gly": "G",
        "His": "H",
        "Ile": "I",
        "Leu": "L",
        "Lys": "K",
        "Met": "M",
        "Phe": "F",
        "Pro": "P",
        "Ser": "S",
        "Thr": "T",
        "Trp": "W",
        "Tyr": "Y",
        "Val": "V",
        "Ter": "*",
    },
)
