"""Common DNA workflow orchestration for reporting routes."""

from api.application.reporting.dna_report_payload import build_dna_report_payload
from api.application.reporting.persistence import (
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from api.application.reporting.persistence import (
    prepare_report_output as prepare_shared_report_output,
)
from api.domain.core.reporting.report_paths import build_report_file_location
from api.domain.core.workflows.contracts import validate_report_inputs


class DNAWorkflowService:
    """Coordinate common DNA reporting workflow steps."""

    @classmethod
    def from_store(cls, store) -> "DNAWorkflowService":
        """Build the workflow service from the runtime store."""
        return cls(
            assay_panel_repository=store.assay_panel_repository,
            gene_list_repository=store.gene_list_repository,
            variant_repository=store.variant_repository,
            blacklist_repository=store.blacklist_repository,
            sample_repository=store.sample_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            biomarker_repository=store.biomarker_repository,
            translocation_repository=store.translocation_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            annotation_repository=store.annotation_repository,
            reported_variant_repository=store.reported_variant_repository,
        )

    def __init__(
        self,
        *,
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
    ) -> None:
        """Create the workflow service with explicit injected repositories."""
        self.assay_panel_repository = assay_panel_repository
        self.gene_list_repository = gene_list_repository
        self.variant_repository = variant_repository
        self.blacklist_repository = blacklist_repository
        self.sample_repository = sample_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.biomarker_repository = biomarker_repository
        self.translocation_repository = translocation_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.annotation_repository = annotation_repository
        self.reported_variant_repository = reported_variant_repository

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
        self, sample: dict, assay_config: dict, save: int, include_snapshot: bool
    ):
        """Build the DNA report payload and optional snapshot rows."""
        return build_dna_report_payload(
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
            vep_metadata_repository=self.vep_metadata_repository,
            annotation_repository=self.annotation_repository,
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
            sample_repository=self.sample_repository,
            reported_variant_repository=self.reported_variant_repository,
        )
