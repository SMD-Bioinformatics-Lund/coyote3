# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Clinical notation and report-language contracts owned by the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from coyote.config.factory_defaults import factory_value


@dataclass(frozen=True)
class ClinicalNotationContract:
    """Approved residue names and Swedish small-cardinal wording."""

    swedish_small_cardinals_common: tuple[str, ...]
    swedish_small_cardinals_neuter: tuple[str, ...]
    amino_acid_three_to_one: dict[str, str]

    @property
    def amino_acid_one_to_three(self) -> dict[str, str]:
        """Return a fresh mapping from one-letter to three-letter amino-acid codes."""
        return {
            one_letter: three_letter
            for three_letter, one_letter in self.amino_acid_three_to_one.items()
        }


CLINICAL_NOTATION: Final = ClinicalNotationContract(
    swedish_small_cardinals_common=tuple(factory_value("notation.swedish_small_cardinals_common")),
    swedish_small_cardinals_neuter=tuple(factory_value("notation.swedish_small_cardinals_neuter")),
    amino_acid_three_to_one=factory_value("notation.amino_acid_three_to_one"),
)
