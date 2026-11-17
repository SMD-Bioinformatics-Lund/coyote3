# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Staged DNA report assembly with independently selected clinical evidence."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pprint import pformat
from typing import Any, Dict

from coyote.application.common.release_resources import assay_resource, gene_list_resources
from coyote.application.interpretation.annotation_enrichment import (
    add_global_annotations as shared_add_global_annotations,
)
from coyote.application.query_rules.service import effective_policy
from coyote.application.reporting.clinical_rules.preparation import (
    prepare_report_context,
    prepare_snv_profile_context,
)
from coyote.application.reporting.eligibility import (
    reportable_tiers,
    structural_report_inclusion,
)
from coyote.application.reporting.report_context import report_scope_label
from coyote.application.reporting.report_service import ReportTemplate
from coyote.application.reporting.snapshot_rows import (
    build_biomarker_snapshot_rows,
    build_cnv_snapshot_rows,
    build_pgx_snapshot_rows,
    build_translocation_snapshot_rows,
    flatten_pgx_records,
)
from coyote.config.constants import primary_analysis_file_key
from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from coyote.domain.common.assay_capabilities import normalize_analysis_sections
from coyote.domain.common.biomarkers import BIOMARKER_ANALYSES, project_biomarkers
from coyote.domain.common.reporting import (
    TIER_DESC,
    TIER_SHORT_DESC,
    VARIANT_CLASS_TRANSLATION,
)
from coyote.domain.common.sample_filters import (
    merged_dna_cnv_filters,
    merged_dna_translocation_filters,
    merged_dna_variant_filters,
    snv_filter_intents,
)
from coyote.domain.dna.dna_filters import (
    get_filter_conseq_terms as shared_get_filter_conseq_terms,
)
from coyote.domain.reporting.report_paths import (
    get_report_timestamp as shared_get_report_timestamp,
)
from coyote.domain.selection import RecordField, Selection

from .context import DnaReportState
from .selection import (
    _build_variant_query,
    _ensure_sample_filters,
    _filter_cnvs_for_report,
    _filter_translocations_for_report,
    _resolve_cnv_gene_scope,
    _resolve_disp_positions,
    _resolve_filter_genes,
    _resolve_sample_vep_version,
    _resolve_translocation_filter_genes,
    load_report_snv_findings,
)
from .snapshots import _build_snapshot_rows
from .variants import (
    filter_variants_for_report,
    get_simple_variants_for_report,
    hotspot_variant,
    sort_by_class_and_af,
)

logger = logging.getLogger(__name__)


def _sample_file_path(sample: dict[str, Any], key: str) -> str:
    """Return a sample file path from the canonical nested file contract."""
    file_doc = (
        (sample.get("files") or {}).get(key) if isinstance(sample.get("files"), dict) else None
    )
    if isinstance(file_doc, dict):
        return str(file_doc.get("path") or "")
    if isinstance(file_doc, str):
        return file_doc
    return str(sample.get(key) or "")


