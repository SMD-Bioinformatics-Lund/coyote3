"""Read-only comparisons of published and proposed selection policies on stored samples."""

import logging
from copy import copy, deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.query_rules.service import QueryRuleService
from coyote3.application.reporting.rna_workflow import RNAWorkflowService
from coyote3.config.clinical_query_policy import resolved_query_policy
from coyote3.config.database_versions import require_sample_vep_version
from coyote3.contracts.schemas.query_rules import QueryRuleDoc, QueryRulePreview, QueryRuleScope
from coyote3.domain.common.assay_filters import get_sample_effective_genes
from coyote3.domain.common.errors import api_error
from coyote3.domain.common.sample_filters import (
    merge_filter_defaults,
    merged_dna_cnv_filters,
    merged_dna_translocation_filters,
    merged_dna_variant_filters,
)
from coyote3.domain.dna.cnvqueries import build_cnv_query, include_normal_cnvs
from coyote3.domain.dna.dna_filters import (
    cnvtype_variant,
    create_cnveffectlist,
    get_filter_conseq_terms,
)
from coyote3.domain.dna.translocqueries import (
    build_transloc_query,
    filter_translocations_by_genes,
)
from coyote3.domain.dna.varqueries import build_query
from coyote3.domain.finding_repositories import SampleFindingReader
from coyote3.domain.selection import Operator, RecordField, select


