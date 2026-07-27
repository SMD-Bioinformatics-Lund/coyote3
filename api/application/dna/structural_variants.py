"""DNA structural route workflow service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.common.pagination import paginate_items, request_pagination
from api.application.common.table_state import (
    numeric_value,
    parse_sort_specs,
    search_items,
    sort_items,
    sort_spec_to_query_value,
    sortable_text,
)
from api.config.database_versions import require_sample_vep_version
from api.domain.common.errors import api_error, setup_error
from api.domain.common.sample_filters import merged_dna_cnv_filters
from api.domain.core.dna.cnvqueries import build_cnv_query
from api.domain.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.domain.core.dna.translocqueries import build_transloc_query


def _cnv_copy_number(cnv: dict[str, Any]) -> float | None:
    ratio = numeric_value(cnv.get("ratio"))
    if ratio is None:
        return None
    return 2 * (2**ratio)


def _cnv_gene_text(cnv: dict[str, Any]) -> str:
    genes = cnv.get("genes") or []
    if not isinstance(genes, list):
        return ""
    return " ".join(str(gene.get("gene", "")) for gene in genes if isinstance(gene, dict))


def _cnv_sort_value(cnv: dict[str, Any], sort_by: str) -> Any:
    sort_map = {
        "genes": lambda: sortable_text(_cnv_gene_text(cnv)),
        "region": lambda: (
            sortable_text(cnv.get("chr")),
            numeric_value(cnv.get("start")) or 0,
            numeric_value(cnv.get("end")) or 0,
        ),
        "callers": lambda: sortable_text(
            ", ".join(cnv.get("callers", []))
            if isinstance(cnv.get("callers"), list)
            else cnv.get("callers")
        ),
        "copy_number": lambda: _cnv_copy_number(cnv),
        "status_artefact": lambda: sortable_text(
            " ".join(
                str(value)
                for value in (cnv.get("fp"), cnv.get("interesting"), cnv.get("noteworthy"))
            )
        ),
    }
    builder = sort_map.get(sort_by)
    return builder() if builder else None


def _cnv_search_text(cnv: dict[str, Any]) -> str:
    values = [
        cnv.get("_id"),
        cnv.get("chr"),
        cnv.get("start"),
        cnv.get("end"),
        cnv.get("ratio"),
        cnv.get("callers"),
        _cnv_gene_text(cnv),
    ]
    return " ".join(str(value) for value in values if value not in (None, ""))


def _translocation_genes(translocation: dict[str, Any]) -> list[str]:
    genes = translocation.get("genes")
    if isinstance(genes, list):
        return [str(gene) for gene in genes if gene]
    gene1 = translocation.get("gene1") or translocation.get("GENE1")
    gene2 = translocation.get("gene2") or translocation.get("GENE2")
    return [str(gene) for gene in (gene1, gene2) if gene]


def _translocation_sort_value(translocation: dict[str, Any], sort_by: str) -> Any:
    genes = _translocation_genes(translocation)
    annotations = translocation.get("annotations") or []
    annotation_text = (
        " ".join(str(value) for value in annotations)
        if isinstance(annotations, list)
        else str(annotations or "")
    )
    sort_map = {
        "badges": lambda: sortable_text(
            " ".join(
                str(value) for value in (translocation.get("fp"), translocation.get("interesting"))
            )
        ),
        "gene1": lambda: sortable_text(genes[0] if len(genes) > 0 else None),
        "gene2": lambda: sortable_text(genes[1] if len(genes) > 1 else None),
        "positions": lambda: sortable_text(
            translocation.get("positions")
            or translocation.get("POS")
            or translocation.get("breakpoints")
        ),
        "type": lambda: sortable_text(translocation.get("type") or translocation.get("SVTYPE")),
        "hgvs": lambda: sortable_text(annotation_text or translocation.get("HGVS")),
        "panel": lambda: sortable_text(translocation.get("panel") or translocation.get("in_panel")),
        "tier": lambda: numeric_value(
            translocation.get("classification") or translocation.get("tier")
        ),
    }
    builder = sort_map.get(sort_by)
    return builder() if builder else None


def _translocation_search_text(translocation: dict[str, Any]) -> str:
    values = [
        translocation.get("_id"),
        translocation.get("type"),
        translocation.get("SVTYPE"),
        translocation.get("positions"),
        translocation.get("breakpoints"),
        translocation.get("HGVS"),
        " ".join(_translocation_genes(translocation)),
    ]
    return " ".join(str(value) for value in values if value not in (None, ""))


class DnaStructuralService:
    """Provide DNA structural-variant workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "DnaStructuralService":
        """Build the service from the runtime store."""
        return cls(
            copy_number_variant_repository=store.copy_number_variant_repository,
            translocation_repository=store.translocation_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            gene_list_repository=store.gene_list_repository,
            bam_record_repository=store.bam_record_repository,
            vep_metadata_repository=store.vep_metadata_repository,
        )

    def __init__(
        self,
        *,
        copy_number_variant_repository: Any,
        translocation_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: Any | None = None,
        gene_list_repository: Any,
        bam_record_repository: Any,
        vep_metadata_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.copy_number_variant_repository = copy_number_variant_repository
        self.translocation_repository = translocation_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.gene_list_repository = gene_list_repository
        self.bam_record_repository = bam_record_repository
        self.vep_metadata_repository = vep_metadata_repository

    def _get_formatted_assay_config(self, sample: dict) -> dict:
        """Resolve formatted assay config using injected repositories when available."""
        if self.assay_configuration_repository is None:
            return get_formatted_assay_config(sample)
        return get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )

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
        cnvs = list(self.copy_number_variant_repository.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def list_cnvs_payload(
        self, *, request, sample: dict, util_module, paginate: bool = True
    ) -> dict[str, Any]:
        """Return the CNV list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.
            util_module: Common utility module used by the route layer.

        Returns:
            dict[str, Any]: CNV list payload for the UI.
        """
        assay_config = self._get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during CNV loading."
                ),
            )

        if sample.get("filters") is None:
            sample = util_module.common.merge_sample_settings_with_assay_config(
                sample, assay_config
            )
        sample_filters = deepcopy(
            assay_config.get("filters", {})
            if sample.get("filters") is None
            else sample.get("filters", {})
        )
        cnv_filters = merged_dna_cnv_filters(sample_filters)
        assay_panel_doc = self.assay_panel_repository.get_asp(asp_name=sample.get("assay"))
        checked_cnvlists = cnv_filters.get("cnvlists", [])
        checked_cnvlists_genes_dict = self.gene_list_repository.get_isgl_by_ids(checked_cnvlists)
        _genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
            sample, assay_panel_doc, checked_cnvlists_genes_dict, target="cnv"
        )
        cnvs = self.load_cnvs_for_sample(
            sample=sample,
            sample_filters=cnv_filters,
            filter_genes=filter_genes,
        )
        query_params = getattr(request, "query_params", {}) or {}
        search_query = str(query_params.get("q", "")).strip()
        if search_query:
            cnvs = search_items(cnvs, search_query=search_query, text_builder=_cnv_search_text)
        sort_specs = parse_sort_specs(query_params)
        cnvs = sort_items(cnvs, specs=sort_specs, value_getter=_cnv_sort_value)
        page_cnvs = cnvs
        pagination_meta: dict[str, Any] = {
            "total": len(cnvs),
            "count": len(cnvs),
            "page_count": len(cnvs),
            "page": 1,
            "per_page": len(cnvs) or 50,
            "has_previous": False,
            "has_next": False,
        }
        if paginate:
            page, per_page = request_pagination(request)
            page_cnvs, pagination_meta = paginate_items(cnvs, page=page, per_page=per_page)
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "profile": sample.get("profile"),
                "files": deepcopy(sample.get("files") or {}),
            },
            "meta": {
                "request_path": request.url.path,
                **pagination_meta,
                "search": search_query,
                "sort": sort_spec_to_query_value(sort_specs),
            },
            "filters": sample_filters,
            "cnvs": page_cnvs,
        }

    def show_cnv_payload(self, *, sample: dict, cnv_id: str, util_module) -> dict[str, Any]:
        """Return the detail payload for a single CNV.

        Args:
            sample: Sample payload owning the CNV.
            cnv_id: CNV identifier to load.
            util_module: Common utility module used by the route layer.

        Returns:
            dict[str, Any]: CNV detail payload for the UI.
        """
        cnv = self.copy_number_variant_repository.get_cnv(cnv_id)
        if not cnv:
            raise api_error(404, "CNV not found")
        cnv_sample_id = cnv.get("SAMPLE_ID") or cnv.get("sample_id")
        if cnv_sample_id and str(cnv_sample_id) != str(sample.get("_id")):
            raise api_error(404, "CNV not found for sample")
        if not cnv_sample_id:
            sample_cnvs = list(
                self.copy_number_variant_repository.get_sample_cnvs(
                    {"SAMPLE_ID": str(sample.get("_id"))}
                )
            )
            sample_cnv_ids = {str(doc.get("_id")) for doc in sample_cnvs}
            if str(cnv.get("_id")) not in sample_cnv_ids:
                raise api_error(404, "CNV not found for sample")

        assay_config = self._get_formatted_assay_config(sample)
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
            "annotations": self.copy_number_variant_repository.get_cnv_annotations(cnv),
            "sample_ids": sample_ids,
            "bam_id": self.bam_record_repository.get_bams(sample_ids),
            "has_hidden_comments": self.copy_number_variant_repository.hidden_cnv_comments(cnv_id),
            "hidden_comments": self.copy_number_variant_repository.hidden_cnv_comments(cnv_id),
            "assay_group": assay_group,
        }

    def set_cnv_flag(self, *, cnv_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single CNV."""
        if flag == "interesting":
            if apply:
                self.copy_number_variant_repository.mark_interesting_cnv(cnv_id)
            else:
                self.copy_number_variant_repository.unmark_interesting_cnv(cnv_id)
            return
        if flag == "false_positive":
            if apply:
                self.copy_number_variant_repository.mark_false_positive_cnv(cnv_id)
            else:
                self.copy_number_variant_repository.unmark_false_positive_cnv(cnv_id)
            return
        if flag == "noteworthy":
            if apply:
                self.copy_number_variant_repository.noteworthy_cnv(cnv_id)
            else:
                self.copy_number_variant_repository.unnoteworthy_cnv(cnv_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def set_cnv_comment_hidden(self, *, cnv_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a CNV comment."""
        if hidden:
            self.copy_number_variant_repository.hide_cnvs_comment(cnv_id, comment_id)
            return
        self.copy_number_variant_repository.unhide_cnvs_comment(cnv_id, comment_id)

    def list_translocations_payload(
        self, *, request, sample: dict, paginate: bool = True
    ) -> dict[str, Any]:
        """Return the translocation list payload for a sample.

        Args:
            request: Active request used for metadata.
            sample: Sample payload to inspect.

        Returns:
            dict[str, Any]: Translocation list payload for the UI.
        """
        translocs = list(
            self.translocation_repository.get_sample_translocations(
                build_transloc_query(str(sample["_id"]))
            )
        )
        query_params = getattr(request, "query_params", {}) or {}
        search_query = str(query_params.get("q", "")).strip()
        if search_query:
            translocs = search_items(
                translocs,
                search_query=search_query,
                text_builder=_translocation_search_text,
            )
        sort_specs = parse_sort_specs(query_params)
        translocs = sort_items(
            translocs,
            specs=sort_specs,
            value_getter=_translocation_sort_value,
        )
        page_translocs = translocs
        pagination_meta: dict[str, Any] = {
            "total": len(translocs),
            "count": len(translocs),
            "page_count": len(translocs),
            "page": 1,
            "per_page": len(translocs) or 50,
            "has_previous": False,
            "has_next": False,
        }
        if paginate:
            page, per_page = request_pagination(request)
            page_translocs, pagination_meta = paginate_items(
                translocs, page=page, per_page=per_page
            )
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "profile": sample.get("profile"),
            },
            "meta": {
                "request_path": request.url.path,
                **pagination_meta,
                "search": search_query,
                "sort": sort_spec_to_query_value(sort_specs),
            },
            "translocations": page_translocs,
        }

    def show_translocation_payload(
        self, *, sample: dict, transloc_id: str, util_module
    ) -> dict[str, Any]:
        """Return the detail payload for a single translocation.

        Args:
            sample: Sample payload owning the translocation.
            transloc_id: Translocation identifier to load.
            util_module: Common utility module used by the route layer.

        Returns:
            dict[str, Any]: Translocation detail payload for the UI.
        """
        transloc = self.translocation_repository.get_transloc(transloc_id)
        if not transloc:
            raise api_error(404, "Translocation not found")
        transloc_sample_id = transloc.get("SAMPLE_ID") or transloc.get("sample_id")
        if transloc_sample_id and str(transloc_sample_id) != str(sample.get("_id")):
            raise api_error(404, "Translocation not found for sample")
        if not transloc_sample_id:
            sample_translocs = list(
                self.translocation_repository.get_sample_translocations(
                    sample_id=str(sample.get("_id"))
                )
            )
            sample_transloc_ids = {str(doc.get("_id")) for doc in sample_translocs}
            if str(transloc.get("_id")) not in sample_transloc_ids:
                raise api_error(404, "Translocation not found for sample")

        assay_config = self._get_formatted_assay_config(sample)
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
            "annotations": self.translocation_repository.get_transloc_annotations(transloc),
            "sample_ids": sample_ids,
            "bam_id": self.bam_record_repository.get_bams(sample_ids),
            "vep_conseq_translations": self.vep_metadata_repository.get_conseq_translations(
                require_sample_vep_version(sample)
            ),
            "has_hidden_comments": self.translocation_repository.hidden_transloc_comments(
                transloc_id
            ),
            "hidden_comments": self.translocation_repository.hidden_transloc_comments(transloc_id),
            "assay_group": assay_group,
        }

    def set_translocation_flag(self, *, transloc_id: str, apply: bool, flag: str) -> None:
        """Apply or remove a boolean flag on a single translocation."""
        if flag == "interesting":
            if apply:
                self.translocation_repository.mark_interesting_transloc(transloc_id)
            else:
                self.translocation_repository.unmark_interesting_transloc(transloc_id)
            return
        if flag == "false_positive":
            if apply:
                self.translocation_repository.mark_false_positive_transloc(transloc_id)
            else:
                self.translocation_repository.unmark_false_positive_transloc(transloc_id)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def set_translocation_comment_hidden(
        self, *, transloc_id: str, comment_id: str, hidden: bool
    ) -> None:
        """Hide or unhide a translocation comment."""
        if hidden:
            self.translocation_repository.hide_transloc_comment(transloc_id, comment_id)
            return
        self.translocation_repository.unhide_transloc_comment(transloc_id, comment_id)
