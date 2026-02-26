"""Coverage processing helpers for FastAPI coverage routes."""

from __future__ import annotations

from collections import defaultdict

from coyote.extensions import store


class CoverageProcessingService:
    @staticmethod
    def _genes_map(cov: dict | None) -> dict:
        if not isinstance(cov, dict):
            return {}
        genes = cov.get("genes")
        return genes if isinstance(genes, dict) else {}

    @staticmethod
    def find_low_covered_genes(cov: dict, cutoff: float, smp_grp: str) -> dict:
        keep = defaultdict(dict)
        genes = CoverageProcessingService._genes_map(cov)
        for gene, gene_cov in genes.items():
            has_low = False
            if "CDS" in gene_cov:
                has_low = CoverageProcessingService.reg_low(
                    gene_cov["CDS"], "CDS", cutoff, gene, smp_grp
                )
            if "probes" in gene_cov:
                has_low = CoverageProcessingService.reg_low(
                    gene_cov["probes"],
                    "probe",
                    cutoff,
                    gene,
                    smp_grp,
                )
            if has_low:
                keep["genes"][gene] = gene_cov
        return keep

    @staticmethod
    def organize_data_for_d3(filtered_dict: dict) -> dict:
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
    def filter_genes_from_form(cov_dict: dict, filter_genes: list, smp_grp: str) -> dict:
        filtered_dict = defaultdict(dict)
        genes = CoverageProcessingService._genes_map(cov_dict)
        for gene, gene_cov in genes.items():
            blacklisted = store.groupcov_handler.is_gene_blacklisted(gene, smp_grp)
            if gene in filter_genes and not blacklisted:
                filtered_dict["genes"][gene] = gene_cov
        return filtered_dict

    @staticmethod
    def reg_low(region_dict: dict, region: str, cutoff: float, gene: str, smp_grp: str) -> bool:
        has_low = False
        for reg in region_dict:
            if "cov" in region_dict[reg] and float(region_dict[reg]["cov"]) < cutoff:
                blacklisted = store.groupcov_handler.is_region_blacklisted(gene, region, reg, smp_grp)
                if not blacklisted:
                    has_low = True
        return has_low

    @staticmethod
    def coverage_table(cov_dict: dict, cov_cutoff: float) -> defaultdict:
        cov_table = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        genes = CoverageProcessingService._genes_map(cov_dict)
        for gene, gene_cov in genes.items():
            if "probes" in gene_cov:
                for probe in gene_cov["probes"]:
                    exons = CoverageProcessingService.assign_to_exon(probe, gene_cov)
                    gene_cov["probes"][probe]["exon_nr"] = exons
                    if len(exons) > 0:
                        for exon in exons:
                            if float(exon["cov"]) < cov_cutoff or float(gene_cov["probes"][probe]["cov"]) < cov_cutoff:
                                cov_table[gene][exon["nbr"]] = exon
                    elif float(gene_cov["probes"][probe]["cov"]) < cov_cutoff:
                        cov_table[gene][probe] = gene_cov["probes"][probe]
            else:
                for exon in gene_cov["CDS"]:
                    cov = gene_cov["CDS"][exon].get("cov", None)
                    if cov is not None and float(cov) < cov_cutoff:
                        cov_table[gene][gene_cov["CDS"][exon]["nbr"]] = gene_cov["CDS"][exon]
        return cov_table

    @staticmethod
    def assign_to_exon(probe: str, gene_cov: dict) -> list:
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
