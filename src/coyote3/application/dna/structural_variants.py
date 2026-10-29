"""DNA structural route workflow service."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from itertools import batched
from typing import Any

from coyote3.application.common.alignment_files import alignment_files_payload
from coyote3.application.common.analysis_query import AnalysisQuery
from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.pagination import query_pagination
from coyote3.application.common.release_resources import assay_resource, gene_list_resources
from coyote3.application.common.table_state import (
    in_memory_sorted_page,
    numeric_value,
    parse_sort_specs,
    select_table_rows,
    sort_spec_to_query_value,
    sortable_text,
)
from coyote3.application.knowledgebase.gene_markers import cosmic_cancer_gene_map
from coyote3.application.query_rules.service import QueryRuleService, effective_policy
from coyote3.contracts.operations import OperationResult
from coyote3.domain.common.assay_filters import (
    get_case_and_control_sample_ids,
    get_sample_effective_genes,
)
from coyote3.domain.common.errors import api_error, setup_error
from coyote3.domain.common.sample_filters import (
    merge_filter_defaults,
    merged_dna_cnv_filters,
    merged_dna_translocation_filters,
)
from coyote3.domain.dna.cnv_metrics import copy_number_from_log2
from coyote3.domain.dna.cnvqueries import build_cnv_query, include_normal_cnvs
from coyote3.domain.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
)
from coyote3.domain.dna.structural_annotations import (
    annotation_key,
    snpeff_consequence_metadata,
    structural_transcript_rows,
)
from coyote3.domain.dna.structural_identity import translocation_annotation_identity
from coyote3.domain.dna.transcript_payloads import build_hgnc_lookup_maps
from coyote3.domain.dna.translocqueries import (
    build_transloc_query,
    filter_translocations_by_genes,
    translocation_genes,
)


def _cnv_copy_number(cnv: dict[str, Any]) -> float | None:
    """Convert the CNV ratio to the copy-number value used for table sorting.

    Args:
        cnv: CNV row with a ratio interpreted as a log2 value.

    Returns:
        Twice two raised to the ratio, or None when the ratio is absent or nonnumeric.

    Raises:
        OverflowError: The exponent exceeds floating-point range.
    """
    ratio = numeric_value(cnv.get("ratio"))
    if ratio is None:
        return None
    return copy_number_from_log2(ratio)


def _cnv_gene_text(cnv: dict[str, Any]) -> str:
    """Join gene names from dictionary entries in a CNV's gene list.

    Args:
        cnv: CNV row with optional list-shaped genes.

    Returns:
        Space-separated gene text, or an empty string without a gene list.
    """
    genes = cnv.get("genes") or []
    if not isinstance(genes, list):
        return ""
    return " ".join(str(gene.get("gene", "")) for gene in genes if isinstance(gene, dict))


def _cnv_sort_value(cnv: dict[str, Any], sort_by: str) -> Any:
    """Build the requested CNV table sort key.

    Args:
        cnv: CNV row with genomic, caller, status, and frequency fields.
        sort_by: genes, region, callers, copy_number, purity, sr, status, or artefact.

    Returns:
        Lowercase text, numeric value, or region tuple; None for an unsupported key.
        Both purity and copy_number use the ratio-derived copy number. Artefact uses
        the largest AFRQ_ value, defaulting to zero.

    Raises:
        OverflowError: Copy-number conversion exceeds floating-point range.
    """
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
        "purity": lambda: _cnv_copy_number(cnv),
        "sr": lambda: sortable_text(cnv.get("SR")),
        "status": lambda: sortable_text(
            " ".join(
                str(value)
                for value in (
                    cnv.get("fp"),
                    cnv.get("interesting"),
                    cnv.get("noteworthy"),
                    cnv.get("NORMAL"),
                )
            )
        ),
        "artefact": lambda: max(
            (
                numeric_value(value) or 0
                for key, value in cnv.items()
                if str(key).startswith("AFRQ_")
            ),
            default=0,
        ),
    }
    builder = sort_map.get(sort_by)
    return builder() if builder else None


def _cnv_search_text(cnv: dict[str, Any]) -> str:
    """Join CNV identity, coordinates, ratio, callers, and genes for text search.

    Args:
        cnv: CNV table row to index.

    Returns:
        Space-separated field text with None and empty strings omitted; case is preserved.
    """
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


def _translocation_sort_value(translocation: dict[str, Any], sort_by: str) -> Any:
    """Build a text or numeric sort key for a translocation table column.

    Args:
        translocation: Structural finding with genes, annotations, and display fields.
        sort_by: badges, gene1, gene2, positions, type, hgvs, panel, or tier.

    Returns:
        Lowercase text or numeric tier, with None for unsupported or unavailable values.
        Tier conversion uses classification directly when truthy, otherwise tier.
    """
    genes = translocation_genes(translocation)
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
    """Join structural finding identity, type, positions, HGVS, and genes for search.

    Args:
        translocation: Translocation table row to index.

    Returns:
        Space-separated field text with None and empty strings omitted; case is preserved.
    """
    values = [
        translocation.get("_id"),
        translocation.get("type"),
        translocation.get("SVTYPE"),
        translocation.get("positions"),
        translocation.get("breakpoints"),
        translocation.get("HGVS"),
        " ".join(translocation_genes(translocation)),
    ]
    return " ".join(str(value) for value in values if value not in (None, ""))


class DnaStructuralService:
    """Provide DNA structural-variant workflows."""

    @classmethod
    def from_store(cls, store: Any, *, page_sorter=in_memory_sorted_page) -> "DnaStructuralService":
        """Build the service from the runtime store."""
        return cls(
            page_sorter=page_sorter,
            annotation_repository=store.annotation_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            translocation_repository=store.translocation_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            gene_list_repository=store.gene_list_repository,
            bam_record_repository=store.bam_record_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            cosmic_repository=store.cosmic_repository,
            query_rule_service=QueryRuleService.from_store(store),
            hgnc_repository=getattr(store, "hgnc_repository", None),
        )

    def __init__(
        self,
        *,
        annotation_repository: Any,
        copy_number_variant_repository: Any,
        translocation_repository: Any,
        page_sorter=in_memory_sorted_page,
        assay_panel_repository: Any,
        assay_configuration_repository: Any | None = None,
        gene_list_repository: Any,
        bam_record_repository: Any,
        vep_metadata_repository: Any,
        cosmic_repository: Any,
        query_rule_service=None,
        hgnc_repository=None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.annotation_repository = annotation_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.translocation_repository = translocation_repository
        self.page_sorter = page_sorter
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.gene_list_repository = gene_list_repository
        self.bam_record_repository = bam_record_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.cosmic_repository = cosmic_repository
        self.query_rule_service = query_rule_service
        self.hgnc_repository = hgnc_repository

    def select_translocation_transcript(
        self, *, sample: dict, transloc_id: str, key: str
    ) -> OperationResult:
        """Select an embedded combination after checking sample ownership and current evidence.

        Args:
            sample: Authorized owning sample.
            transloc_id: Finding identifier.
            key: Digest identifying one stored SnpEff annotation row.

        Returns:
            Repository operation counts for the completed selection.

        Raises:
            AppError: Finding is missing or belongs to another sample, the key is
                unavailable, or annotations changed concurrently.
        """
        finding = self.translocation_repository.get_transloc(transloc_id)
        if not finding or str(finding.get("SAMPLE_ID")) != str(sample["_id"]):
            raise api_error(404, "Translocation not found for sample")
        annotations = (finding.get("INFO") or {}).get("ANN") or []
        selected = next((row for row in annotations if annotation_key(row) == key), None)
        if selected is None:
            raise api_error(422, "Requested SnpEff annotation is not available for this finding")
        result = self.translocation_repository.select_annotation(
            transloc_id, str(sample["_id"]), annotations, selected
        )
        if not result.matched_count:
            raise api_error(409, "Annotations changed; reload the finding before selecting")
        return result

    def _get_formatted_assay_config(self, sample: dict) -> dict:
        """Resolve configuration through the injected resource repositories."""
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
        assay_panel: dict | None = None,
        assay_group: str | None = None,
        stream: bool = False,
    ) -> list[dict] | Iterable[dict]:
        """Load CNVs for a sample using the active filters.

        Args:
            sample: Sample payload to inspect.
            sample_filters: Active sample filters.
            filter_genes: Effective genes selected for the sample.
            stream: Yield batches lazily for table pagination; false preserves list callers.

        Returns:
            list[dict]: Filtered CNV documents for the sample.
        """
        cnv_query = build_cnv_query(
            str(sample["_id"]),
            filters={
                **sample_filters,
                "filter_genes": filter_genes,
                "assay_group": assay_group
                or (assay_panel or {}).get("asp_group")
                or sample.get("asp_group"),
                "asp_id": sample.get("asp_id"),
                "diagnosis_id": sample.get("diagnosis_id"),
                "intent": "somatic",
            },
            include_normal=include_normal_cnvs(sample, assay_panel),
            policy=effective_policy(
                self.query_rule_service,
                "cnv",
                sample,
                assay_group=assay_group or (assay_panel or {}).get("asp_group"),
            ),
        )
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))

        def rows() -> Iterable[dict]:
            """Normalize filtered CNVs in bounded batches without changing source order."""
            for batch in batched(
                self.copy_number_variant_repository.get_sample_cnvs(cnv_query, stream=True), 100
            ):
                cnvs = list(batch)
                if filter_cnveffects:
                    cnvs = cnvtype_variant(cnvs, filter_cnveffects)
                yield from cnv_organizegenes(cnvs)

        return rows() if stream else list(rows())

    def list_cnvs_payload(
        self, *, query: AnalysisQuery, sample: dict, paginate: bool = True
    ) -> dict[str, Any]:
        """Return the CNV list payload for a sample.

        Args:
            query: Active query used for metadata.
            sample: Sample payload to inspect.

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

        sample_filters = merge_filter_defaults(
            sample.get("filters"),
            assay_config.get("filters"),
            asp_category=str(sample.get("asp_category") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
        )
        cnv_filters = merged_dna_cnv_filters(sample_filters)
        sample = {**sample, "filters": sample_filters}
        assay_panel_doc = assay_resource(assay_config)
        checked_cnvlists = cnv_filters.get("cnvlists", [])
        checked_cnvlists_genes_dict = gene_list_resources(assay_config, checked_cnvlists)
        _genes_covered_in_panel, filter_genes = get_sample_effective_genes(
            sample, assay_panel_doc, checked_cnvlists_genes_dict, target="cnv"
        )
        cnv_filters["restrict_to_genes"] = True
        cnvs = self.load_cnvs_for_sample(
            sample=sample,
            sample_filters=cnv_filters,
            filter_genes=filter_genes,
            assay_panel=assay_panel_doc,
            assay_group=assay_config.get("asp_group"),
            stream=True,
        )
        query_params = query.parameters
        search_query = str(query_params.get("q", "")).strip()
        sort_specs = parse_sort_specs(query_params)
        page, per_page = query_pagination(query.parameters)
        page_cnvs, pagination_meta = select_table_rows(
            cnvs,
            page_sorter=self.page_sorter,
            search_query=search_query,
            text_builder=_cnv_search_text,
            specs=sort_specs,
            value_getter=_cnv_sort_value,
            page=page if paginate else None,
            per_page=per_page,
        )
        page_genes = [
            str(gene.get("gene") or gene.get("name"))
            for cnv in page_cnvs
            for gene in (cnv.get("genes") or [])
            if isinstance(gene, dict) and (gene.get("gene") or gene.get("name"))
        ]
        return {
            "sample": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "asp_id": sample.get("asp_id"),
                "environment": sample.get("environment"),
                "purity": (sample.get("case") or {}).get("purity"),
                "files": deepcopy(sample.get("files") or {}),
            },
            "meta": {
                "request_path": query.source_path,
                **pagination_meta,
                "search": search_query,
                "sort": sort_spec_to_query_value(sort_specs),
            },
            "filters": sample_filters,
            "cnvs": page_cnvs,
            "cosmic_cancer_gene_map": cosmic_cancer_gene_map(self.cosmic_repository, page_genes),
        }

    def show_cnv_payload(self, *, sample: dict, cnv_id: str) -> dict[str, Any]:
        """Return the detail payload for a single CNV.

        Args:
            sample: Sample payload owning the CNV.
            cnv_id: CNV identifier to load.

        Returns:
            dict[str, Any]: CNV detail payload for the UI.
        """
        cnv = self.copy_number_variant_repository.get_cnv(cnv_id)
        if not cnv:
            raise api_error(404, "CNV not found")
        owner = cnv.get("SAMPLE_ID")
        if not owner or not sample.get("_id") or str(owner) != str(sample["_id"]):
            raise api_error(404, "CNV not found for sample")

        assay_config = self._get_formatted_assay_config(sample)
        assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
        sample_ids = get_case_and_control_sample_ids(sample)
        cosmic = self.cosmic_repository.get_cnv_evidence(
            cnv, genome_build=sample.get("genome_build")
        )
        _, classification, alternatives, _ = self.annotation_repository.get_global_annotations(
            {
                "nomenclature": "cn",
                "variant": f"{cnv.get('chr')}:{cnv.get('start')}-{cnv.get('end')}",
                "SAMPLE_ID": cnv.get("SAMPLE_ID"),
            },
            assay_group,
            sample.get("diagnosis_id") or "base",
            sample_context=assay_config["aspc_resolution"]["context"],
            include_history=True,
        )
        return {
            "latest_classification": classification,
            "other_classifications": alternatives,
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "asp_id": sample.get("asp_id"),
                "assay_group": assay_group,
            },
            "cnv": cnv,
            "annotations": self.copy_number_variant_repository.get_cnv_annotations(
                cnv, sample_context=assay_config["aspc_resolution"]["context"]
            ),
            "sample_ids": sample_ids,
            **alignment_files_payload(
                sample,
                sample_ids,
                self.bam_record_repository.get_bams,
                asp=assay_resource(assay_config),
            ),
            "has_hidden_comments": self.copy_number_variant_repository.hidden_cnv_comments(cnv_id),
            "hidden_comments": self.copy_number_variant_repository.hidden_cnv_comments(cnv_id),
            "assay_group": assay_group,
            "cosmic": cosmic,
        }

    def require_resource_for_sample(self, *, sample: dict, resource: str, resource_id: str) -> dict:
        """Require a CNV or translocation to belong to the authorized sample."""
        from coyote3.application.common.finding_access import require_sample_finding

        loaders = {
            "cnv": self.copy_number_variant_repository.get_cnv,
            "translocation": self.translocation_repository.get_transloc,
        }
        return require_sample_finding(sample, resource_id, loaders[resource])

    def set_cnv_flag(self, *, sample: dict, cnv_id: str, apply: bool, flag: str) -> OperationResult:
        """Set an allowed flag using the authorized sample in the write predicate."""
        fields = {"interesting": "interesting", "false_positive": "fp", "noteworthy": "noteworthy"}
        if flag not in fields:
            raise ValueError(f"Unsupported flag: {flag}")
        return self.copy_number_variant_repository.set_sample_finding_flag(
            sample_id=str(sample["_id"]), resource_ids=[cnv_id], flag=fields[flag], value=apply
        )

    def set_cnv_comment_hidden(self, *, cnv_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a CNV comment."""
        if hidden:
            self.copy_number_variant_repository.hide_cnvs_comment(cnv_id, comment_id)
            return
        self.copy_number_variant_repository.unhide_cnvs_comment(cnv_id, comment_id)

    def list_translocations_payload(
        self, *, query: AnalysisQuery, sample: dict, paginate: bool = True
    ) -> dict[str, Any]:
        """Return the translocation list payload for a sample.

        Args:
            query: Active query used for metadata.
            sample: Sample payload to inspect.

        Returns:
            dict[str, Any]: Translocation list payload for the UI.
        """
        assay_config = self._get_formatted_assay_config(sample)
        if not assay_config:
            raise setup_error(
                "ASPC could not be resolved for the sample",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                    "configuration during translocation loading."
                ),
            )
        sample_filters = merge_filter_defaults(
            sample.get("filters"),
            assay_config.get("filters"),
            asp_category="dna",
            analysis_intents=sample.get("analysis_intents"),
        )
        translocation_filters = merged_dna_translocation_filters(
            sample_filters,
            analysis_intents=sample.get("analysis_intents"),
        )
        assay_panel_doc = assay_resource(assay_config)
        selected_list_ids = list(translocation_filters.get("fusionlists") or [])
        selected_lists = gene_list_resources(assay_config, selected_list_ids)
        _covered_map, filter_genes = get_sample_effective_genes(
            {**sample, "filters": sample_filters},
            assay_panel_doc,
            selected_lists,
            target="translocation",
        )

        policy_settings = {
            "filter_genes": filter_genes,
            **translocation_filters,
            "assay_group": assay_config.get("asp_group"),
            "asp_id": sample.get("asp_id"),
            "diagnosis_id": sample.get("diagnosis_id"),
            "intent": "somatic",
        }
        translocation_policy = effective_policy(
            self.query_rule_service,
            "translocation",
            sample,
            assay_group=assay_config.get("asp_group"),
        )

        def translocation_rows() -> Iterable[dict[str, Any]]:
            """Apply the established gene and policy filters to cursor batches."""
            cursor = self.translocation_repository.get_sample_translocations(
                build_transloc_query(
                    str(sample["_id"]), policy_settings, policy=translocation_policy
                ),
                stream=True,
            )
            for batch in batched(cursor, 100):
                yield from filter_translocations_by_genes(
                    list(batch),
                    filter_genes=filter_genes,
                    restricted=True,
                    settings=policy_settings,
                    policy=translocation_policy,
                )

        query_params = query.parameters
        search_query = str(query_params.get("q", "")).strip()
        sort_specs = parse_sort_specs(query_params)
        page, per_page = query_pagination(query.parameters)
        page_translocs, pagination_meta = select_table_rows(
            translocation_rows(),
            page_sorter=self.page_sorter,
            search_query=search_query,
            text_builder=_translocation_search_text,
            specs=sort_specs,
            value_getter=_translocation_sort_value,
            page=page if paginate else None,
            per_page=per_page,
        )
        page_genes = [gene for transloc in page_translocs for gene in translocation_genes(transloc)]
        return {
            "sample": {
                "database_versions": sample.get("database_versions") or {},
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "asp_id": sample.get("asp_id"),
                "environment": sample.get("environment"),
            },
            "meta": {
                "request_path": query.source_path,
                **pagination_meta,
                "search": search_query,
                "sort": sort_spec_to_query_value(sort_specs),
            },
            "filters": sample_filters,
            "snpeff_conseq_translations": snpeff_consequence_metadata(page_translocs),
            "translocations": page_translocs,
            "cosmic_cancer_gene_map": cosmic_cancer_gene_map(self.cosmic_repository, page_genes),
        }

    def show_translocation_payload(self, *, sample: dict, transloc_id: str) -> dict[str, Any]:
        """Return the detail payload for a single translocation.

        Args:
            sample: Sample payload owning the translocation.
            transloc_id: Translocation identifier to load.

        Returns:
            dict[str, Any]: Translocation detail payload for the UI.
        """
        transloc = self.translocation_repository.get_transloc(transloc_id)
        if not transloc:
            raise api_error(404, "Translocation not found")
        owner = transloc.get("SAMPLE_ID")
        if not owner or not sample.get("_id") or str(owner) != str(sample["_id"]):
            raise api_error(404, "Translocation not found for sample")

        assay_config = self._get_formatted_assay_config(sample)
        assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
        sample_ids = get_case_and_control_sample_ids(sample)
        cosmic = self.cosmic_repository.get_translocation_evidence(
            transloc, genome_build=sample.get("genome_build")
        )
        annotations = (transloc.get("INFO") or {}).get("ANN") or []
        genes = [gene for row in annotations for gene in str(row.get("Gene_Name") or "").split("&")]
        records = (
            self.hgnc_repository.get_metadata_by_ids_and_symbols([], genes)
            if self.hgnc_repository
            else []
        )
        by_id, by_symbol = build_hgnc_lookup_maps(records)
        _, classification, alternatives, _ = self.annotation_repository.get_global_annotations(
            {
                "nomenclature": "t",
                "variant": translocation_annotation_identity(transloc),
                "SAMPLE_ID": transloc.get("SAMPLE_ID"),
            },
            assay_group,
            sample.get("diagnosis_id") or "base",
            sample_context=assay_config["aspc_resolution"]["context"],
            include_history=True,
        )
        return {
            "latest_classification": classification,
            "other_classifications": alternatives,
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "asp_id": sample.get("asp_id"),
                "assay_group": assay_group,
            },
            "translocation": transloc,
            "transcript_combinations": structural_transcript_rows(annotations, by_id, by_symbol),
            "annotations": self.translocation_repository.get_transloc_annotations(
                transloc, sample_context=assay_config["aspc_resolution"]["context"]
            ),
            "sample_ids": sample_ids,
            **alignment_files_payload(
                sample,
                sample_ids,
                self.bam_record_repository.get_bams,
                asp=assay_resource(assay_config),
            ),
            "snpeff_conseq_translations": snpeff_consequence_metadata([transloc]),
            "has_hidden_comments": self.translocation_repository.hidden_transloc_comments(
                transloc_id
            ),
            "hidden_comments": self.translocation_repository.hidden_transloc_comments(transloc_id),
            "assay_group": assay_group,
            "cosmic": cosmic,
        }

    def set_translocation_flag(
        self, *, sample: dict, transloc_id: str, apply: bool, flag: str
    ) -> OperationResult:
        """Set an allowed flag using the authorized sample in the write predicate."""
        fields = {
            "interesting": "interesting",
            "false_positive": "fp",
            "irrelevant": "irrelevant",
            "blacklisted": "blacklisted",
        }
        if flag not in fields:
            raise ValueError(f"Unsupported flag: {flag}")
        return self.translocation_repository.set_sample_finding_flag(
            sample_id=str(sample["_id"]), resource_ids=[transloc_id], flag=fields[flag], value=apply
        )

    def set_translocation_comment_hidden(
        self, *, transloc_id: str, comment_id: str, hidden: bool
    ) -> None:
        """Hide or unhide a translocation comment."""
        if hidden:
            self.translocation_repository.hide_transloc_comment(transloc_id, comment_id)
            return
        self.translocation_repository.unhide_transloc_comment(transloc_id, comment_id)