class DnaReportBuilder:
    """Assemble DNA evidence, clinical evaluation and snapshots in explicit stages."""

    def __init__(
        self,
        sample: dict,
        assay_config: dict,
        save: int = 0,
        include_snapshot: bool = False,
        *,
        plot_reader: Callable[[str], str | bool],
        variant_repository: Any,
        blacklist_repository: Any,
        sample_repository: Any,
        diagnosis_repository: Any,
        copy_number_variant_repository: Any,
        biomarker_repository: Any,
        translocation_repository: Any,
        vep_metadata_repository: Any,
        annotation_repository: Any,
        pgx_repository: Any = None,
        clinical_rule_service: Any = None,
        query_rule_service: Any = None,
        clinical_rule_override: ClinicalRuleSetDoc | None = None,
        clinical_rule_only: bool = False,
        clinical_rule_condition_trace: bool = False,
    ) -> None:
        """Bind report inputs and repository capabilities for one reusable builder.

        Args:
            sample: Source sample metadata; filter preparation copies it before use.
            assay_config: Resolved assay resources and reviewed reporting configuration.
            save: Existing preview/finalization display flag.
            include_snapshot: Whether to capture the exact selected findings.
            plot_reader: Registered plot reader returning embedded image data or False.
            variant_repository: Reads and hydrates small variants.
            blacklist_repository: Adds assay-specific exclusion evidence.
            sample_repository: Reads the latest visible sample comment.
            diagnosis_repository: Resolves diagnosis names for report context.
            copy_number_variant_repository: Reads copy-number findings.
            biomarker_repository: Reads measured sample biomarkers.
            translocation_repository: Reads DNA rearrangements, distinct from RNA fusions.
            vep_metadata_repository: Provides version-specific consequence metadata.
            annotation_repository: Resolves applicable clinical interpretations.
            pgx_repository: Optional pharmacogenomic measurement repository.
            clinical_rule_service: Evaluates the applicable published reporting rules.
            query_rule_service: Resolves published finding-selection policies.
            clinical_rule_override: Optional draft rule set for an explicit trial.
            clinical_rule_only: Return rule evaluation without rendered report data.
            clinical_rule_condition_trace: Include trial condition evidence when requested.
        """
        self.sample = sample
        self.assay_config = assay_config
        self.save = save
        self.include_snapshot = include_snapshot
        self.clinical_rule_override = clinical_rule_override
        self.clinical_rule_only = clinical_rule_only
        self.clinical_rule_condition_trace = clinical_rule_condition_trace
        self.plot_reader = plot_reader
        self.variant_repository = variant_repository
        self.blacklist_repository = blacklist_repository
        self.sample_repository = sample_repository
        self.diagnosis_repository = diagnosis_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.biomarker_repository = biomarker_repository
        self.translocation_repository = translocation_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.annotation_repository = annotation_repository
        self.pgx_repository = pgx_repository
        self.clinical_rule_service = clinical_rule_service
        self.query_rule_service = query_rule_service

    def build(self) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Build independent report state and return its renderer context and snapshots.

        Returns:
            Template identity, evaluated display context and selected finding snapshots.

        Raises:
            AppError: Required assay resources or clinical rules cannot be resolved.
            ValueError: Required versioned evidence is missing or invalid.
        """
        state = DnaReportState(
            sample=self.sample,
            assay_config=self.assay_config,
            save=self.save,
            include_snapshot=self.include_snapshot,
            clinical_rule_override=self.clinical_rule_override,
            clinical_rule_only=self.clinical_rule_only,
            clinical_rule_condition_trace=self.clinical_rule_condition_trace,
        )
        self._prepare(state)
        self._load_small_variants(state)
        self._load_germline_variants(state)
        self._load_copy_numbers(state)
        self._load_copy_number_profile(state)
        self._load_biomarkers(state)
        self._load_translocations(state)
        self._load_pharmacogenomics(state)
        self._evaluate_clinical_rules(state)
        if state.clinical_rule_only:
            return (
                "",
                {
                    "clinical_rule_evaluation": state.clinical_rule_evaluation.model_dump(
                        mode="json"
                    )
                    if state.clinical_rule_evaluation
                    else None
                },
                [],
            )
        return self._template_context(state)

    def _prepare(self, state: DnaReportState) -> None:
        """Resolve filters, assay context and versioned consequence metadata."""
        state.sample_assay = state.sample.get("asp_id")
        state.assay_group = state.assay_config.get("asp_group", "unknown")
        state.diagnosis = state.sample.get("diagnosis_id")
        state.report_sections = normalize_analysis_sections(
            state.assay_config.get("reporting", {}).get("report_sections", [])
        )
        state.report_sections_data = {}
        logger.debug(
            "Assay group: %s - DNA config: %s", state.assay_group, pformat(state.report_sections)
        )
        logger.debug("Assay group: %s - Diagnosis: %s", state.assay_group, state.diagnosis)
        state.assay_panel_doc = assay_resource(state.assay_config)
        state.sample, state.sample_filters = _ensure_sample_filters(
            state.sample, state.assay_config
        )
        state.active_snv_intents = snv_filter_intents(state.sample, state.assay_config)
        state.primary_snv_intent = state.active_snv_intents[0]
        state.genes_covered_in_panel, state.filter_genes = _resolve_filter_genes(
            sample=state.sample,
            sample_filters=state.sample_filters,
            assay_panel_doc=state.assay_panel_doc,
            assay_config=state.assay_config,
            intent=state.primary_snv_intent,
        )
        state.sample_vep_version = _resolve_sample_vep_version(state.sample)
        state.conseq_terms_mapper = self.vep_metadata_repository.get_consequence_group_map(
            state.sample_vep_version
        )
        state.snv_filters = merged_dna_variant_filters(
            state.sample_filters, intent=state.primary_snv_intent
        )
        state.cnv_filters = merged_dna_cnv_filters(state.sample_filters)
        state.filter_conseq = shared_get_filter_conseq_terms(
            state.snv_filters.get("vep_consequences", []), state.conseq_terms_mapper
        )
        state.disp_pos = _resolve_disp_positions(state.sample, state.assay_config)

    def _load_small_variants(self, state: DnaReportState) -> None:
        """Select the primary SNV profile and retain its interpretation snapshots."""
        query = _build_variant_query(
            query_rule_service=self.query_rule_service,
            assay_group=state.assay_group,
            sample=state.sample,
            sample_filters=state.sample_filters,
            filter_conseq=state.filter_conseq,
            filter_genes=state.filter_genes,
            disp_pos=state.disp_pos,
            restrict_to_genes=True,
            intent=state.primary_snv_intent,
        )
        state.variants = list(self.variant_repository.get_case_variants(query) or [])
        if not state.clinical_rule_only:
            state.variants = self.variant_repository.hydrate_finding_comments_many(state.variants)
        state.variants = self.blacklist_repository.add_blacklist_data(
            state.variants, state.assay_group, asp_id=state.sample["asp_id"]
        )
        state.variants, tiered_variants = shared_add_global_annotations(
            state.variants,
            state.assay_group,
            state.diagnosis,
            annotation_repository=self.annotation_repository,
            sample_context=state.assay_config["aspc_resolution"]["context"],
        )
        state.variants = hotspot_variant(state.variants)
        state.variants = filter_variants_for_report(
            state.variants,
            state.filter_genes,
            reportable_tiers(state.assay_config["reporting"], "SNV"),
            restrict_to_genes=True,
        )
        state.latest_sample_comment = (
            None
            if state.clinical_rule_only
            else self.sample_repository.get_latest_sample_comment(
                sample_id=str(state.sample["_id"])
            )
        )
        state.snapshot_rows = []
        if state.include_snapshot:
            state.snapshot_rows = _build_snapshot_rows(
                variants=state.variants,
                assay_group=state.assay_group,
                diagnosis=state.diagnosis,
                latest_sample_comment=state.latest_sample_comment,
                intent=state.primary_snv_intent,
            )
        if not state.clinical_rule_only:
            variants_simple = get_simple_variants_for_report(state.variants, state.assay_config)
            state.report_sections_data["snvs"] = sort_by_class_and_af(variants_simple)
        state.rule_sections_data = {"snvs": state.variants}

    def _load_germline_variants(self, state: DnaReportState) -> None:
        """Add the separate germline profile when enabled by assay configuration."""
        state.germline_variants = []
        if "germline" in state.active_snv_intents and state.primary_snv_intent != "germline":
            state.germline_variants = load_report_snv_findings(
                sample=state.sample,
                assay_config=state.assay_config,
                sample_filters=state.sample_filters,
                intent="germline",
                disp_pos=state.disp_pos,
                consequence_terms=lambda values: shared_get_filter_conseq_terms(
                    values, state.conseq_terms_mapper
                ),
                variant_repository=self.variant_repository,
                blacklist_repository=self.blacklist_repository,
                annotation_repository=self.annotation_repository,
                query_rule_service=self.query_rule_service,
                hydrate_comments=not state.clinical_rule_only,
            )
            if state.include_snapshot:
                state.snapshot_rows.extend(
                    _build_snapshot_rows(
                        variants=state.germline_variants,
                        assay_group=state.assay_group,
                        diagnosis=state.diagnosis,
                        latest_sample_comment=state.latest_sample_comment,
                        intent="germline",
                    )
                )
            if not state.clinical_rule_only:
                state.report_sections_data["germline_snvs"] = sort_by_class_and_af(
                    get_simple_variants_for_report(state.germline_variants, state.assay_config)
                )
            state.rule_sections_data["germline_snvs"] = state.germline_variants

    def _load_copy_numbers(self, state: DnaReportState) -> None:
        """Select reportable CNVs within the configured copy-number gene scope."""
        if "CNV" in state.report_sections:
            cnv_scope = _resolve_cnv_gene_scope(
                state.sample,
                state.sample_filters,
                state.assay_panel_doc,
                assay_config=state.assay_config,
            )
            structural_cnvs = list(
                self.copy_number_variant_repository.get_sample_cnvs(
                    Selection(criteria={RecordField.SAMPLE: str(state.sample["_id"])})
                )
                or []
            )
            structural_cnvs, _ = shared_add_global_annotations(
                structural_cnvs,
                state.assay_group,
                state.diagnosis,
                annotation_repository=self.annotation_repository,
                sample_context=state.assay_config["aspc_resolution"]["context"],
            )
            cnv_tiers = reportable_tiers(state.assay_config["reporting"], "CNV")
            state.report_sections_data["cnvs"] = _filter_cnvs_for_report(
                [row for row in structural_cnvs if structural_report_inclusion(row, cnv_tiers)],
                sample_filters=state.sample_filters,
                filter_genes=list(cnv_scope.genes),
                restricted=cnv_scope.restricted,
            )
            state.rule_sections_data["cnvs"] = state.report_sections_data["cnvs"]
            if state.include_snapshot:
                state.snapshot_rows.extend(
                    build_cnv_snapshot_rows(state.report_sections_data["cnvs"])
                )

    def _load_copy_number_profile(self, state: DnaReportState) -> None:
        """Read an enabled genomic copy-number plot for display."""
        if "CNV_PROFILE" in state.report_sections and (not state.clinical_rule_only):
            state.report_sections_data["cnv_profile_base64"] = self.plot_reader(
                _sample_file_path(state.sample, primary_analysis_file_key("dna", "CNV_PROFILE"))
            )

    def _load_biomarkers(self, state: DnaReportState) -> None:
        """Project measured biomarkers and preserve their snapshot evidence."""
        if set(state.report_sections) & set(BIOMARKER_ANALYSES):
            state.report_sections_data["biomarkers"] = project_biomarkers(
                self.biomarker_repository.get_sample_biomarkers(sample_id=str(state.sample["_id"]))
                or [],
                state.report_sections,
            )
            state.rule_sections_data["biomarkers"] = state.report_sections_data["biomarkers"]
            for analysis in BIOMARKER_ANALYSES:
                state.report_sections_data[analysis.lower()] = project_biomarkers(
                    state.report_sections_data["biomarkers"], [analysis]
                )
            if state.include_snapshot:
                state.snapshot_rows.extend(
                    build_biomarker_snapshot_rows(state.report_sections_data["biomarkers"])
                )

    def _load_translocations(self, state: DnaReportState) -> None:
        """Select DNA translocations and retain their chosen partner annotations."""
        if "TRANSLOCATION" in state.report_sections:
            translocation_filter_genes = _resolve_translocation_filter_genes(
                state.sample,
                state.sample_filters,
                state.assay_panel_doc,
                assay_config=state.assay_config,
            )
            structural_translocations = list(
                self.translocation_repository.get_sample_translocations(str(state.sample["_id"]))
                or []
            )
            structural_translocations, _ = shared_add_global_annotations(
                structural_translocations,
                state.assay_group,
                state.diagnosis,
                annotation_repository=self.annotation_repository,
                sample_context=state.assay_config["aspc_resolution"]["context"],
            )
            translocation_tiers = reportable_tiers(state.assay_config["reporting"], "TRANSLOCATION")
            state.report_sections_data["translocs"] = _filter_translocations_for_report(
                [
                    row
                    for row in structural_translocations
                    if structural_report_inclusion(row, translocation_tiers)
                ],
                filter_genes=translocation_filter_genes,
                restricted=True,
                policy=effective_policy(
                    self.query_rule_service,
                    "translocation",
                    state.sample,
                    assay_group=state.assay_group,
                ),
                settings={
                    "assay_group": state.assay_group,
                    "asp_id": state.sample.get("asp_id"),
                    "diagnosis_id": state.sample.get("diagnosis_id"),
                    "intent": "somatic",
                },
            )
            state.rule_sections_data["translocs"] = state.report_sections_data["translocs"]
            if state.include_snapshot:
                state.snapshot_rows.extend(
                    build_translocation_snapshot_rows(state.report_sections_data["translocs"])
                )

    def _load_pharmacogenomics(self, state: DnaReportState) -> None:
        """Add enabled pharmacogenomic results and snapshots."""
        if "PGX" in state.report_sections:
            state.report_sections_data["pgx"] = flatten_pgx_records(
                list(self.pgx_repository.get_sample_pgx(str(state.sample["_id"])) or [])
                if self.pgx_repository is not None
                else []
            )
            state.rule_sections_data["pgx"] = state.report_sections_data["pgx"]
            if state.include_snapshot:
                state.snapshot_rows.extend(
                    build_pgx_snapshot_rows(state.report_sections_data["pgx"])
                )

    def _evaluate_clinical_rules(self, state: DnaReportState) -> None:
        """Evaluate the report rules with selected findings and exact gene-list scope."""
        selected_list_ids = list(
            dict.fromkeys(
                [
                    *state.snv_filters.get("snvlists", []),
                    *state.cnv_filters.get("cnvlists", []),
                    *merged_dna_translocation_filters(state.sample_filters).get("fusionlists", []),
                ]
            )
        )
        selected_list_docs = gene_list_resources(state.assay_config, selected_list_ids)
        applied_gene_lists = [
            {
                **document,
                "isgl_id": isgl_id,
                "selected_for": [
                    domain
                    for domain, selected_ids in (
                        ("snv", state.snv_filters.get("snvlists", [])),
                        ("cnv", state.cnv_filters.get("cnvlists", [])),
                        (
                            "translocation",
                            merged_dna_translocation_filters(state.sample_filters).get(
                                "fusionlists", []
                            ),
                        ),
                    )
                    if isgl_id in selected_ids
                ],
            }
            for isgl_id, document in selected_list_docs.items()
        ]
        prepared_rule_context = prepare_report_context(
            sample=state.sample,
            asp=state.assay_panel_doc or {},
            aspc=state.assay_config,
            analyte="dna",
            applied_gene_lists=applied_gene_lists,
            report_sections_data=state.rule_sections_data,
            intent=state.primary_snv_intent,
        )
        intent_contexts = {}
        if state.primary_snv_intent == "germline":
            prepared_rule_context = prepare_snv_profile_context(
                sample=state.sample,
                asp=state.assay_panel_doc or {},
                aspc=state.assay_config,
                sample_filters=state.sample_filters,
                findings=state.variants,
                intent="germline",
            )
        if "germline_snvs" in state.rule_sections_data and "SNV" in state.report_sections:
            intent_contexts["germline"] = prepare_snv_profile_context(
                sample=state.sample,
                asp=state.assay_panel_doc or {},
                aspc=state.assay_config,
                sample_filters=state.sample_filters,
                findings=state.germline_variants,
                intent="germline",
            )
        evaluation_options = {"intent_contexts": intent_contexts} if intent_contexts else {}
        state.clinical_rule_evaluation = None
        if self.clinical_rule_service is not None:
            state.clinical_rule_evaluation = (
                self.clinical_rule_service.evaluate_document(
                    rule_set=state.clinical_rule_override,
                    context=prepared_rule_context,
                    include_condition_trace=state.clinical_rule_condition_trace,
                    **evaluation_options,
                )
                if state.clinical_rule_override is not None
                else self.clinical_rule_service.evaluate(
                    aspc=state.assay_config, context=prepared_rule_context, **evaluation_options
                )
            )

    def _template_context(
        self, state: DnaReportState
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Build display metadata from the completed report state."""
        vep_variant_class_meta = self.vep_metadata_repository.get_variant_class_translations(
            state.sample_vep_version
        )
        report_date = datetime.now().date()
        report_timestamp: str = shared_get_report_timestamp()
        template_context: Dict[str, Any] = {
            "report_scope_label": report_scope_label(
                state.sample, state.assay_config, self.diagnosis_repository
            ),
            "assay_config": state.assay_config,
            "report_sections": state.report_sections,
            "report_sections_data": state.report_sections_data,
            "sample": state.sample,
            "translation": VARIANT_CLASS_TRANSLATION,
            "vep_var_class_translations": vep_variant_class_meta,
            "class_desc": TIER_DESC,
            "class_desc_short": TIER_SHORT_DESC,
            "report_date": report_date,
            "report_timestamp": report_timestamp,
            "save": state.save,
            "sample_assay": state.sample_assay,
            "assay_group": state.assay_group,
            "genes_covered_in_panel": state.genes_covered_in_panel,
            "panel_doc": json.dumps(state.assay_panel_doc, default=str),
            "report_snvlists": json.dumps(state.genes_covered_in_panel, default=str),
            "report_sample_filters": json.dumps(state.sample_filters, default=str),
            "latest_sample_comment_text": str(
                (state.latest_sample_comment or {}).get("text") or ""
            ),
            "clinical_rule_evaluation": state.clinical_rule_evaluation.model_dump(mode="json")
            if state.clinical_rule_evaluation
            else None,
        }
        return (ReportTemplate.DNA.value, template_context, state.snapshot_rows)
