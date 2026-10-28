"""Shared knowledgebase reads and access-scoped clinical cohort use cases."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from coyote3.application.common.access import sample_scope_allowed
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error
from coyote3.domain.exceptions import AppError

if TYPE_CHECKING:
    from coyote3.application.common.query_service import CommonQueryService


class Knowledgebase:
    """Knowledgebase operations with actor-derived clinical visibility."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], CommonQueryService],
        *,
        search_limit: int,
    ) -> None:
        """Bind authorization, evidence repositories and the configured result limit."""
        self._runtime, self._service = runtime, service
        self._search_limit = search_limit

    def _require_visible_sample(self, sample_id: str, actor: Any) -> None:
        """Reject absent or unauthorized source samples without returning their metadata."""
        sample = self._runtime.sample_loader(sample_id)
        if not sample:
            raise api_error(404, "Sample not found")
        if not sample_scope_allowed(
            actor,
            sample,
            policy_factory=self._runtime.policy_factory,
            assay_loader=self._runtime.assay_loader,
        ):
            raise api_error(403, "Sample is outside your access scope")

    def gene_cohort(self, *, gene_id: str, include_history: bool = False) -> dict[str, Any]:
        """Return prevalence and recurrent typed findings for visible samples.

        Args:
            gene_id: Gene identifier or HGNC symbol.
            include_history: Include all saved report versions when True; defaults to False.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return cast(
                dict[str, Any],
                self._service().gene_cohort_payload(
                    gene_id=gene_id,
                    visible_asp_ids=None if actor.is_superuser else list(actor.asp_ids),
                    visible_environments=None if actor.is_superuser else list(actor.envs),
                    include_history=include_history,
                ),
            )

        return self._runtime.execute("knowledgebase.gene_cohort", ("gene.annotation:view",), run)

    def cancer_gene_census_summary(self) -> dict[str, Any]:
        """Return non-clinical CGC distributions when the collection is populated.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return cast(dict[str, Any], self._service().cancer_gene_census_summary())

        return self._runtime.execute("knowledgebase.cancer_gene_census_summary", None, run)

    def statistics(self) -> dict[str, Any]:
        """Return non-clinical source coverage statistics.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return cast(dict[str, Any], self._service().knowledgebase_statistics())

        return self._runtime.execute("knowledgebase.statistics", None, run)

    def gene(self, *, gene_id: str) -> dict[str, Any]:
        """Return HGNC-normalized gene context across configured knowledgebases.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return cast(dict[str, Any], self._service().knowledgebase_gene_payload(gene_id))

        return self._runtime.execute("knowledgebase.gene", ("gene.annotation:view",), run)

    def oncokb_gene(self, *, gene_id: str) -> dict[str, Any]:
        """Return only OncoKB-related gene context.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            payload = self._service().knowledgebase_gene_payload(gene_id)
            sources = {
                key: value for key, value in payload["sources"].items() if key.startswith("oncokb")
            }
            payload["sources"] = sources
            payload["available_sources"] = self._service()._available_sources(sources)
            return cast(dict[str, Any], payload)

        return self._runtime.execute("knowledgebase.oncokb_gene", ("gene.annotation:view",), run)

    def clinpgx_gene(self, *, gene_id: str) -> dict[str, Any]:
        """Return only local ClinPGx public gene-marker context.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            payload = self._service().knowledgebase_gene_payload(gene_id)
            sources = {"clinpgx_public": payload["sources"].get("clinpgx_public")}
            payload["sources"] = sources
            payload["available_sources"] = self._service()._available_sources(sources)
            return cast(dict[str, Any], payload)

        return self._runtime.execute("knowledgebase.clinpgx_gene", ("gene.annotation:view",), run)

    def civic_gene(self, *, gene_id: str) -> dict[str, Any]:
        """Return only local CIViC gene context.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            payload = self._service().knowledgebase_gene_payload(gene_id)
            sources = {"civic_gene": payload["sources"].get("civic_gene")}
            payload["sources"] = sources
            payload["available_sources"] = self._service()._available_sources(sources)
            return cast(dict[str, Any], payload)

        return self._runtime.execute("knowledgebase.civic_gene", ("gene.annotation:view",), run)

    def brca_exchange_gene(self, *, gene_id: str) -> dict[str, Any]:
        """Return BRCA Exchange gene applicability context.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            return _single_source_gene_payload(
                service=self._service(), gene_id=gene_id, source_keys=("brca_exchange",)
            )

        return self._runtime.execute(
            "knowledgebase.brca_exchange_gene", ("gene.annotation:view",), run
        )

    def iarc_tp53_gene(self, *, gene_id: str) -> dict[str, Any]:
        """Read IARC TP53 applicability for a gene with gene.annotation:view permission.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            IARC TP53 gene evidence and source availability.
        """
        return self._runtime.execute(
            "knowledgebase.iarc_tp53_gene",
            ("gene.annotation:view",),
            lambda actor, sample: _single_source_gene_payload(
                service=self._service(), gene_id=gene_id, source_keys=("iarc_tp53",)
            ),
        )

    def variant_evidence(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
        genome_build: int | None = None,
    ) -> dict[str, Any]:
        """Read aggregated local evidence with gene.annotation:view.

        Args:
            chrom: Reference chromosome name.
            pos: One-based reference position.
            ref: Reference allele.
            alt: Alternate allele.
            gene: HGNC gene symbol.
            hgvsc: Optional coding transcript consequence; None omits this match.
            hgvsp: Optional protein consequence; None omits this match.
            assay_group: Biological assay group; defaults to dna.
            genome_build: Reference assembly number; None uses source defaults.

        Returns:
            Matching local evidence and source availability.

        Raises:
            AppError: Authentication, permission or evidence selection is invalid.
        """
        return self._runtime.execute(
            "knowledgebase.variant_evidence",
            ("gene.annotation:view",),
            lambda actor, sample: dict(
                self._service().knowledgebase_variant_payload(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alt=alt,
                    gene=gene,
                    hgvsc=hgvsc,
                    hgvsp=hgvsp,
                    assay_group=assay_group,
                    genome_build=genome_build,
                )
            ),
        )

    def civic_variant_evidence(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
        genome_build: int | None = None,
    ) -> dict[str, Any]:
        """Read CIViC evidence with gene.annotation:view.

        Args:
            chrom: Reference chromosome name.
            pos: One-based reference position.
            ref: Reference allele.
            alt: Alternate allele.
            gene: HGNC gene symbol.
            hgvsc: Optional coding transcript consequence; None omits this match.
            hgvsp: Optional protein consequence; None omits this match.
            assay_group: Biological assay group; defaults to dna.
            genome_build: Reference assembly number; None uses source defaults.

        Returns:
            Matching local evidence and source availability.

        Raises:
            AppError: Authentication, permission or evidence selection is invalid.
        """
        return self._runtime.execute(
            "knowledgebase.civic_variant_evidence",
            ("gene.annotation:view",),
            lambda actor, sample: _single_source_variant_payload(
                service=self._service(),
                source_keys=("civic_variants",),
                chrom=chrom,
                pos=pos,
                ref=ref,
                alt=alt,
                gene=gene,
                hgvsc=hgvsc,
                hgvsp=hgvsp,
                assay_group=assay_group,
                genome_build=genome_build,
            ),
        )

    def brca_exchange_variant_evidence(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
        genome_build: int | None = None,
    ) -> dict[str, Any]:
        """Read BRCA Exchange evidence with gene.annotation:view.

        Args:
            chrom: Reference chromosome name.
            pos: One-based reference position.
            ref: Reference allele.
            alt: Alternate allele.
            gene: HGNC gene symbol.
            hgvsc: Optional coding transcript consequence; None omits this match.
            hgvsp: Optional protein consequence; None omits this match.
            assay_group: Biological assay group; defaults to dna.
            genome_build: Reference assembly number; None uses source defaults.

        Returns:
            Matching local evidence and source availability.

        Raises:
            AppError: Authentication, permission or evidence selection is invalid.
        """
        return self._runtime.execute(
            "knowledgebase.brca_exchange_variant_evidence",
            ("gene.annotation:view",),
            lambda actor, sample: _single_source_variant_payload(
                service=self._service(),
                source_keys=("brca_exchange",),
                chrom=chrom,
                pos=pos,
                ref=ref,
                alt=alt,
                gene=gene,
                hgvsc=hgvsc,
                hgvsp=hgvsp,
                assay_group=assay_group,
                genome_build=genome_build,
            ),
        )

    def iarc_tp53_variant_evidence(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
        genome_build: int | None = None,
    ) -> dict[str, Any]:
        """Read IARC TP53 evidence with gene.annotation:view.

        Args:
            chrom: Reference chromosome name.
            pos: One-based reference position.
            ref: Reference allele.
            alt: Alternate allele.
            gene: HGNC gene symbol.
            hgvsc: Optional coding transcript consequence; None omits this match.
            hgvsp: Optional protein consequence; None omits this match.
            assay_group: Biological assay group; defaults to dna.
            genome_build: Reference assembly number; None uses source defaults.

        Returns:
            Matching local evidence and source availability.

        Raises:
            AppError: Authentication, permission or evidence selection is invalid.
        """
        return self._runtime.execute(
            "knowledgebase.iarc_tp53_variant_evidence",
            ("gene.annotation:view",),
            lambda actor, sample: _single_source_variant_payload(
                service=self._service(),
                source_keys=("iarc_tp53",),
                chrom=chrom,
                pos=pos,
                ref=ref,
                alt=alt,
                gene=gene,
                hgvsc=hgvsc,
                hgvsp=hgvsp,
                assay_group=assay_group,
                genome_build=genome_build,
            ),
        )

    def tiered_variant_context(self, *, variant_id: str, tier: int) -> dict[str, Any]:
        """Read reported finding context restricted to currently visible source samples.

        Args:
            variant_id: Saved finding identifier.
            tier: Clinical tier whose saved context is requested.

        Returns:
            Finding evidence after excluding absent or inaccessible source samples.

        Raises:
            AppError: Authentication or gene.annotation:view permission is denied.
        """

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Cache visibility only for this operation's verified identity."""

            @lru_cache(maxsize=256)
            def sample_is_visible(sample_id: str) -> bool:
                """Hide unavailable samples without exposing scope or sample metadata."""
                if not sample_id:
                    return False
                try:
                    self._require_visible_sample(sample_id, actor)
                except AppError as exc:
                    if exc.status_code in {403, 404}:
                        return False
                    raise
                return True

            return dict(
                self._service().tiered_variant_context_payload(
                    variant_id=variant_id, tier=tier, sample_is_visible=sample_is_visible
                )
            )

        return self._runtime.execute(
            "knowledgebase.tiered_variant_context", ("gene.annotation:view",), read
        )

    def tiered_variant_search(
        self,
        *,
        search_str: str | None = None,
        search_mode: str = "gene",
        include_annotation_text: bool = False,
        assays: list[str] | None = None,
        assay: list[str] | None = None,
        nomenclatures: list[str] | None = None,
        limit_entries: int | None = None,
    ) -> dict[str, Any]:
        """Search tiered variants and related annotations across reports.

        Args:
            search_str: Gene or finding search text; None omits the text restriction.
            search_mode: Existing search strategy, such as gene; defaults to gene.
            include_annotation_text: Include authored annotation text in matching when True.
            assays: Optional assay selections; a nonempty list takes precedence over assay.
            assay: Existing alternate assay-list input; used when assays is empty or None.
            nomenclatures: Optional registered nomenclature fields used for text matching.
            limit_entries: Maximum search results; None uses the configured host search limit.

        Returns:
            Knowledgebase context or visible clinical cohort evidence.

        Raises:
            AppError: Authentication, access, selection validation or lookup fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Evaluate the operation under the current verified actor."""
            effective_limit = self._search_limit if limit_entries is None else limit_entries
            selected_assays = assays or assay

            @lru_cache(maxsize=256)
            def sample_is_visible(sample_id: str) -> bool:
                """Restrict annotation history links to samples visible to the current actor."""
                try:
                    self._require_visible_sample(sample_id, actor)
                except AppError as exc:
                    if exc.status_code in {403, 404}:
                        return False
                    raise
                return True

            return cast(
                dict[str, Any],
                self._service().tiered_variant_search_payload(
                    search_str=search_str,
                    search_mode=search_mode,
                    include_annotation_text=include_annotation_text,
                    assays=selected_assays,
                    nomenclatures=nomenclatures,
                    limit_entries=effective_limit,
                    sample_is_visible=sample_is_visible,
                ),
            )

        return self._runtime.execute(
            "knowledgebase.tiered_variant_search", ("gene.annotation:view",), run
        )


def _single_source_gene_payload(
    *, service: Any, gene_id: str, source_keys: tuple[str, ...]
) -> dict[str, Any]:
    """Return a gene payload narrowed to one knowledgebase family."""
    payload = service.knowledgebase_gene_payload(gene_id)
    sources = {key: payload["sources"].get(key) for key in source_keys}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return cast(dict[str, Any], payload)


def _single_source_variant_payload(
    *,
    service: Any,
    source_keys: tuple[str, ...],
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None,
    hgvsp: str | None,
    assay_group: str,
    genome_build: int | None = None,
) -> dict[str, Any]:
    """Return a variant-evidence payload narrowed to one knowledgebase family."""
    payload = service.knowledgebase_variant_payload(
        chrom=chrom,
        pos=pos,
        ref=ref,
        alt=alt,
        gene=gene,
        hgvsc=hgvsc,
        hgvsp=hgvsp,
        assay_group=assay_group,
        genome_build=genome_build,
    )
    sources = {key: payload["sources"].get(key) for key in source_keys}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return cast(dict[str, Any], payload)
