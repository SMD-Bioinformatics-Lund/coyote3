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
Utility functions for processing genomic coverage data, including identification of low-covered genes and regions, data organization for visualization, gene filtering, and probe-to-exon assignment. Designed for use within the Coyote3 genomic analysis framework.
"""

from collections import defaultdict
from coyote.extensions import store


class CoverageUtility:
    """
    CoverageUtility provides static methods for processing genomic coverage data.

    Main functionalities:
    - Identifies low-covered genes and regions based on coverage cutoffs.
    - Organizes data structures for visualization (e.g., for JavaScript/D3).
    - Filters genes based on user input and blacklist status.
    - Assigns probes to exons for accurate mapping.
    - Generates condensed coverage tables for reporting.

    Intended for use within the Coyote3 genomic analysis framework.
    """

    @staticmethod
    def find_low_covered_genes(cov: dict, cutoff: float, smp_grp: str) -> dict:
        """
        Identifies low-covered regions within specified genes of interest.

        Args:
            cov (dict): Coverage data structured by gene, containing subregions such as 'CDS' and 'probes'.
            cutoff (float): Coverage threshold below which a region is considered low-covered.
            smp_grp (str): Sample group identifier for blacklist checks.

        Returns:
            dict: Dictionary of genes with at least one region below the coverage cutoff and not blacklisted.
        """
        keep = defaultdict(dict)
        for gene in cov["genes"]:
            has_low = False
            if "CDS" in cov["genes"][gene]:
                has_low = CoverageUtility.reg_low(
                    cov["genes"][gene]["CDS"], "CDS", cutoff, gene, smp_grp
                )
            if "probes" in cov["genes"][gene]:
                has_low = CoverageUtility.reg_low(
                    cov["genes"][gene]["probes"],
                    "probe",
                    cutoff,
                    gene,
                    smp_grp,
                )
            if has_low:
                keep["genes"][gene] = cov["genes"][gene]
        return keep

    @staticmethod
    def organize_data_for_d3(filtered_dict: dict) -> dict:
        """
        Converts gene, exon, and probe data from dictionary format to lists for JavaScript visualization.

        This transformation is necessary because data is initially structured as dictionaries to facilitate
        blacklisting and filtering operations in Python. However, JavaScript visualization libraries (such as D3)
        require data in list format for proper JSON serialization and plotting.

        Args:
            filtered_dict (dict): Dictionary containing gene coverage data with nested dictionaries for exons, CDS, and probes.

        Returns:
            dict: The input dictionary with 'exons', 'CDS', and 'probes' fields converted to lists for each gene.
        """
        for gene in filtered_dict["genes"]:
            if "exons" in filtered_dict["genes"][gene]:
                exons = []
                for exon in filtered_dict["genes"][gene]["exons"]:
                    exons.append(filtered_dict["genes"][gene]["exons"][exon])
                filtered_dict["genes"][gene]["exons"] = exons
            else:
                filtered_dict["genes"][gene]["exons"] = []
            if "CDS" in filtered_dict["genes"][gene]:
                cds = []
                for exon in filtered_dict["genes"][gene]["CDS"]:
                    cds.append(filtered_dict["genes"][gene]["CDS"][exon])
                filtered_dict["genes"][gene]["CDS"] = cds
            else:
                filtered_dict["genes"][gene]["CDS"] = []
            if "probes" in filtered_dict["genes"][gene]:
                probes = []
                for probe in filtered_dict["genes"][gene]["probes"]:
                    probes.append(
                        filtered_dict["genes"][gene]["probes"][probe]
                    )
                filtered_dict["genes"][gene]["probes"] = probes
            else:
                filtered_dict["genes"][gene]["probes"] = []

        return filtered_dict

    @staticmethod
    def filter_genes_from_form(
        cov_dict: dict, filter_genes: list, smp_grp: str
    ) -> dict:
        """
        Filters the genes in the coverage dictionary, keeping only those present in the provided list and not blacklisted for the given sample group.

        Args:
            cov_dict (dict): Dictionary containing gene coverage data.
            filter_genes (list): List of gene names to retain.
            smp_grp (str): Sample group identifier for blacklist checking.

        Returns:
            dict: Filtered dictionary containing only allowed genes.
        """
        filtered_dict = defaultdict(dict)
        for gene in cov_dict["genes"]:
            blacklisted = store.groupcov_handler.is_gene_blacklisted(
                gene, smp_grp
            )
            if gene in filter_genes and not blacklisted:
                filtered_dict["genes"][gene] = cov_dict["genes"][gene]
        return filtered_dict

    @staticmethod
    def reg_low(
        region_dict: dict, region: str, cutoff: float, gene: str, smp_grp: str
    ) -> bool:
        """
        Checks if any region in the given region dictionary has coverage below the specified cutoff,
        ignoring regions that are blacklisted for the given gene, region type, and sample group.

        Args:
            region_dict (dict): Dictionary of regions (e.g., exons or probes) with coverage information.
            region (str): The type of region (e.g., 'CDS', 'probe').
            cutoff (float): Coverage threshold below which a region is considered low-covered.
            gene (str): Gene name.
            smp_grp (str): Sample group identifier for blacklist checks.

        Returns:
            bool: True if at least one non-blacklisted region is below the cutoff, False otherwise.
        """
        has_low = False
        for reg in region_dict:
            if "cov" in region_dict[reg]:
                if float(region_dict[reg]["cov"]) < cutoff:
                    blacklisted = store.groupcov_handler.is_region_blacklisted(
                        gene, region, reg, smp_grp
                    )
                    if not blacklisted:
                        has_low = True
        return has_low

    @staticmethod
    def coverage_table(cov_dict: dict, cov_cutoff: float) -> defaultdict:
        """
        Organizes coverage data into a condensed table format for reporting.

        Args:
            cov_dict (dict): Dictionary containing gene coverage data.
            cov_cutoff (float): Coverage threshold for identifying low-covered regions.

        Returns:
            defaultdict: Nested dictionary summarizing low-covered exons or probes per gene.
        """
        cov_table = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        for gene in cov_dict["genes"]:
            gene_cov = cov_dict["genes"][gene]
            # if data has probes, create cov table based on these and their overlap to CDS
            if "probes" in gene_cov:
                for probe in gene_cov["probes"]:
                    exons = CoverageUtility.assign_to_exon(probe, gene_cov)
                    cov_dict["genes"][gene]["probes"][probe]["exon_nr"] = exons
                    if len(exons) > 0:
                        for exon in exons:
                            if (
                                float(exon["cov"]) < cov_cutoff
                                or float(gene_cov["probes"][probe]["cov"])
                                < cov_cutoff
                            ):
                                cov_table[gene][exon["nbr"]] = exon
                    else:
                        if (
                            float(gene_cov["probes"][probe]["cov"])
                            < cov_cutoff
                        ):
                            cov_table[gene][probe] = gene_cov["probes"][probe]
            else:
                """
                assign low cov CDS to cov_table
                """
                for exon in gene_cov["CDS"]:
                    cov = gene_cov["CDS"][exon].get("cov", None)
                    if cov is not None:
                        cov = float(cov)
                        if cov < cov_cutoff:
                            cov_table[gene][gene_cov["CDS"][exon]["nbr"]] = (
                                gene_cov["CDS"][exon]
                            )

        return cov_table

    @staticmethod
    def assign_to_exon(probe: str, gene_cov: dict) -> list:
        """
        Assigns a probe to the correct exon(s) (CDS) based on genomic coordinate overlap.

        Args:
            probe: The probe identifier (key) in the gene coverage dictionary.
            gene_cov (dict): Dictionary containing 'probes' and 'CDS' (exons) with their start and end positions.

        Returns:
            list: List of exon (CDS) dictionaries that overlap with the given probe.
        """
        exons = []
        for exon in gene_cov["CDS"]:
            p_start = int(gene_cov["probes"][probe]["start"])
            p_end = int(gene_cov["probes"][probe]["end"])
            e_start = int(gene_cov["CDS"][exon]["start"])
            e_end = int(gene_cov["CDS"][exon]["end"])
            if p_start <= e_end and p_end >= e_start:
                exons.append(gene_cov["CDS"][exon])
        # exons = ','.join(exons)
        return exons
