# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve CNV gene boundaries consistently for analysis and reporting."""

from __future__ import annotations

from typing import Any

from coyote.domain.common.assay_filters import get_sample_effective_genes
from coyote.domain.common.sample_filters import merged_dna_cnv_filters
from pydantic import BaseModel, ConfigDict


class CnvGeneScope(BaseModel):
    """Effective CNV genes with an explicit unrestricted/empty distinction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    genes: tuple[str, ...]
    restricted: bool

    @classmethod
    def resolve(
        cls,
        sample: dict[str, Any],
        panel: dict[str, Any],
        selected_lists: dict[str, Any],
    ) -> CnvGeneScope:
        """Resolve selected CNV lists, then panel genes, then an unrestricted scope.

        Args:
            sample: Sample with its merged, canonical analysis filters.
            panel: Applied assay panel; absent covered genes impose no CNV boundary.
            selected_lists: Released documents for the explicitly selected CNV lists.

        Returns:
            Selected eligible genes and whether a gene restriction applies. An
            empty, inactive or unavailable selected list remains restrictive.
            Target-specific ad hoc selections follow the same rules.
        """
        lists, genes = get_sample_effective_genes(sample, panel, selected_lists, target="cnv")
        filters = merged_dna_cnv_filters(sample.get("filters") or {})
        return cls(
            genes=tuple(sorted(genes)),
            restricted=bool(panel.get("covered_genes") or filters.get("cnvlists") or lists),
        )
