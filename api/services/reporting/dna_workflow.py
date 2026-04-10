"""Shared DNA workflow orchestration for reporting routes."""

from api.core.reporting.report_paths import build_report_file_location
from api.core.workflows.contracts import validate_report_inputs
from api.services.reporting.dna_report_payload import build_dna_report_payload
from api.services.reporting.persistence import (
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from api.services.reporting.persistence import (
    prepare_report_output as prepare_shared_report_output,
)


class DNAWorkflowService:
    """Coordinate shared DNA reporting workflow steps."""

    @classmethod
    def from_store(cls, store) -> "DNAWorkflowService":
        """Build the workflow service from the shared store."""
        return cls(
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            variant_handler=store.variant_handler,
            blacklist_handler=store.blacklist_handler,
            sample_handler=store.sample_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            biomarker_handler=store.biomarker_handler,
            translocation_handler=store.translocation_handler,
            vep_metadata_handler=store.vep_metadata_handler,
            annotation_handler=store.annotation_handler,
            reported_variant_handler=store.reported_variant_handler,
        )

    def __init__(
        self,
        *,
        assay_panel_handler,
        gene_list_handler,
        variant_handler,
        blacklist_handler,
        sample_handler,
        copy_number_variant_handler,
        biomarker_handler,
        translocation_handler,
        vep_metadata_handler,
        annotation_handler,
        reported_variant_handler,
    ) -> None:
        """Create the workflow service with explicit injected handlers."""
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.variant_handler = variant_handler
        self.blacklist_handler = blacklist_handler
        self.sample_handler = sample_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.biomarker_handler = biomarker_handler
        self.translocation_handler = translocation_handler
        self.vep_metadata_handler = vep_metadata_handler
        self.annotation_handler = annotation_handler
        self.reported_variant_handler = reported_variant_handler

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
            assay_panel_handler=self.assay_panel_handler,
            gene_list_handler=self.gene_list_handler,
            variant_handler=self.variant_handler,
            blacklist_handler=self.blacklist_handler,
            sample_handler=self.sample_handler,
            copy_number_variant_handler=self.copy_number_variant_handler,
            biomarker_handler=self.biomarker_handler,
            translocation_handler=self.translocation_handler,
            vep_metadata_handler=self.vep_metadata_handler,
            annotation_handler=self.annotation_handler,
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
    ) -> str:
        """Persist DNA report artifacts through the shared reporting pipeline."""
        return persist_shared_report_and_snapshot(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
            sample_handler=self.sample_handler,
            reported_variant_handler=self.reported_variant_handler,
        )
