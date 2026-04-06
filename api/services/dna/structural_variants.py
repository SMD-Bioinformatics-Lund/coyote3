"""DNA structural route workflow service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.dna.cnvqueries import build_cnv_query
from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.core.dna.translocqueries import build_transloc_query
from api.http import api_error, get_formatted_assay_config


class DnaStructuralService:
    """Provide DNA structural-variant workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "DnaStructuralService":
        """Build the service from the shared store."""
        return cls(
            copy_number_variant_handler=store.copy_number_variant_handler,
            translocation_handler=store.translocation_handler,
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            bam_record_handler=store.bam_record_handler,
            vep_metadata_handler=store.vep_metadata_handler,
        )

    def __init__(
        self,
        *,
        copy_number_variant_handler: Any,
        translocation_handler: Any,
        assay_panel_handler: Any,
        gene_list_handler: Any,
        bam_record_handler: Any,
        vep_metadata_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.copy_number_variant_handler = copy_number_variant_handler
        self.translocation_handler = translocation_handler
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.bam_record_handler = bam_record_handler
        self.vep_metadata_handler = vep_metadata_handler

    def load_cnvs_for_sample(
        self,
        *,
        sample: dict,
        sample_filters: dict,
        filter_genes: list[str],
    ) -> list[dict]:
        """Load CNVs for a sample using the active filters.

        Args:
            sample: Sample payload to inspect.
            sample_filters: Active sample filters.
            filter_genes: Effective genes selected for the sample.

        Returns:
            list[dict]: Filtered CNV documents for the sample.
        """
        cnv_query = build_cnv_query(
            str(sample["_id"]),
            filters={
                **sample_filters,
                "filter_genes": filter_genes,
            },
        )
        cnvs = list(self.copy_number_variant_handler.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def list_cnvs_payload(self, *, request, sample: dict, util_module) -> dict[str, Any]:
        """Return the CNV list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.
            util_module: Shared utility module used by the route layer.

        Returns:
            dict[str, Any]: CNV list payload for the UI.
        """
        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")

        sample = util_module.common.merge_sample_settings_with_assay_config(sample, assay_config)
        sample_filters = deepcopy(sample.get("filters", {}))
        assay_panel_doc = self.assay_panel_handler.get_asp(asp_name=sample.get("assay"))
        checked_cnv_genelists = sample_filters.get("cnv_genelists", [])
        checked_cnv_genelists_genes_dict = self.gene_list_handler.get_isgl_by_ids(
            checked_cnv_genelists
        )
        _genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
            sample, assay_panel_doc, checked_cnv_genelists_genes_dict
        )
        cnvs = self.load_cnvs_for_sample(
            sample=sample,
            sample_filters=sample_filters,
            filter_genes=filter_genes,
        )
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "profile": sample.get("profile"),
            },
            "meta": {"request_path": request.url.path, "count": len(cnvs)},
            "filters": sample_filters,
            "cnvs": cnvs,
        }

    def show_cnv_payload(self, *, sample: dict, cnv_id: str, util_module) -> dict[str, Any]:
        """Return the detail payload for a single CNV.

        Args:
            sample: Sample payload owning the CNV.
            cnv_id: CNV identifier to load.
            util_module: Shared utility module used by the route layer.

        Returns:
            dict[str, Any]: CNV detail payload for the UI.
        """
        cnv = self.copy_number_variant_handler.get_cnv(cnv_id)
        if not cnv:
            raise api_error(404, "CNV not found")
        cnv_sample_id = cnv.get("SAMPLE_ID") or cnv.get("sample_id")
        if cnv_sample_id and str(cnv_sample_id) != str(sample.get("_id")):
            raise api_error(404, "CNV not found for sample")
        if not cnv_sample_id:
            sample_cnvs = list(
                self.copy_number_variant_handler.get_sample_cnvs(
                    {"SAMPLE_ID": str(sample.get("_id"))}
                )
            )
            sample_cnv_ids = {str(doc.get("_id")) for doc in sample_cnvs}
            if str(cnv.get("_id")) not in sample_cnv_ids:
                raise api_error(404, "CNV not found for sample")

        assay_config = get_formatted_assay_config(sample)
        assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        return {
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "assay_group": assay_group,
            },
            "cnv": cnv,
            "annotations": self.copy_number_variant_handler.get_cnv_annotations(cnv),
            "sample_ids": sample_ids,
            "bam_id": self.bam_record_handler.get_bams(sample_ids),
            "has_hidden_comments": self.copy_number_variant_handler.hidden_cnv_comments(cnv_id),
            "hidden_comments": self.copy_number_variant_handler.hidden_cnv_comments(cnv_id),
            "assay_group": assay_group,
        }

    def set_cnv_flag(self, *, cnv_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single CNV."""
        if flag == "interesting":
            if apply:
                self.copy_number_variant_handler.mark_interesting_cnv(cnv_id)
            else:
                self.copy_number_variant_handler.unmark_interesting_cnv(cnv_id)
            return
        if flag == "false_positive":
            if apply:
                self.copy_number_variant_handler.mark_false_positive_cnv(cnv_id)
            else:
                self.copy_number_variant_handler.unmark_false_positive_cnv(cnv_id)
            return
        if flag == "noteworthy":
            if apply:
                self.copy_number_variant_handler.noteworthy_cnv(cnv_id)
            else:
                self.copy_number_variant_handler.unnoteworthy_cnv(cnv_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def set_cnv_comment_hidden(self, *, cnv_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a CNV comment."""
        if hidden:
            self.copy_number_variant_handler.hide_cnvs_comment(cnv_id, comment_id)
            return
        self.copy_number_variant_handler.unhide_cnvs_comment(cnv_id, comment_id)

    def list_translocations_payload(self, *, request, sample: dict) -> dict[str, Any]:
        """Return the translocation list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.

        Returns:
            dict[str, Any]: Translocation list payload for the UI.
        """
        translocs = list(
            self.translocation_handler.get_sample_translocations(
                build_transloc_query(str(sample["_id"]))
            )
        )
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "profile": sample.get("profile"),
            },
            "meta": {"request_path": request.url.path, "count": len(translocs)},
            "translocations": translocs,
        }

    def show_translocation_payload(
        self, *, sample: dict, transloc_id: str, util_module
    ) -> dict[str, Any]:
        """Return the detail payload for a single translocation.

        Args:
            sample: Sample payload owning the translocation.
            transloc_id: Translocation identifier to load.
            util_module: Shared utility module used by the route layer.

        Returns:
            dict[str, Any]: Translocation detail payload for the UI.
        """
        transloc = self.translocation_handler.get_transloc(transloc_id)
        if not transloc:
            raise api_error(404, "Translocation not found")
        transloc_sample_id = transloc.get("SAMPLE_ID") or transloc.get("sample_id")
        if transloc_sample_id and str(transloc_sample_id) != str(sample.get("_id")):
            raise api_error(404, "Translocation not found for sample")
        if not transloc_sample_id:
            sample_translocs = list(
                self.translocation_handler.get_sample_translocations(
                    sample_id=str(sample.get("_id"))
                )
            )
            sample_transloc_ids = {str(doc.get("_id")) for doc in sample_translocs}
            if str(transloc.get("_id")) not in sample_transloc_ids:
                raise api_error(404, "Translocation not found for sample")

        assay_config = get_formatted_assay_config(sample)
        assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        return {
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "assay_group": assay_group,
            },
            "translocation": transloc,
            "annotations": self.translocation_handler.get_transloc_annotations(transloc),
            "sample_ids": sample_ids,
            "bam_id": self.bam_record_handler.get_bams(sample_ids),
            "vep_conseq_translations": self.vep_metadata_handler.get_conseq_translations(
                sample.get("vep", 103)
            ),
            "has_hidden_comments": self.translocation_handler.hidden_transloc_comments(transloc_id),
            "hidden_comments": self.translocation_handler.hidden_transloc_comments(transloc_id),
            "assay_group": assay_group,
        }

    def set_translocation_flag(self, *, transloc_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single translocation."""
        if flag == "interesting":
            if apply:
                self.translocation_handler.mark_interesting_transloc(transloc_id)
            else:
                self.translocation_handler.unmark_interesting_transloc(transloc_id)
            return
        if flag == "false_positive":
            if apply:
                self.translocation_handler.mark_false_positive_transloc(transloc_id)
            else:
                self.translocation_handler.unmark_false_positive_transloc(transloc_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def set_translocation_comment_hidden(
        self, *, transloc_id: str, comment_id: str, hidden: bool
    ) -> None:
        """Hide or unhide a translocation comment."""
        if hidden:
            self.translocation_handler.hide_transloc_comment(transloc_id, comment_id)
            return
        self.translocation_handler.unhide_transloc_comment(transloc_id, comment_id)
