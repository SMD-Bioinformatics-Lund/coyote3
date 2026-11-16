# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Software-owned feature identities shared by application controls and clients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplicationModule:
    """Describe one independently available user-facing application module."""

    key: str
    control_field: str
    label: str
    description: str


APPLICATION_MODULES: tuple[ApplicationModule, ...] = (
    ApplicationModule(
        key="dna_analysis",
        control_field="dna_analysis_enabled",
        label="DNA analysis",
        description="Small variants, CNVs, translocations, HRD, MSI, TMB, and coverage.",
    ),
    ApplicationModule(
        key="rna_analysis",
        control_field="rna_analysis_enabled",
        label="RNA analysis",
        description="RNA fusion and expression analysis workflows.",
    ),
    ApplicationModule(
        key="reports",
        control_field="reports_enabled",
        label="Clinical reporting",
        description="Report preview, rendering, saving, and report retrieval.",
    ),
    ApplicationModule(
        key="variant_search",
        control_field="variant_search_enabled",
        label="Tiered variant search",
        description="Cross-sample search of tiered variants and annotation text.",
    ),
    ApplicationModule(
        key="knowledgebases",
        control_field="knowledgebases_enabled",
        label="Knowledgebases",
        description="Gene annotations and local or external knowledgebase lookups.",
    ),
    ApplicationModule(
        key="ingest_workspace",
        control_field="ingest_workspace_enabled",
        label="Ingest workspace",
        description="Manual sample-bundle upload, validation, and queue submission.",
    ),
    ApplicationModule(
        key="assay_catalog",
        control_field="assay_catalog_enabled",
        label="Assay catalog",
        description="Public assay catalog, matrix, assay genes, and gene-list views.",
    ),
)

APPLICATION_MODULE_BY_KEY = {module.key: module for module in APPLICATION_MODULES}
APPLICATION_MODULE_FIELDS = {module.control_field for module in APPLICATION_MODULES}
