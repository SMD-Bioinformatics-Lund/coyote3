#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
DNA workflow service facade.

This module centralizes DNA workflow orchestration used by blueprint routes,
while preserving existing behavior and route contracts.
"""

from api.services.reporting.report_paths import build_report_file_location
from api.services.reporting.pipeline import (
    prepare_report_output as prepare_shared_report_output,
    persist_report_and_snapshot as persist_shared_report_and_snapshot,
)
from api.services.dna.dna_reporting import build_dna_report_payload
from api.services.workflow.contracts import validate_report_inputs_warn_only


class DNAWorkflowService:
    @staticmethod
    def validate_report_inputs(logger, sample: dict, assay_config: dict) -> None:
        """
        Warn-only report contract validation wrapper for DNA routes.
        """
        validate_report_inputs_warn_only(logger, sample, assay_config, analyte="dna")

    @staticmethod
    def build_report_location(sample: dict, assay_config: dict, reports_base_path: str) -> tuple[str, str, str]:
        """
        Build report id/path/file location for DNA save flow.
        """
        assay_group = assay_config.get("asp_group", "unknown")
        return build_report_file_location(
            sample=sample,
            assay_config=assay_config,
            default_assay_group=assay_group,
            reports_base_path=reports_base_path,
        )

    @staticmethod
    def build_report_payload(sample: dict, assay_config: dict, save: int, include_snapshot: bool):
        """
        Build DNA report payload through shared services.
        """
        return build_dna_report_payload(
            sample=sample,
            assay_config=assay_config,
            save=save,
            include_snapshot=include_snapshot,
        )

    @staticmethod
    def prepare_report_output(report_path: str, report_file: str, logger=None) -> None:
        """
        Prepare report output destination (mkdir + conflict check).
        """
        prepare_shared_report_output(report_path, report_file, logger=logger)

    @staticmethod
    def persist_report(
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
        """
        Persist DNA report artifacts via shared reporting pipeline.
        """
        return persist_shared_report_and_snapshot(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
        )