class QueryRuleTestingService:
    """Compare candidate membership while retaining sample filters and policy inheritance."""

    def __init__(self, store: Any) -> None:
        """Bind explicit repositories from the application store.

        Args:
            store: Repository provider; the service does not access raw collections.
        """
        self.store = store
        self.rules = QueryRuleService.from_store(store)

    def search_samples(
        self,
        *,
        scope: QueryRuleScope,
        search: str,
        page: int,
        allowed_asp_ids: list[str] | None,
        allowed_environments: list[str] | None,
    ) -> dict:
        """Search ready samples within both the rule scope and the operator's access.

        Args:
            scope: Draft or saved policy scope.
            search: Sample search text.
            page: One-based page, using twenty results per page.
            allowed_asp_ids: User assay grants; None denotes unrestricted access.
            allowed_environments: User environment grants; None denotes unrestricted access.

        Returns:
            Authorized sample identity rows and pagination metadata.
        """
        self.rules.validate_scope(scope)
        category = "rna" if scope.analysis == "fusion" else "dna"
        assays = [
            a["asp_id"]
            for a in self.store.assay_panel_repository.get_all_asps(is_active=True)
            if a.get("asp_category") == category
            and (not scope.assay_group or a.get("asp_group") == scope.assay_group)
            and (not scope.asp_id or a["asp_id"] == scope.asp_id)
            and (not scope.family or a.get("asp_family") == scope.family)
            and (allowed_asp_ids is None or a["asp_id"] in allowed_asp_ids)
        ]
        environments = allowed_environments
        if scope.environment:
            environments = (
                [scope.environment]
                if environments is None or scope.environment in environments
                else []
            )
        if not assays or environments == []:
            return {"items": [], "total": 0, "page": page, "per_page": 20}
        rows, total = self.store.sample_repository.search_samples_for_admin(
            asp_ids=assays,
            environments=environments,
            diagnosis_id=scope.diagnosis_id,
            search_str=search,
            page=page,
            per_page=20,
            ready_only=True,
        )
        return {
            "items": [
                {
                    "id": str(r["_id"]),
                    "name": str(r.get("name") or r["_id"]),
                    "asp_id": r.get("asp_id"),
                    "diagnosis_id": r.get("diagnosis_id") or "base",
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "per_page": 20,
        }

    def _proposed_service(self, request: QueryRulePreview) -> QueryRuleService:
        """Overlay a draft at its actual hierarchy level without mutating published state.

        Args:
            request: Scope and optional validated draft content.

        Returns:
            Private resolver preserving more-specific published descendants.
        """
        if request.content is None:
            return self.rules
        service = copy(self.rules)
        now = datetime.now(timezone.utc)
        draft = QueryRuleDoc(
            scope=request.scope,
            scope_key=request.scope.key(),
            content=request.content,
            name="Sample preview",
            reason="Read-only sample test",
            version=1,
            revision=1,
            status="published",
            created_by="preview",
            updated_by="preview",
            created_on=now,
            updated_on=now,
        ).model_dump(by_alias=True)

        def published_for(scope):
            """Substitute only the requested ancestor, retaining every other publication."""
            rows = self.rules.repository.published_for(scope)
            if any(
                value is not None and scope.get(key) != value
                for key, value in request.scope.model_dump().items()
            ):
                return rows
            return [row for row in rows if row["scope_key"] != request.scope.key()] + [draft]

        service.repository = SimpleNamespace(published_for=published_for)
        return service

    def preview(
        self,
        request: QueryRulePreview,
        sample: dict,
        *,
        allowed_asp_ids: list[str] | None,
        allowed_environments: list[str] | None,
    ) -> dict:
        """Compare full retrieval predicates on an already-authorized stored sample.

        Args:
            request: Rule scope and draft content; null content compares published state.
            sample: Sample after assay, environment and readiness access validation.
            allowed_asp_ids: User assay grants; None denotes unrestricted access.
            allowed_environments: User environment grants; None denotes unrestricted access.

        Returns:
            Exact candidate counts and up to one hundred added/removed identities.
            No sample, rule, finding or report is persisted.

        Raises:
            AppError: Scope mismatch, missing configuration or more than 10000 candidates.
        """
        if (allowed_asp_ids is not None and sample.get("asp_id") not in allowed_asp_ids) or (
            allowed_environments is not None
            and sample.get("environment") not in allowed_environments
        ):
            raise api_error(403, "Sample is outside your assigned scope")
        self.rules.validate_scope(request.scope)
        if sample.get("ingest_status") != "ready":
            raise api_error(422, "Only ready samples can be used for query-rule testing")
        config = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.store.assay_panel_repository,
            assay_configuration_repository=self.store.assay_configuration_repository,
        )
        context = config.get("aspc_resolution", {}).get("context", {})
        scope = QueryRuleScope(
            assay_group=config.get("asp_group"),
            asp_id=sample.get("asp_id"),
            diagnosis_id=sample.get("diagnosis_id") or "base",
            analysis=request.scope.analysis,
            intent="somatic" if request.scope.analysis == "snv" else request.scope.intent,
            environment=sample.get("environment"),
            family=context.get("family"),
            modality=context.get("modality") if context.get("family") else None,
        )
        if scope.analysis.upper() not in config.get("analysis_types", []):
            raise api_error(422, "The sample ASPC does not enable the selected analysis")
        if any(
            getattr(request.scope, key) is not None
            and getattr(request.scope, key) != getattr(scope, key)
            for key in (
                "assay_group",
                "asp_id",
                "diagnosis_id",
                "modality",
                "family",
                "environment",
            )
        ):
            raise api_error(422, "Sample is outside the query-rule scope")
        if (sample.get("asp_category") == "rna") != (scope.analysis == "fusion"):
            raise api_error(422, "Sample omics layer does not support the selected analysis")
        if scope.intent not in (sample.get("analysis_intents") or ["somatic"]):
            raise api_error(422, "Sample does not enable the selected analysis intent")
        panel = self.store.assay_panel_repository.get_asp(sample["asp_id"]) or {}
        current = self.rules.resolve(scope)
        proposed = self._proposed_service(request).resolve(scope)
        if request.content is not None:
            for source in proposed.lineage:
                if source["source"] == request.scope.key():
                    source.update(source="draft: " + request.scope.key(), version=None)
        try:
            before, before_query, post_filters = self._findings(
                sample, config, panel, scope, current
            )
            after, after_query, _ = self._findings(sample, config, panel, scope, proposed)
        except (KeyError, ValueError) as error:
            raise api_error(
                422, "Sample configuration does not satisfy the analysis contract", str(error)
            ) from error
        added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
        return {
            "sample": {"id": str(sample["_id"]), "name": str(sample.get("name") or sample["_id"])},
            "analysis": scope.analysis,
            "intent": scope.intent,
            "persisted": False,
            "published_count": len(before),
            "draft_count": len(after),
            "added_count": len(added),
            "removed_count": len(removed),
            "unchanged_count": len(before.keys() & after.keys()),
            "added": [after[key] for key in added[:100]],
            "removed": [before[key] for key in removed[:100]],
            "display_limit": 100,
            "published_policy": current.model_dump(mode="json"),
            "draft_policy": proposed.model_dump(mode="json"),
            "published_query": before_query,
            "draft_query": after_query,
            "post_filters": post_filters,
        }

    def _findings(self, sample, config, panel, scope, resolution) -> tuple[dict, dict, list[str]]:
        """Execute the analysis query and mandatory post-filters without report enrichment.

        Args:
            sample: Authorized sample, never mutated.
            config: Sample's recorded ASPC settings.
            panel: Registered ASP.
            scope: Concrete sample analysis scope.
            resolution: Published or proposed effective policy.

        Returns:
            Finding identities, an adapter-provided selection diagnostic and descriptions
            of subsequent in-memory filters. The repository independently enforces sample scope.

        Raises:
            AppError: Candidate count exceeds the bounded interactive comparison limit.
        """
        repository: SampleFindingReader
        analysis = scope.analysis
        policy = resolved_query_policy(analysis, resolution.evidence_mode, resolution.exceptions)
        filters = merge_filter_defaults(
            deepcopy(sample.get("filters")),
            config.get("filters"),
            asp_category=sample.get("asp_category") or "dna",
            analysis_intents=sample.get("analysis_intents"),
        )
        effective_sample = {**sample, "filters": filters}
        if analysis == "fusion":
            workflow = RNAWorkflowService.from_store(self.store)
            rna_sample, section = workflow.merge_and_normalize_sample_filters(
                deepcopy(sample), config, str(sample["_id"]), logging.getLogger(__name__)
            )
            context = workflow.compute_filter_context(
                sample=rna_sample,
                sample_filters=section,
                assay_panel_doc=panel,
                selected_list_docs=self.store.gene_list_repository.get_isgl_by_ids(
                    section.get("fusionlists", [])
                ),
            )
            resolver = SimpleNamespace(policy_for_sample=lambda **kwargs: policy)
            query = workflow.build_fusion_list_query(
                scope.assay_group,
                str(sample["_id"]),
                section,
                context,
                sample=sample,
                query_rule_service=resolver,
            )
            repository = self.store.fusion_repository
        else:
            section = (
                merged_dna_variant_filters(
                    filters, intent=scope.intent, analysis_intents=sample.get("analysis_intents")
                )
                if analysis == "snv"
                else merged_dna_cnv_filters(filters)
                if analysis == "cnv"
                else merged_dna_translocation_filters(
                    filters, analysis_intents=sample.get("analysis_intents")
                )
            )
            list_key = {"snv": "snvlists", "cnv": "cnvlists", "translocation": "fusionlists"}[
                analysis
            ]
            lists = self.store.gene_list_repository.get_isgl_by_ids(section.get(list_key, []))
            _, genes = get_sample_effective_genes(
                effective_sample, panel, lists, target=analysis, intent=scope.intent
            )
            settings = {
                **section,
                "id": str(sample["_id"]),
                "filter_genes": genes,
                "restrict_to_genes": True,
                "assay_group": scope.assay_group,
                "asp_id": scope.asp_id,
                "diagnosis_id": scope.diagnosis_id,
                "intent": scope.intent,
            }
            if analysis == "snv":
                groups = self.store.vep_metadata_repository.get_consequence_group_map(
                    require_sample_vep_version(sample)
                )
                settings["filter_conseq"] = get_filter_conseq_terms(
                    section.get("vep_consequences", []), groups
                )
                settings["disp_pos"] = next(
                    (
                        positions
                        for key, positions in config.get("verification_samples", {}).items()
                        if key in sample.get("name", "")
                    ),
                    [],
                )
                query = build_query(scope.assay_group, settings, intent=scope.intent, policy=policy)
                repository = self.store.variant_repository
            elif analysis == "cnv":
                query = build_cnv_query(
                    str(sample["_id"]),
                    filters=settings,
                    include_normal=include_normal_cnvs(sample, panel),
                    policy=policy,
                )
                repository = self.store.copy_number_variant_repository
            else:
                query = build_transloc_query(str(sample["_id"]), settings, policy=policy)
                repository = self.store.translocation_repository
        rows = repository.preview_sample_findings(str(sample["_id"]), query)
        if len(rows) > 10000:
            raise api_error(
                422, "Sample test exceeds 10000 candidates; use a smaller validation sample"
            )
        post_filters = []
        if analysis == "translocation":
            post_filters.append(
                "Translocation gene-scope and exception checks run after repository selection."
            )
            rows = filter_translocations_by_genes(
                rows, filter_genes=genes, restricted=True, settings=settings, policy=policy
            )
        if analysis == "cnv":
            effects = create_cnveffectlist(section.get("cnveffects", []))
            if effects:
                post_filters.append(
                    "CNV effect selection runs after repository selection: " + ", ".join(effects)
                )
                rows = cnvtype_variant(rows, effects)
        findings = {
            str(row["_id"]): {
                "id": str(row["_id"]),
                "label": str(
                    row.get("simple_id") or row.get("ID") or row.get("genes") or row["_id"]
                ),
            }
            for row in rows
        }
        return (
            findings,
            self.rules.selection_renderer(
                select({Operator.ALL: [{RecordField.SAMPLE: str(sample["_id"])}, query]})
            ),
            post_filters,
        )
