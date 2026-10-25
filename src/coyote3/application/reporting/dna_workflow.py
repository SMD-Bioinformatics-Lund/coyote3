"""Common DNA workflow orchestration for reporting routes."""

from collections.abc import Callable

from coyote3.application.query_rules.service import QueryRuleService
from coyote3.application.reporting.clinical_rules.service import ClinicalRuleService
from coyote3.application.reporting.dna_report_payload import build_dna_report_payload
from coyote3.application.reporting.persistence import (
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from coyote3.application.reporting.persistence import (
    prepare_report_output as prepare_shared_report_output,
)
from coyote3.application.reporting.report_paths import build_report_file_location
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from coyote3.domain.validation.contracts import validate_report_inputs


class DNAWorkflowService:
    """Coordinate common DNA reporting workflow steps."""

    @classmethod
    def from_store(cls, store, *, plot_reader: Callable[[str], str | bool]) -> "DNAWorkflowService":
        """Bind reporting repositories and an explicit registered-artifact reader.

        Args:
            store: Initialized reporting and clinical repositories.
            plot_reader: Reads a registered image path as base64, or returns False
                when the path is absent or not a file.

        Returns:
            Workflow service using the supplied storage capabilities.
        """
        return cls(
            plot_reader=plot_reader,
            assay_panel_repository=store.assay_panel_repository,
            gene_list_repository=store.gene_list_repository,
            variant_repository=store.variant_repository,
            blacklist_repository=store.blacklist_repository,
            sample_repository=store.sample_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            biomarker_repository=store.biomarker_repository,
            translocation_repository=store.translocation_repository,
            pgx_repository=store.pgx_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            annotation_repository=store.annotation_repository,
            reported_variant_repository=store.reported_variant_repository,
            report_repository=store.report_repository,
            clinical_rule_service=ClinicalRuleService.from_store(store),
            query_rule_service=QueryRuleService.from_store(store),
        )

    def __init__(
        self,
        *,
        plot_reader: Callable[[str], str | bool],
        assay_panel_repository,
        gene_list_repository,
        variant_repository,
        blacklist_repository,
        sample_repository,
        copy_number_variant_repository,
        biomarker_repository,
        translocation_repository,
        vep_metadata_repository,
        annotation_repository,
        reported_variant_repository,
        report_repository,
        pgx_repository=None,
        clinical_rule_service=None,
        query_rule_service=None,
    ) -> None:
        """Bind report repositories and the mounted-artifact reader.

        Args:
            plot_reader: Reads registered plot paths; missing files return False.
            assay_panel_repository: Assay eligibility definitions.
            gene_list_repository: Gene-list definitions.
            variant_repository: Small-variant reads and review state.
            blacklist_repository: Exclusion annotations for clinical findings.
            sample_repository: Sample metadata and atomic report persistence.
            copy_number_variant_repository: Copy-number findings and review state.
            biomarker_repository: Sample biomarker measurements.
            translocation_repository: Structural rearrangement findings.
            vep_metadata_repository: Versioned consequence and display vocabularies.
            annotation_repository: Shared clinical classifications and comments.
            reported_variant_repository: Stored finding snapshots from approved reports.
            report_repository: Report numbering and saved report metadata.
            pgx_repository: Optional pharmacogenomic measurements.
            clinical_rule_service: Optional governed reporting-rule resolver.
            query_rule_service: Optional governed finding-query policy resolver.
        """
        self.plot_reader = plot_reader
        self.assay_panel_repository = assay_panel_repository
        self.gene_list_repository = gene_list_repository
        self.variant_repository = variant_repository
        self.blacklist_repository = blacklist_repository
        self.sample_repository = sample_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.biomarker_repository = biomarker_repository
        self.translocation_repository = translocation_repository
        self.pgx_repository = pgx_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.annotation_repository = annotation_repository
        self.reported_variant_repository = reported_variant_repository
        self.report_repository = report_repository
        self.clinical_rule_service = clinical_rule_service
        self.query_rule_service = query_rule_service

    def next_report_num(self, sample_id: str) -> int:
        """Return the next sequential report number for a sample."""
        return self.report_repository.next_report_num(sample_id)

    @staticmethod
    def validate_report_inputs(logger, sample: dict, assay_config: dict) -> None:
        """Validate DNA report prerequisites before building output."""
        validate_report_inputs(logger, sample, assay_config, analyte="dna")

    @staticmethod
    def build_report_location(
        sample: dict, assay_config: dict, reports_base_path: str
    ) -> tuple[str, str, str]:
        """Build report identifiers and output paths for DNA reports."""
        assay_group = assay_config.get("asp_group", "unknown")
        return build_report_file_location(
            sample=sample,
            assay_config=assay_config,
            default_assay_group=assay_group,
            reports_base_path=reports_base_path,
        )

    def build_report_payload(
        self,
        sample: dict,
        assay_config: dict,
        save: int,
        include_snapshot: bool,
        clinical_rule_override: ClinicalRuleSetDoc | None = None,
        clinical_rule_only: bool = False,
        clinical_rule_condition_trace: bool = False,
    ):
        """Build the DNA report payload and optional snapshot rows."""
        return build_dna_report_payload(
            plot_reader=self.plot_reader,
            sample=sample,
            assay_config=assay_config,
            save=save,
            include_snapshot=include_snapshot,
            assay_panel_repository=self.assay_panel_repository,
            gene_list_repository=self.gene_list_repository,
            variant_repository=self.variant_repository,
            blacklist_repository=self.blacklist_repository,
            sample_repository=self.sample_repository,
            copy_number_variant_repository=self.copy_number_variant_repository,
            biomarker_repository=self.biomarker_repository,
            translocation_repository=self.translocation_repository,
            pgx_repository=self.pgx_repository,
            vep_metadata_repository=self.vep_metadata_repository,
            annotation_repository=self.annotation_repository,
            clinical_rule_service=self.clinical_rule_service,
            query_rule_service=self.query_rule_service,
            clinical_rule_override=clinical_rule_override,
            clinical_rule_only=clinical_rule_only,
            clinical_rule_condition_trace=clinical_rule_condition_trace,
        )

    @staticmethod
    def prepare_report_output(report_path: str, report_file: str, logger=None) -> None:
        """Prepare the DNA report output destination."""
        prepare_shared_report_output(report_path, report_file, logger=logger)

    def persist_report(
        self,
        *,
        sample_id: str,
        sample: dict,
        report_num: int,
        report_id: str,
        report_file: str,
        html: str,
        snapshot_rows: list | None,
        created_by: str,
        rule_provenance: dict | None = None,
        resolution_snapshot: dict | None = None,
    ) -> tuple[str, str]:
        """Persist DNA report artifacts through the common reporting pipeline."""
        return persist_shared_report_and_snapshot(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
            rule_provenance=rule_provenance,
            resolution_snapshot=resolution_snapshot,
            sample_repository=self.sample_repository,
        )
