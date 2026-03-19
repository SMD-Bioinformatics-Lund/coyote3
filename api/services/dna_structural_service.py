"""DNA structural route workflow service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.core.dna.query_builders import build_cnv_query
from api.http import api_error, get_formatted_assay_config
from api.repositories.dna_repository import DnaRouteRepository


class DnaStructuralService:
    """Provide dna structural workflows."""

    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or DnaRouteRepository()

    @staticmethod
    def mutation_payload(
        sample_id: str, resource: str, resource_id: str, action: str
    ) -> dict[str, Any]:
        """Handle mutation payload.

        Args:
            sample_id (str): Value for ``sample_id``.
            resource (str): Value for ``resource``.
            resource_id (str): Value for ``resource_id``.
            action (str): Value for ``action``.

        Returns:
            dict[str, Any]: The function result.
        """
        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "resource": resource,
            "resource_id": str(resource_id),
            "action": action,
            "meta": {"status": "updated"},
        }

    def load_cnvs_for_sample(
        self, *, sample: dict, sample_filters: dict, filter_genes: list[str]
    ) -> list[dict]:
        """Load cnvs for sample.

        Args:
            sample (dict): Value for ``sample``.
            sample_filters (dict): Value for ``sample_filters``.
            filter_genes (list[str]): Value for ``filter_genes``.

        Returns:
            list[dict]: The function result.
        """
        cnv_query = build_cnv_query(
            str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes}
        )
        cnvs = list(self.repository.cnv_handler.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def list_cnvs_payload(self, *, request, sample: dict, util_module) -> dict[str, Any]:
        """List cnvs payload.

        Args:
            request: Value for ``request``.
            sample (dict): Value for ``sample``.
            util_module: Value for ``util_module``.

        Returns:
            dict[str, Any]: The function result.
        """
        assay_config = get_formatted_assay_config(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")

        sample = util_module.common.merge_sample_settings_with_assay_config(sample, assay_config)
        sample_filters = deepcopy(sample.get("filters", {}))
        assay_panel_doc = self.repository.asp_handler.get_asp(asp_name=sample.get("assay"))
        checked_genelists = sample_filters.get("genelists", [])
        checked_genelists_genes_dict = self.repository.isgl_handler.get_isgl_by_ids(
            checked_genelists
        )
        _genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
            sample, assay_panel_doc, checked_genelists_genes_dict
        )
        cnvs = self.load_cnvs_for_sample(
            sample=sample, sample_filters=sample_filters, filter_genes=filter_genes
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
        """Show cnv payload.

        Args:
            sample (dict): Value for ``sample``.
            cnv_id (str): Value for ``cnv_id``.
            util_module: Value for ``util_module``.

        Returns:
            dict[str, Any]: The function result.
        """
        cnv = self.repository.cnv_handler.get_cnv(cnv_id)
        if not cnv:
            raise api_error(404, "CNV not found")
        cnv_sample_id = cnv.get("SAMPLE_ID") or cnv.get("sample_id")
        if cnv_sample_id and str(cnv_sample_id) != str(sample.get("_id")):
            raise api_error(404, "CNV not found for sample")
        if not cnv_sample_id:
            sample_cnvs = list(
                self.repository.cnv_handler.get_sample_cnvs({"SAMPLE_ID": str(sample.get("_id"))})
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
            "annotations": self.repository.cnv_handler.get_cnv_annotations(cnv),
            "sample_ids": sample_ids,
            "bam_id": self.repository.bam_service_handler.get_bams(sample_ids),
            "has_hidden_comments": self.repository.cnv_handler.hidden_cnv_comments(cnv_id),
            "hidden_comments": self.repository.cnv_handler.hidden_cnv_comments(cnv_id),
            "assay_group": assay_group,
        }

    def list_translocations_payload(self, *, request, sample: dict) -> dict[str, Any]:
        """List translocations payload.

        Args:
            request: Value for ``request``.
            sample (dict): Value for ``sample``.

        Returns:
            dict[str, Any]: The function result.
        """
        translocs = list(
            self.repository.transloc_handler.get_sample_translocations(sample_id=str(sample["_id"]))
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
        """Show translocation payload.

        Args:
            sample (dict): Value for ``sample``.
            transloc_id (str): Value for ``transloc_id``.
            util_module: Value for ``util_module``.

        Returns:
            dict[str, Any]: The function result.
        """
        transloc = self.repository.transloc_handler.get_transloc(transloc_id)
        if not transloc:
            raise api_error(404, "Translocation not found")
        transloc_sample_id = transloc.get("SAMPLE_ID") or transloc.get("sample_id")
        if transloc_sample_id and str(transloc_sample_id) != str(sample.get("_id")):
            raise api_error(404, "Translocation not found for sample")
        if not transloc_sample_id:
            sample_translocs = list(
                self.repository.transloc_handler.get_sample_translocations(
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
            "annotations": self.repository.transloc_handler.get_transloc_annotations(transloc),
            "sample_ids": sample_ids,
            "bam_id": self.repository.bam_service_handler.get_bams(sample_ids),
            "vep_conseq_translations": self.repository.vep_meta_handler.get_conseq_translations(
                sample.get("vep", 103)
            ),
            "has_hidden_comments": self.repository.transloc_handler.hidden_transloc_comments(
                transloc_id
            ),
            "hidden_comments": self.repository.transloc_handler.hidden_transloc_comments(
                transloc_id
            ),
            "assay_group": assay_group,
        }
