"""Coverage processing helpers for FastAPI coverage routes."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy


class CoverageProcessingService:
    """Provide coverage processing workflows."""

    @staticmethod
    def _genes_map(cov: dict | None) -> dict:
        """Return the gene map from a coverage document.

        Args:
            cov: Coverage document or payload.

        Returns:
            dict: Gene map extracted from the payload.
        """
        if not isinstance(cov, dict):
            return {}
        genes = cov.get("genes")
        return genes if isinstance(genes, dict) else {}

    @staticmethod
    def _blacklist_index(entries: list[dict] | None) -> tuple[set[str], set[tuple[str, str, str]]]:
        """Build in-memory blacklist lookup sets from group entries."""
        gene_blacklist: set[str] = set()
        region_blacklist: set[tuple[str, str, str]] = set()
        for entry in entries or []:
            gene = str(entry.get("gene") or "")
            region = str(entry.get("region") or "")
            coord = str(entry.get("coord") or "")
            if not gene:
                continue
            if region == "gene":
                gene_blacklist.add(gene)
                continue
            if region and coord:
                region_blacklist.add((gene, region, coord))
        return gene_blacklist, region_blacklist

    @staticmethod
    def _region_is_blacklisted(gene: str, region: str, key: str, row: dict, entries: set) -> bool:
        """Match a stored region key or the coordinate submitted by the coverage UI.

        Args:
            gene: Gene symbol owning the interval.
            region: CDS or probe region type.
            key: Original coverage mapping key, which may be an exon number.
            row: Interval with optional chr, start and end coordinates.
            entries: Assay-group blacklist tuples of gene, type and coordinate.

        Returns:
            Whether either supported identity matches a blacklist entry.
        """
        coordinates = str(key)
        if all(row.get(field) is not None for field in ("chr", "start", "end")):
            coordinates = f"{row['chr']}:{row['start']}-{row['end']}"
        return (gene, region, str(key)) in entries or (gene, region, coordinates) in entries

    @staticmethod
    def find_low_covered_genes(
        cov: dict, cutoff: float, smp_grp: str, *, d4_coverage_blacklist_repository
    ) -> dict:
        """Return genes with unblocked low coverage, retaining their complete design.

        Args:
            cov: Coverage payload to inspect.
            cutoff: Coverage threshold for low-coverage detection.
            smp_grp: Assay group used for blacklist lookups.
            d4_coverage_blacklist_repository: Repository supplying group-scoped exclusions.

        Returns:
            Copies of retained genes with a transient blacklisted flag on CDS and
            probe intervals. Source documents are not mutated or persisted.
        """
        keep = defaultdict(dict)
        genes = CoverageProcessingService._genes_map(cov)
        gene_blacklist, region_blacklist = CoverageProcessingService._blacklist_index(
            d4_coverage_blacklist_repository.get_regions_per_group(smp_grp)
        )
        for gene, gene_cov in genes.items():
            if gene in gene_blacklist:
                continue
            gene_cov = deepcopy(gene_cov)
            for field, region in (("CDS", "CDS"), ("probes", "probe")):
                for coord, row in gene_cov.get(field, {}).items():
                    row["blacklisted"] = CoverageProcessingService._region_is_blacklisted(
                        gene, region, coord, row, region_blacklist
                    )
            has_low = False
            if "CDS" in gene_cov:
                has_low = has_low or CoverageProcessingService.reg_low(
                    gene_cov["CDS"],
                    "CDS",
                    cutoff,
                    gene,
                    smp_grp,
                    d4_coverage_blacklist_repository=d4_coverage_blacklist_repository,
                    region_blacklist=region_blacklist,
                )
            if "probes" in gene_cov:
                has_low = has_low or CoverageProcessingService.reg_low(
                    gene_cov["probes"],
                    "probe",
                    cutoff,
                    gene,
                    smp_grp,
                    d4_coverage_blacklist_repository=d4_coverage_blacklist_repository,
                    region_blacklist=region_blacklist,
                )
            if has_low:
                keep["genes"][gene] = gene_cov
        return keep

    @staticmethod
    def organize_data_for_d3(filtered_dict: dict) -> dict:
        """Normalize coverage data for D3 consumption.

        Args:
            filtered_dict: Filtered coverage payload to normalize.

        Returns:
            dict: Coverage payload with list-based exon and probe structures.
        """
        genes = CoverageProcessingService._genes_map(filtered_dict)
        for gene, gene_cov in genes.items():
            if "exons" in gene_cov:
                exons = []
                for exon in gene_cov["exons"]:
                    exons.append(gene_cov["exons"][exon])
                gene_cov["exons"] = exons
            else:
                gene_cov["exons"] = []
            if "CDS" in gene_cov:
                cds = []
                for exon in gene_cov["CDS"]:
                    cds.append(gene_cov["CDS"][exon])
                gene_cov["CDS"] = cds
            else:
                gene_cov["CDS"] = []
            if "probes" in gene_cov:
                probes = []
                for probe in gene_cov["probes"]:
                    probes.append(gene_cov["probes"][probe])
                gene_cov["probes"] = probes
            else:
                gene_cov["probes"] = []

        return filtered_dict

    @staticmethod
    def filter_genes_from_form(
        cov_dict: dict,
        filter_genes: list[str],
        smp_grp: str,
        *,
        d4_coverage_blacklist_repository,
    ) -> dict:
        """Filter coverage data down to selected genes.

        Args:
            cov_dict: Coverage payload to filter.
            filter_genes: Resolved sample eligibility. An empty list excludes all genes.
            smp_grp: Assay group used for blacklist lookups.

        Returns:
            dict: Coverage payload containing only selected genes.
        """
        filtered_dict = defaultdict(dict)
        genes = CoverageProcessingService._genes_map(cov_dict)
        filter_set = set(filter_genes or [])
        gene_blacklist, _region_blacklist = CoverageProcessingService._blacklist_index(
            d4_coverage_blacklist_repository.get_regions_per_group(smp_grp)
        )
        for gene, gene_cov in genes.items():
            if gene in filter_set and gene not in gene_blacklist:
                filtered_dict["genes"][gene] = gene_cov
        return filtered_dict

    @staticmethod
    def reg_low(
        region_dict: dict,
        region: str,
        cutoff: float,
        gene: str,
        smp_grp: str,
        *,
        d4_coverage_blacklist_repository,
        region_blacklist: set[tuple[str, str, str]] | None = None,
    ) -> bool:
        """Return whether a region collection contains low coverage.

        Args:
            region_dict: Region coverage payload keyed by coordinate.
            region: Region type being evaluated.
            cutoff: Coverage threshold for low-coverage detection.
            gene: Gene symbol owning the regions.
            smp_grp: Assay group used for blacklist lookups.

        Returns:
            bool: ``True`` when a non-blacklisted region is below the cutoff.
        """
        has_low = False
        for reg in region_dict:
            if region_dict[reg].get("cov") is not None and float(region_dict[reg]["cov"]) < cutoff:
                if region_blacklist is not None:
                    blacklisted = CoverageProcessingService._region_is_blacklisted(
                        gene, region, reg, region_dict[reg], region_blacklist
                    )
                else:
                    blacklisted = d4_coverage_blacklist_repository.is_region_blacklisted(
                        gene, region, reg, smp_grp
                    )
                if not blacklisted:
                    has_low = True
        return has_low

    @staticmethod
    def coverage_table(cov_dict: dict, cov_cutoff: float) -> defaultdict:
        """Include low-coverage coding regions and regions identified by low probes.

        Args:
            cov_dict: Coverage payload to summarize.
            cov_cutoff: Coverage threshold for table inclusion.

        Returns:
            defaultdict: Nested coverage table keyed by gene and region.
        """
        cov_table = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        genes = CoverageProcessingService._genes_map(cov_dict)
        for gene, gene_cov in genes.items():
            if "probes" in gene_cov:
                for probe in gene_cov["probes"]:
                    exons = CoverageProcessingService.assign_to_exon(probe, gene_cov)
                    gene_cov["probes"][probe]["exon_nr"] = exons
                    if gene_cov["probes"][probe].get("blacklisted"):
                        continue
                    exons = [exon for exon in exons if not exon.get("blacklisted")]
                    if len(exons) > 0:
                        for exon in exons:
                            exon_cov = exon.get("cov")
                            probe_cov = gene_cov["probes"][probe].get("cov")
                            if (exon_cov is not None and float(exon_cov) < cov_cutoff) or (
                                probe_cov is not None and float(probe_cov) < cov_cutoff
                            ):
                                cov_table[gene][exon["nbr"]] = exon
                    elif (
                        gene_cov["probes"][probe].get("cov") is not None
                        and float(gene_cov["probes"][probe]["cov"]) < cov_cutoff
                    ):
                        cov_table[gene][probe] = gene_cov["probes"][probe]
            for exon in gene_cov.get("CDS", {}).values():
                cov = exon.get("cov")
                if not exon.get("blacklisted") and cov is not None and float(cov) < cov_cutoff:
                    cov_table[gene][exon["nbr"]] = exon
        return cov_table

    @staticmethod
    def assign_to_exon(probe: str, gene_cov: dict) -> list:
        """Return exons overlapped by a probe.

        Args:
            probe: Probe identifier to resolve.
            gene_cov: Coverage payload for the gene.

        Returns:
            list: Exon payloads overlapped by the probe.
        """
        exons = []
        if "CDS" not in gene_cov or "probes" not in gene_cov or probe not in gene_cov["probes"]:
            return exons
        for exon in gene_cov["CDS"]:
            p_start = int(gene_cov["probes"][probe]["start"])
            p_end = int(gene_cov["probes"][probe]["end"])
            e_start = int(gene_cov["CDS"][exon]["start"])
            e_end = int(gene_cov["CDS"][exon]["end"])
            if p_start <= e_end and p_end >= e_start:
                exons.append(gene_cov["CDS"][exon])
        return exons
