from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from flask import current_app as app
from coyote.extensions import store
from bisect import bisect_left


class CoverageUtility:
    """
    This class contains utility functions for coverage data processing.
    """

    @staticmethod
    def find_low_covered_genes(cov, cutoff, smp_grp):
        """
        find low covered parts in defined regions of interest
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
                    cov["genes"][gene]["probes"], "probe", cutoff, gene, smp_grp
                )
            if has_low == True:
                keep["genes"][gene] = cov["genes"][gene]
        return keep

    @staticmethod
    def organize_data_for_d3(filtered_dict):
        """
        This is for javascript. Data imported as dicts to make blacklisting easier
        but needs to be as lists for javascript to jsonify correctly in plot functions
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
                    probes.append(filtered_dict["genes"][gene]["probes"][probe])
                filtered_dict["genes"][gene]["probes"] = probes
            else:
                filtered_dict["genes"][gene]["probes"] = []

        return filtered_dict

    @staticmethod
    def filter_genes_from_form(cov_dict, filter_genes, smp_grp):
        filtered_dict = defaultdict(dict)
        for gene in cov_dict["genes"]:
            blacklisted = store.groupcov_handler.is_gene_blacklisted(gene, smp_grp)
            if gene in filter_genes and not blacklisted:
                filtered_dict["genes"][gene] = cov_dict["genes"][gene]
        return filtered_dict

    @staticmethod
    def reg_low(region_dict, region, cutoff, gene, smp_grp):
        """
        filter against cutoff ignore if region is blacklisted
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
    def coverage_table(cov_dict, cov_cutoff):
        """
        organize data to be presented condensed in table format
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
                                or float(gene_cov["probes"][probe]["cov"]) < cov_cutoff
                            ):
                                cov_table[gene][exon["nbr"]] = exon
                    else:
                        if float(gene_cov["probes"][probe]["cov"]) < cov_cutoff:
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
                            cov_table[gene][gene_cov["CDS"][exon]["nbr"]] = gene_cov["CDS"][exon]

        return cov_table

    @staticmethod
    def assign_to_exon(probe, gene_cov):
        """
        assign probe to correct exon(cds)
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
